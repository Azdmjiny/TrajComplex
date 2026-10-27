"""Compare smooth and segmented 15 km injections with the original 9-feature Encoder."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "vectoring-15km-star-2026-10-24" / "results"
ARMS = [
    ("smooth", "Smooth 15 km", "#4C72B0", "old-15km-r094"),
    ("segmented", "Segmented 15 km", "#DD8452", "old-15km-segmented-r094"),
]
SCENES = ["2026-09-15T07Z", "2026-09-19T07Z", "2026-09-27T05Z"]


def read(name):
    return json.loads((RESULTS / name / "summary.json").read_text(encoding="utf8"))


def main():
    summaries = {key: read(folder) for key, _, _, folder in ARMS}
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    ax = axes[0]
    medians = [summaries[key]["all"]["full"]["median"] for key, _, _, _ in ARMS]
    positive = [f"{summaries[key]['all']['full']['positive']}/{summaries[key]['all']['full']['n']}" for key, _, _, _ in ARMS]
    ax.bar(range(len(ARMS)), medians, color=[color for _, _, color, _ in ARMS])
    for i, (value, text) in enumerate(zip(medians, positive)):
        ax.text(i, value + .02, f"{value:.3f}\n({text} pos)", ha="center", va="bottom", fontsize=9)
    ax.axhline(0, color="black", lw=.7); ax.set_xticks(range(len(ARMS)))
    ax.set_xticklabels(["smooth", "segmented"]); ax.set_ylim(0, 1.18)
    ax.set_ylabel("median Spearman rho"); ax.set_title("(a) All estimable dose curves")

    ax = axes[1]
    x = np.arange(len(SCENES)); width = .34
    for offset, (key, label, color, _) in zip((-width / 2, width / 2), ARMS):
        values = [summaries[key]["scenes"][i]["full"]["median"] for i in range(4)
                  if summaries[key]["scenes"][i]["scene_id"] in SCENES]
        ax.bar(x + offset, [np.nan if v is None else v for v in values], width, color=color, label=label)
    ax.axhline(0, color="black", lw=.7); ax.set_xticks(x); ax.set_xticklabels([s[5:16] for s in SCENES], fontsize=9)
    ax.set_ylabel("median rho"); ax.set_title("(b) Scene-level association"); ax.legend(fontsize=8)

    ax = axes[2]
    # Example dose response, scene 2026-09-19, first order.
    for key, label, color, folder in ARMS:
        scenes = json.loads((RESULTS / folder / "experiment-results.json").read_text(encoding="utf8"))["qc500_safe"]["vectoring"]["scenes"]
        trial = next(t for t in scenes if t["scene_id"] == "2026-09-19T07Z" and t["replicate"] == 1)
        values = []
        for d in trial["dose_curve"]:
            ok = d.get("r_squared") is not None and d["r_squared"] >= 0.94 and (d.get("fit_slope") or 0) > 0
            values.append(d["fit_slope"] if ok else np.nan)
        xf = np.arange(len(values)) / max(len(values) - 1, 1)
        ax.plot(xf, values, marker="o", ms=3, color=color, label=label)
    ax.set_xlabel("injected fraction"); ax.set_ylabel("D")
    ax.set_title("(c) Dose response, 2026-09-19 order 1"); ax.legend(fontsize=8)
    fig.tight_layout()
    (HERE / "figures").mkdir(exist_ok=True)
    fig.savefig(HERE / "figures" / "smooth-vs-segmented.png", dpi=200)
    fig.savefig(HERE / "figures" / "smooth-vs-segmented.svg")
    (HERE / "comparison.json").write_text(json.dumps({key: summaries[key]["all"]["full"] for key, _, _, _ in ARMS}, indent=2), encoding="utf8")
    print(json.dumps({key: summaries[key]["all"]["full"] for key, _, _, _ in ARMS}, indent=2))


if __name__ == "__main__":
    main()
