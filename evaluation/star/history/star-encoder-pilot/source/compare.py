"""Compare the historical 5 km arm with the 15 km old/STAR arms.

Every arm is recomputed from its saved D diagnostics; no embedding or D is
re-run here. The only parameter varied is the R-squared acceptance gate.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.distance import pdist
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
B = HERE.parent
ARMS = [
    dict(key="old-5km", label="5 km, 9-feat", path=B / "four-scene-vectoring-evaluation" / "results"),
    dict(key="old-15km", label="15 km, 9-feat", path=HERE / "results" / "old-15km-r094"),
    dict(key="star-15km", label="15 km, 15-feat STAR", path=HERE / "results" / "star-15km-r094"),
]
THRESHOLDS = (0.98, 0.96, 0.95, 0.94, 0.90)
SCENES = ["2026-09-14T06Z", "2026-09-15T07Z", "2026-09-19T07Z", "2026-09-27T05Z"]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def trials_of(arm):
    data = read(arm["path"] / "experiment-results.json")
    return next(iter(data.values()))["vectoring"]["scenes"]


def curve(trial, threshold):
    good = [d for d in trial["dose_curve"]
            if d.get("r_squared") is not None and d["r_squared"] >= threshold
            and (d.get("fit_slope") or 0) > 0]
    if len(good) < 5 or len({d["fit_slope"] for d in good}) < 2:
        return None
    return float(spearmanr([d["vectoring_aircraft"] for d in good], [d["fit_slope"] for d in good]).statistic)


def metrics(trials, threshold):
    rows = []
    for trial in trials:
        rows.append(dict(scene=trial["scene_id"], replicate=trial["replicate"],
                         rho=curve(trial, threshold),
                         accepted=sum(1 for d in trial["dose_curve"]
                                      if d.get("r_squared") is not None and d["r_squared"] >= threshold
                                      and (d.get("fit_slope") or 0) > 0),
                         total=len(trial["dose_curve"])))
    values = [r["rho"] for r in rows if r["rho"] is not None]
    scenes = {}
    for scene in SCENES:
        scene_values = [r["rho"] for r in rows if r["scene"] == scene and r["rho"] is not None]
        scenes[scene] = float(np.median(scene_values)) if scene_values else None
    hour = [v for v in scenes.values() if v is not None]
    return dict(curves=len(values), total_curves=len(rows), median=float(np.median(values)) if values else None,
                positive=int(sum(v > 0 for v in values)), scenes=scenes,
                hour_median=float(np.median(hour)) if hour else None,
                accepted=sum(r["accepted"] for r in rows), doses=sum(r["total"] for r in rows), rows=rows)


def displacement(arm):
    ratios = {}
    for path in sorted(arm["path"].glob("*-embeddings.npz")):
        scene = path.name.replace("-embeddings.npz", "")
        with np.load(path) as z:
            base = z["baseline"]
            ids = [str(x) for x in z["ids"]] if "ids" in z.files else None
            distances = []
            if ids is not None:
                for i, aircraft in enumerate(ids):
                    for side in ("left", "right"):
                        key = f"{aircraft}_{side}"
                        if key in z.files:
                            distance = float(np.linalg.norm(z[key] - base[i]))
                            if distance > 1e-9:
                                distances.append(distance)
            else:
                left, right = z["left"], z["right"]
                for i in range(len(base)):
                    for array in (left, right):
                        distance = float(np.linalg.norm(array[i] - base[i]))
                        if distance > 1e-9:
                            distances.append(distance)
        cloud = pdist(base)
        cloud = cloud[cloud > 0]
        ratios[scene] = dict(displacement=float(np.median(distances)) if distances else None,
                             cloud=float(np.median(cloud)), ratio=float(np.median(distances) / np.median(cloud)) if distances else None)
    return ratios


def main():
    results = {}
    for arm in ARMS:
        if not (arm["path"] / "experiment-results.json").exists():
            print("missing", arm["path"])
            continue
        trials = trials_of(arm)
        results[arm["key"]] = dict(arm=arm, thresholds={str(t): metrics(trials, t) for t in THRESHOLDS},
                                   displacement=displacement(arm))
        print(arm["key"], "loaded", len(trials))

    # Markdown table at 0.94 (0.98 for the historical arm in the original report).
    lines = ["| arm | doses accepted / total | curves | positive | median rho | hour-level median |",
             "|---|---:|---:|---:|---:|---:|"]
    for key in ("old-5km", "old-15km", "star-15km"):
        if key not in results:
            continue
        m = results[key]["thresholds"]["0.94"]
        lines.append(f"| {results[key]['arm']['label']} | {m['accepted']}/{m['doses']} | {m['curves']}/{m['total_curves']} | "
                     f"{m['positive']}/{m['curves']} | {m['median']:.3f} | {m['hour_median']:.3f} |")
    (HERE / "comparison-table.md").write_text("\n".join(lines) + "\n", encoding="utf8")

    scene_lines = ["| scene | 5 km, 9-feat | 15 km, 9-feat | 15 km, 15-feat STAR |",
                   "|---|---:|---:|---:|"]
    for scene in SCENES:
        cells = []
        for key in ("old-5km", "old-15km", "star-15km"):
            value = results.get(key, {}).get("thresholds", {}).get("0.94", {}).get("scenes", {}).get(scene)
            cells.append("n/a" if value is None else f"{value:.3f}")
        scene_lines.append(f"| {scene} | " + " | ".join(cells) + " |")
    (HERE / "comparison-scenes.md").write_text("\n".join(scene_lines) + "\n", encoding="utf8")

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    colors = {"old-5km": "#4C72B0", "old-15km": "#DD8452", "star-15km": "#55A868"}
    # (a) median rho by scene
    ax = axes[0, 0]
    x = np.arange(len(SCENES)); width = 0.26
    for offset, key in zip((-width, 0, width), ("old-5km", "old-15km", "star-15km")):
        if key not in results:
            continue
        values = [results[key]["thresholds"]["0.94"]["scenes"][scene] for scene in SCENES]
        ax.bar(x + offset, [np.nan if v is None else v for v in values], width, label=results[key]["arm"]["label"], color=colors[key])
    ax.axhline(0, color="black", lw=.7); ax.set_xticks(x); ax.set_xticklabels([s[5:16] for s in SCENES], rotation=0, fontsize=8)
    ax.set_ylabel("median Spearman rho"); ax.set_title("(a) Dose-D association by scene (R²≥0.94)"); ax.legend(fontsize=7)
    # (b) displacement ratio
    ax = axes[0, 1]
    for offset, key in zip((-width, 0, width), ("old-5km", "old-15km", "star-15km")):
        if key not in results:
            continue
        values = [results[key]["displacement"].get(scene, {}).get("ratio") for scene in SCENES]
        ax.bar(x + offset, [np.nan if v is None else 100 * v for v in values], width, color=colors[key], label=results[key]["arm"]["label"])
    ax.set_xticks(x); ax.set_xticklabels([s[5:16] for s in SCENES], fontsize=8)
    ax.set_ylabel("injected displacement / baseline spacing (%)"); ax.set_title("(b) Encoder sensitivity to the injection"); ax.legend(fontsize=7)
    # (c) example dose response
    ax = axes[1, 0]
    for key in ("old-5km", "old-15km", "star-15km"):
        if key not in results:
            continue
        trials = [t for t in trials_of(results[key]["arm"]) if t["scene_id"] == "2026-09-15T07Z"]
        curves = []
        for trial in trials:
            curves.append([d["fit_slope"] if (d.get("r_squared") or 0) >= 0.94 and (d.get("fit_slope") or 0) > 0 else np.nan
                           for d in trial["dose_curve"]])
        mean = np.nanmean(np.asarray(curves), axis=0)
        fraction = np.arange(len(mean)) / max(len(mean) - 1, 1)
        ax.plot(fraction, mean, marker="o", ms=3, label=results[key]["arm"]["label"], color=colors[key])
    ax.set_xlabel("injected fraction of eligible aircraft"); ax.set_ylabel("mean D")
    ax.set_title("(c) Dose response, 2026-09-15 15:00"); ax.legend(fontsize=7)
    # (d) R2 acceptance
    ax = axes[1, 1]
    for key in ("old-5km", "old-15km", "star-15km"):
        if key not in results:
            continue
        values = [results[key]["thresholds"][str(t)]["accepted"] / results[key]["thresholds"][str(t)]["doses"] for t in THRESHOLDS]
        ax.plot(THRESHOLDS, values, marker="o", label=results[key]["arm"]["label"], color=colors[key])
    ax.set_xlabel("minimum R²"); ax.set_ylabel("accepted dose fraction"); ax.set_title("(d) D fit gate sensitivity")
    ax.invert_xaxis(); ax.legend(fontsize=7)
    fig.tight_layout()
    (HERE / "figures").mkdir(exist_ok=True)
    fig.savefig(HERE / "figures" / "vectoring-15km-comparison.png", dpi=200)
    fig.savefig(HERE / "figures" / "vectoring-15km-comparison.svg")
    (HERE / "comparison.json").write_text(json.dumps({k: dict(label=results[k]["arm"]["label"],
                                                              displacement=results[k]["displacement"],
                                                              thresholds=results[k]["thresholds"]) for k in results},
                                                     indent=2, allow_nan=False), encoding="utf8")
    print((HERE / "comparison-table.md").read_text(encoding="utf8"))
    print((HERE / "comparison-scenes.md").read_text(encoding="utf8"))


if __name__ == "__main__":
    main()
