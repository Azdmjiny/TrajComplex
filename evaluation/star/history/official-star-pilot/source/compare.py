"""Compare baseline self-reference with two official-STAR assignment policies."""
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
    ("baseline", "Baseline self-reference", "#4C72B0", "star-15km-r094"),
    ("officialAll", "Official STAR, forced on all candidates", "#C44E52", "star-official-all-15km-r094"),
]
SCENES = ["2026-09-15T07Z", "2026-09-19T07Z", "2026-09-27T05Z"]


def read(name):
    return json.loads((RESULTS / name / "summary.json").read_text(encoding="utf8"))


def main():
    summaries = {key: read(folder) for key, _, _, folder in ARMS}
    coverage = json.loads((HERE / "coverage.json").read_text(encoding="utf8"))

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    ax = axes[0]
    labels = [label for _, label, _, _ in ARMS]
    medians = [summaries[key]["all"]["full"]["median"] for key, _, _, _ in ARMS]
    positive = [f"{summaries[key]['all']['full']['positive']}/{summaries[key]['all']['full']['n']}" for key, _, _, _ in ARMS]
    bars = ax.bar(range(len(ARMS)), medians, color=[color for _, _, color, _ in ARMS])
    for i, (value, text) in enumerate(zip(medians, positive)):
        ax.text(i, value + .02 if value >= 0 else value - .05, f"{value:.3f}\n({text} pos)",
                ha="center", va="bottom" if value >= 0 else "top", fontsize=9)
    ax.axhline(0, color="black", lw=.7); ax.set_xticks(range(len(ARMS)))
    ax.set_xticklabels(["baseline", "official\nforced"], fontsize=9)
    ax.set_ylim(0, 1.18)
    ax.set_ylabel("median Spearman rho"); ax.set_title("(a) All estimable dose curves")

    ax = axes[1]
    x = np.arange(len(SCENES)); width = .32
    offsets = np.linspace(-width, width, len(ARMS)) if len(ARMS) > 1 else [0.0]
    for offset, (key, label, color, _) in zip(offsets, ARMS):
        values = [summaries[key]["scenes"][i]["full"]["median"] for i in range(4)
                  if summaries[key]["scenes"][i]["scene_id"] in SCENES]
        ax.bar(x + offset, [np.nan if v is None else v for v in values], width, color=color, label=label)
    ax.axhline(0, color="black", lw=.7); ax.set_xticks(x); ax.set_xticklabels([s[5:16] for s in SCENES], fontsize=9)
    ax.set_ylabel("median rho"); ax.set_title("(b) Scene-level association"); ax.legend(fontsize=7)

    ax = axes[2]
    from official_routes import routes as official_routes
    routes = official_routes()

    def distance(p):
        best = np.inf
        for route in routes.values():
            a, b = route[:-1], route[1:]
            ab = b - a
            u = np.clip(np.einsum("nmd,md->nm", p[:, None, :2] - a[None], ab) / np.sum(ab * ab, axis=1), 0, 1)
            nearest = a[None] + u[..., None] * ab[None]
            best = min(best, float(np.median(np.linalg.norm(p[:, None, :2] - nearest, axis=2).min(axis=1))))
        return best / 1000

    candidates = []
    for path in sorted((HERE.parent / "vectoring-15km-star-2026-10-24" / "population-15km").glob("*-population.npz")):
        data = np.load(path)
        records = json.loads(path.with_name(path.name.replace("-population.npz", "-records.json")).read_text(encoding="utf8"))
        for record in records:
            if record["injectable"]:
                candidates.append((record["icao24"], distance(data[record["icao24"] + "_baseline"])))
    candidates.sort(key=lambda item: item[1])
    ax.bar(range(len(candidates)), [v for _, v in candidates], color="#C44E52")
    ax.axhline(2, color="#2E8B57", ls="--", lw=1, label="2 km")
    ax.axhline(5, color="#D79823", ls="--", lw=1, label="5 km")
    ax.set_xticks(range(len(candidates))); ax.set_xticklabels([c[0] for c in candidates], rotation=90, fontsize=7)
    ax.set_ylabel("distance to nearest official STAR (km)")
    ax.set_title("(c) Injectable candidates' official-STAR offset"); ax.legend(fontsize=8)
    fig.tight_layout()
    (HERE / "figures").mkdir(exist_ok=True)
    fig.savefig(HERE / "figures" / "official-vs-baseline.png", dpi=200)
    fig.savefig(HERE / "figures" / "official-vs-baseline.svg")

    (HERE / "comparison.json").write_text(json.dumps({key: summaries[key]["all"]["full"] for key, _, _, _ in ARMS}, indent=2), encoding="utf8")
    print(json.dumps({key: summaries[key]["all"]["full"] for key, _, _, _ in ARMS}, indent=2))


if __name__ == "__main__":
    main()
