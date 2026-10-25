"""Re-run the four-scene Vectoring dose-response at 15 km.

Two arms are supported:
  old-15km     frozen nine-feature epoch-90 Encoder, no route reference
  star-15km    retrained fifteen-feature Encoder with STAR-relative channels

The frozen candidate order is reused (filtered only when a candidate cannot be
injected at 15 km). D is recomputed from the new embeddings; the fit gate is
0.95 and a threshold sensitivity table is written from the same diagnostics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial.distance import pdist

B = Path(__file__).resolve().parents[1]
WS = B / "evaluation-10s" / "workspace"
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(B / "evaluation-python-deps"), str(B / "encoder-10s" / "source"), str(WS), str(WS / "evaluation" / "code")]
import torch  # noqa: E402
from trajectory_encoder.inference import FrozenEncoder  # noqa: E402
from complexity.calculator import ComplexityConfig, estimate_complexity  # noqa: E402
from run_analysis import summarize  # noqa: E402
from truncation import finite_ok  # noqa: E402


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False), encoding="utf8")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--population", default=str(HERE / "population-15km"))
    parser.add_argument("--reference", choices=("baseline", "shuffled", "corridor", "official", "none"), default="baseline")
    parser.add_argument("--corridor-file", default=str(B / "changi-reference-2026-10-24" / "corridors-month" / "corridors.npz"))
    parser.add_argument("--max-corridor-angle-deg", type=float, default=30.0)
    parser.add_argument("--max-official-distance-m", type=float, default=10000.0)
    parser.add_argument("--min-r2", type=float, default=0.94)
    args = parser.parse_args()

    population = Path(args.population)
    generation = read(population / "summary.json")
    assignments = read(B / "four-scene-vectoring-evaluation" / "assignments.json")
    assignment_by_scene = {row["scene"]: row for row in assignments}
    eligible_by_scene = {row["scene"]: set(row["injectable"]) for row in generation["scenes"]}

    cfg = ComplexityConfig(normalize=False, min_r_squared=args.min_r2)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    encoder = FrozenEncoder(args.checkpoint, pooling="sum", device=device)
    route_aware = len(encoder.preprocess["mean"]) > 9
    if route_aware != (args.reference != "none"):
        raise ValueError("checkpoint width and --reference disagree")
    corridors = None
    if args.reference == "corridor":
        saved = np.load(args.corridor_file)
        corridors = dict(r_grid=np.asarray(saved["r_grid_km"], float),
                         lines=[np.asarray(line, float) for line in saved["centerlines"]])
    official = None
    if args.reference == "official":
        sys.path.insert(0, str(B / "changi-reference-2026-10-24"))
        from official_routes import routes as official_routes
        official = official_routes()

    def assign_corridor(p):
        """Nearest independent arrival corridor; baseline fallback outside flow."""
        r = np.linalg.norm(p[:, :2], axis=1) / 1000.0
        theta = np.arctan2(p[:, 1], p[:, 0])
        if r[0] - r[-1] <= 3.0 or p[0, 2] - p[-1, 2] <= 300:
            return p, dict(corridor=None, reason="not_an_arrival", angle_deg=None)
        best = None
        for index, line in enumerate(corridors["lines"]):
            lr = np.linalg.norm(line, axis=1) / 1000.0
            lt = np.arctan2(line[:, 1], line[:, 0])
            finite = np.isfinite(lr) & np.isfinite(lt)
            if finite.sum() < 4:
                continue
            order = np.argsort(lr[finite])
            angle = np.interp(r, lr[finite][order], np.unwrap(lt[finite])[order], left=np.nan, right=np.nan)
            valid = np.isfinite(angle)
            if valid.sum() < 5:
                continue
            residual = float(np.mean(np.abs(np.angle(np.exp(1j * (theta[valid] - angle[valid]))))))
            if best is None or residual < best[0]:
                best = (residual, index, line)
        if best is None or np.rad2deg(best[0]) > args.max_corridor_angle_deg:
            return p, dict(corridor=None, reason="outside_corridor_library",
                           angle_deg=None if best is None else float(np.rad2deg(best[0])))
        return best[2], dict(corridor=int(best[1]), reason="assigned", angle_deg=float(np.rad2deg(best[0])))

    def assign_official(p, force=False):
        """Nearest published RWY20 STAR; baseline fallback when far from all.

        ``force`` is used for injectable candidates: a vectoring candidate is
        an arrival even when its ten-minute window is level or short, so the
        official reference must not be skipped by the descent heuristic.
        """
        r = np.linalg.norm(p[:, :2], axis=1)
        if not force and (r[0] - r[-1] <= 3000 or p[0, 2] - p[-1, 2] <= 300):
            return p, dict(corridor=None, reason="not_an_arrival", angle_deg=None)
        best = None
        for name, route in official.items():
            a, b = route[:-1], route[1:]
            ab = b - a
            den = np.sum(ab * ab, axis=1)
            u = np.clip(np.einsum("nmd,md->nm", p[:, None, :2] - a[None], ab) / den, 0, 1)
            nearest = a[None] + u[..., None] * ab[None]
            distance = np.linalg.norm(p[:, None, :2] - nearest, axis=2).min(axis=1)
            residual = float(np.median(distance))
            if best is None or residual < best[0]:
                best = (residual, name, route)
        if best is None or (best[0] > args.max_official_distance_m and not force):
            return p, dict(corridor=None, reason="outside_official_stars",
                           angle_deg=None if best is None else float(best[0]))
        return best[2], dict(corridor=best[1], reason="assigned", angle_deg=float(best[0]))

    out = HERE / "results" / args.label
    out.mkdir(parents=True, exist_ok=False)
    trials = []
    diagnostics = []
    encoding_calls = 0
    for index, scene in enumerate(generation["scenes"], 1):
        sid = scene["scene"]
        records = {r["icao24"]: r for r in read(population / f"{sid}-records.json")}
        ids = sorted(records)
        saved = np.load(population / f"{sid}-population.npz")
        baseline = [saved[a + "_baseline"] for a in ids]
        eligible = [a for a in ids if a in eligible_by_scene[sid]]

        def encode(p, reference):
            nonlocal encoding_calls
            if route_aware:
                result = encoder.encode(p, reference_enu=reference, resample_from_1hz=False)
            else:
                result = encoder.encode(p, resample_from_1hz=False)
            encoding_calls += 1
            return result["embedding"]

        if args.reference == "corridor":
            assigned = [assign_corridor(p) for p in baseline]
            references = [row[0] for row in assigned]
            reference_info = [row[1] for row in assigned]
        elif args.reference == "official":
            assigned = [assign_official(p, force=ids[i] in eligible) for i, p in enumerate(baseline)]
            references = [row[0] for row in assigned]
            reference_info = [row[1] for row in assigned]
        else:
            references = [p if args.reference == "baseline" else baseline[(i + 1) % len(baseline)]
                          for i, p in enumerate(baseline)]
            reference_info = [dict(corridor=None, reason=args.reference, angle_deg=None) for _ in baseline]
        base = np.asarray([encode(p, reference) for p, reference in zip(baseline, references)])
        injected = {}
        for a in eligible:
            position = ids.index(a)
            injected[a] = {
                "left": encode(saved[a + "_left"], references[position]),
                "right": encode(saved[a + "_right"], references[position]),
            }
        positive = pdist(base)
        positive = positive[positive > 0]
        radii = np.geomspace(positive.min(), positive.max(), 64)

        def estimate(embedding):
            return estimate_complexity(embedding, config=cfg, radii=radii, scene_id=sid).to_dict()

        baseline_D = estimate(base)
        frozen = assignment_by_scene[sid]
        for repeat in frozen["repeats"]:
            current = base.copy()
            curve = [dict(vectoring_aircraft=0, **baseline_D)]
            selected = [a for a in (x["icao24"] for x in repeat["assignments"]) if a in eligible]
            side = {x["icao24"]: x["side"] for x in repeat["assignments"]}
            for dose, a in enumerate(selected, 1):
                current[ids.index(a)] = injected[a]["left" if side[a] < 0 else "right"]
                curve.append(dict(vectoring_aircraft=dose, **estimate(current)))
            trials.append(dict(scene_id=sid, replicate=repeat["replicate"], seed=repeat["seed"],
                               n_aircraft=len(ids), n_vectoring_eligible=len(eligible),
                               assignments=[dict(icao24=a, side=side[a], baseline_index=ids.index(a)) for a in selected],
                               dose_curve=curve))
        diagnostics.append(dict(scene=sid, n_aircraft=len(ids), eligible=len(eligible),
                                baseline_status=baseline_D["status"], baseline_reason=baseline_D["reason"],
                                baseline_D=baseline_D["dimension"], radii=radii.tolist(),
                                threshold=args.min_r2,
                                reference=dict(mode=args.reference,
                                               assigned=sum(x["corridor"] is not None for x in reference_info),
                                               fallback=sum(x["corridor"] is None for x in reference_info),
                                               median_angle_deg=float(np.median([x["angle_deg"] for x in reference_info
                                                                                if x["angle_deg"] is not None])) if any(
                                                   x["angle_deg"] is not None for x in reference_info) else None,
                                               aircraft=reference_info)))
        np.savez_compressed(out / f"{sid}-embeddings.npz", baseline=base, ids=np.asarray(ids),
                            **{f"{a}_{side}": value for a, values in injected.items() for side, value in values.items()})
        print(json.dumps(diagnostics[-1], default=str), flush=True)

    experiment = {"qc500_safe": {"vectoring": {"kind": "vectoring", "variant": args.label, "scenes": trials}}}
    write(out / "experiment-results.json", experiment)
    summary, selection = summarize(trials, "vectoring", truncate=False)
    write(out / "summary.json", summary)
    write(out / "scene-diagnostics.json", diagnostics)

    thresholds = {}
    for threshold in (0.98, 0.96, 0.95, 0.94, 0.90):
        curves = []
        for trial in trials:
            good = [d for d in trial["dose_curve"] if d.get("r_squared") is not None
                    and d["r_squared"] >= threshold and (d.get("fit_slope") or 0) > 0]
            from scipy.stats import spearmanr
            rho = None
            if len(good) >= 5 and len({d["fit_slope"] for d in good}) > 1:
                rho = float(spearmanr([d["vectoring_aircraft"] for d in good], [d["fit_slope"] for d in good]).statistic)
            curves.append(dict(scene=trial["scene_id"], replicate=trial["replicate"], valid=len(good),
                               total=len(trial["dose_curve"]), rho=rho))
        values = [c["rho"] for c in curves if c["rho"] is not None]
        thresholds[str(threshold)] = dict(estimable_curves=len(values), total_curves=len(curves),
                                          median_rho=float(np.median(values)) if values else None,
                                          positive=int(sum(v > 0 for v in values)), curves=curves)
    write(out / "threshold-sensitivity.json", thresholds)

    manifest = dict(state="complete", label=args.label, checkpoint=str(args.checkpoint), checkpoint_sha256=sha(args.checkpoint),
                    route_aware=route_aware, reference=args.reference, peak_m=generation["peak_m"],
                    population=generation["totals"], config=cfg.__dict__, device=str(device),
                    torch=torch.__version__, numpy=np.__version__, encoding_calls=encoding_calls,
                    assignment_policy="frozen four-scene orders, filtered to candidates that pass both sides at 15 km",
                    interpretation="conditional synthetic perturbation; within-scene repeats are not independent scenes")
    write(out / "run-manifest.json", manifest)
    print("EVALUATION COMPLETE " + json.dumps(summary["all"]["full"]), flush=True)


if __name__ == "__main__":
    main()
