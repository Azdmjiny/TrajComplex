"""Compare Changi hourly D rankings against the 16-D epoch-60 reference."""

import argparse
from pathlib import Path
from typing import NamedTuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, rankdata

from eval._hourly import HourlyEncoder, configure_inference, load_plan, score_month

REFERENCE = "pooled_d16"
COMPARISONS = {
    "pooled_d8": (8, "8 dimensions"), "pooled_d32": (32, "32 dimensions"),
    "2025-03_d16": (16, "March 2025"), "2025-04_d16": (16, "April 2025"),
    "2025-05_d16": (16, "May 2025"),
}
COLORS = ("#a6c0d2", "#d99a84")


class Panel(NamedTuple):
    label: str
    auc: float
    n: int
    low: np.ndarray
    high: np.ndarray


def comparison(label, scores, low, high):
    ranks = rankdata(scores, method="average") / (len(scores) + 1)
    a, b = ranks[low], ranks[high]
    auc = mannwhitneyu(b, a).statistic / (len(a) * len(b))
    return Panel(label, auc, len(scores), a, b)


def compare_hourly(scores):
    columns = [REFERENCE, *COMPARISONS]
    common = scores.loc[np.isfinite(scores[columns]).all(axis=1)].copy()
    if len(common) < 4:
        raise ValueError("Need at least four jointly computable hourly scenes")
    q25, q75 = common[REFERENCE].quantile([.25, .75])
    if q25 >= q75:
        raise ValueError("The reference quartiles do not separate")
    low, high = common[REFERENCE] <= q25, common[REFERENCE] >= q75
    common["reference_group"] = np.select([low, high], ["low", "high"], default="middle")
    panels = [comparison(label, common[key], low, high)
              for key, (_, label) in COMPARISONS.items()]
    return common, panels


def plot(panels, output):
    fig, axes = plt.subplots(1, len(panels), figsize=(max(6, len(panels) * 1.25), 2.8), sharey=True)
    for ax, panel in zip(axes, panels):
        for x, values, color in zip((1, 2), (panel.low, panel.high), COLORS):
            if np.ptp(values):
                body = ax.violinplot(values, positions=[x], widths=.75, showextrema=False)["bodies"][0]
                body.set(facecolor=color, edgecolor="#27363d", alpha=1)
            else:
                ax.hlines(values[0], x - .2, x + .2, color=color, lw=2)
            q25, median, q75 = np.quantile(values, [.25, .5, .75])
            ax.vlines(x, q25, q75, color="#27363d", lw=2)
            ax.scatter(x, median, color="white", edgecolor="#27363d", s=13, zorder=4)
        ax.set(title=f"{panel.label}\nAUC {panel.auc:.3f}", ylim=(0, 1), xticks=[])
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=.25)
    axes[0].set_ylabel("Comparison $D$ percentile")
    fig.legend([Patch(facecolor=color) for color in COLORS], ["Reference low", "Reference high"],
               loc="lower center", ncols=2, frameon=False)
    fig.tight_layout(rect=(0, .12, 1, 1))
    fig.savefig(output, dpi=300)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True, help="Prepared WSSS directory")
    parser.add_argument("--baseline", type=Path, required=True, help="Original 16-D epoch-60 checkpoint")
    parser.add_argument("--variants", type=Path, required=True, help="Directory of the five variant runs")
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("--output must be a new directory")

    configure_inference()
    plan = load_plan(args.prepared, "WSSS")
    scores = plan[["hour_utc", "hour_local"]].copy().reset_index(drop=True)
    checkpoints = {REFERENCE: (16, args.baseline)}
    checkpoints.update((name, (dimension, args.variants / name / "epoch_60.pt"))
                       for name, (dimension, _) in COMPARISONS.items())
    for name, (dimension, checkpoint) in checkpoints.items():
        encoder = HourlyEncoder(checkpoint, "WSSS", dimension, args.device)
        frame = score_month(args.prepared, plan, encoder)
        scores["N"] = frame.N
        scores[name] = frame.dimension
        del encoder
        print(f"Scored {name}: {len(frame)} hours", flush=True)

    common, panels = compare_hourly(scores)
    args.output.mkdir(parents=True)
    scores.to_csv(args.output / "hourly_D.csv", index=False)
    common.to_csv(args.output / "reference_groups.csv", index=False)
    pd.DataFrame([
        dict(comparison=panel.label, auc=panel.auc, common_hours=panel.n,
             low_n=len(panel.low), high_n=len(panel.high)) for panel in panels
    ]).to_csv(args.output / "comparison.csv", index=False)
    plot(panels, args.output / "comparison.png")


if __name__ == "__main__":
    main()
