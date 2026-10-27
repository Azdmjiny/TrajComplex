"""Regenerate the frozen four-scene screening population at a 15 km peak.

The five-kilometre routes were already generated and frozen by the approved
screen. This driver reconstructs the identical continuous reference from the
saved fit knots (verified by exactly reproducing every saved 5 km route), then
asks the same solver for a 15 km peak. Baselines, candidates, quality checks,
scene membership and left/right assignment are unchanged. No candidate is
added, removed or shrunk to make it pass.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.interpolate import make_interp_spline

B = Path(__file__).resolve().parents[1]
SCREEN = B / "four-scene-vectoring-screen" / "screening"
CODE = B / "vectoring-direction-repair" / "code"
OUT = Path(__file__).resolve().parent / "population-15km"
sys.path[:0] = [str(B / "evaluation-python-deps"), str(CODE)]
import vectoring_path as path  # noqa: E402
import vectoring_reference as reference  # noqa: E402

PEAK = 15_000.0
OLD_PEAK = 5_000.0


def sha(path_):
    return hashlib.sha256(Path(path_).read_bytes()).hexdigest()


def rebuild(reference_file):
    saved = np.load(reference_file)
    times = saved["times"]
    n = len(times)
    zero = np.zeros(n)
    fit = reference.WholeTrackFit(
        float(saved["epoch"]), times, saved["raw_xy"], saved["fitted_xy"],
        saved["origin"], saved["radii"], None, {},
    )
    # Identical natural quintic cardinal basis used by fit_track().
    fit.mapping = make_interp_spline(
        times, np.eye(n), k=5,
        bc_type=([(3, zero), (4, zero)], [(3, zero), (4, zero)]),
    )
    return fit, saved


def main():
    scenes = json.loads((SCREEN / "manifest.json").read_text(encoding="utf8"))["scenes"]
    references = {p.stem: p for p in (SCREEN / "references").glob("*.npz")}
    OUT.mkdir(parents=True, exist_ok=False)
    summary = {"peak_m": PEAK, "old_peak_m": OLD_PEAK, "scenes": [], "reproduction_max_abs_m": 0.0}
    all_rows = []
    for scene in scenes:
        population = np.load(SCREEN / f"{scene}-population.npz")
        records = {r["icao24"]: r for r in json.loads((SCREEN / f"{scene}-records.json").read_text(encoding="utf8"))}
        arrays = {}
        rows = []
        for icao, record in sorted(records.items()):
            baseline = population[icao + "_baseline"]
            arrays[icao + "_baseline"] = baseline
            if not record["injectable"]:
                rows.append(dict(record, new_injectable=False, new_rejection_reasons=["not_an_approved_candidate"]))
                continue
            reference_file = references[f"{scene}-{icao}"]
            fit, saved = rebuild(reference_file)
            start = (len(baseline) - 60) // 2
            try:
                old = 0.0
                old_ref = reference.maneuver_reference(fit, saved["grid"], start)
                path.PEAK = OLD_PEAK
                for side, label in ((-1, "left"), (1, "right")):
                    old_route = path.generate(old_ref, side, {}, sample_s=10)
                    old = max(old, float(np.abs(old_route - population[f"{icao}_{label}"][start:start + 61, :2]).max()))
                summary["reproduction_max_abs_m"] = max(summary["reproduction_max_abs_m"], old)
                path.PEAK = PEAK
                new_ref = reference.maneuver_reference(fit, saved["grid"], start)
                injected = {}
                reasons = []
                for side, label in ((-1, "left"), (1, "right")):
                    try:
                        injected[label] = path.generate(new_ref, side, {}, sample_s=10)
                    except Exception as exc:  # rejection is data, not a crash
                        reasons.append(f"side_{side}:{exc}")
                ok = len(injected) == 2
                if ok:
                    for label, xy in injected.items():
                        q = baseline.copy()
                        q[start:start + 61, :2] = xy
                        arrays[f"{icao}_{label}"] = q
                rows.append(dict(record, new_injectable=ok, new_rejection_reasons=sorted(reasons)))
            except Exception as exc:
                rows.append(dict(record, new_injectable=False, new_rejection_reasons=[f"reference_rebuild:{exc}"]))
        np.savez_compressed(OUT / f"{scene}-population.npz", **arrays)
        (OUT / f"{scene}-records.json").write_text(json.dumps(rows, indent=2), encoding="utf8")
        injectable = [r["icao24"] for r in rows if r["new_injectable"]]
        summary["scenes"].append(dict(scene=scene, background=len(rows), injectable_before=len([r for r in rows if r["injectable"]]),
                                      injectable_after=len(injectable), injectable=injectable,
                                      rejection_counts=dict(Counter(reason for r in rows for reason in r["new_rejection_reasons"]
                                                                    if not r["new_injectable"]))))
        all_rows.extend(rows)
        print(json.dumps(summary["scenes"][-1]), flush=True)
    summary["totals"] = dict(background=len(all_rows), injectable_before=sum(r["injectable"] for r in all_rows),
                             injectable_after=sum(r["new_injectable"] for r in all_rows))
    summary["source_sha256"] = {str(p): sha(p) for p in [SCREEN / "manifest.json", *sorted(references.values())]}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf8")
    print("GENERATION COMPLETE " + json.dumps(summary["totals"]), flush=True)


if __name__ == "__main__":
    main()
