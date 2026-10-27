"""Official STAR coverage and Encoder-reference comparison.

The six WSSS RWY20 RNAV STARs are transcribed from CAAS AIP charts. For every
evaluation arrival we report the median cross-track distance to its nearest
published STAR. The Encoder arms are then compared: baseline self-reference,
official STAR (nearest, no fallback), and official STAR with a 10 km fallback.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from official_routes import routes

HERE = Path(__file__).resolve().parent
B = HERE.parent
POP = B / "vectoring-15km-star-2026-10-24" / "population-15km"
RESULTS = B / "vectoring-15km-star-2026-10-24" / "results"


def segment_distance(points, route):
    a, b = route[:-1], route[1:]
    ab = b - a
    den = np.sum(ab * ab, axis=1)
    u = np.clip(np.einsum("nmd,md->nm", points[:, None, :] - a[None], ab) / den, 0, 1)
    nearest = a[None] + u[..., None] * ab[None]
    return np.linalg.norm(points[:, None, :] - nearest, axis=2).min(axis=1)


def main():
    routes_ = routes()
    coverage = {"routes": {name: route.tolist() for name, route in routes_.items()}, "scenes": []}
    for path in sorted(POP.glob("*-population.npz")):
        scene = path.name.replace("-population.npz", "")
        data = np.load(path)
        records = json.loads(path.with_name(path.name.replace("-population.npz", "-records.json")).read_text(encoding="utf8"))
        rows = []
        for record in records:
            p = data[record["icao24"] + "_baseline"]
            r = np.linalg.norm(p[:, :2], axis=1)
            if r[0] - r[-1] <= 3000 or p[0, 2] - p[-1, 2] <= 300:
                continue
            distances = {name: float(np.median(segment_distance(p[:, :2], route))) for name, route in routes_.items()}
            best = min(distances, key=distances.get)
            rows.append(dict(icao24=record["icao24"], injectable=bool(record["injectable"]),
                             star=best, residual_m=distances[best],
                             residual_km=round(distances[best] / 1000, 2)))
        coverage["scenes"].append(dict(scene=scene, arrivals=len(rows), rows=rows))
        print(json.dumps(dict(scene=scene, arrivals=len(rows),
                              under_2km=sum(r["residual_m"] <= 2000 for r in rows),
                              under_5km=sum(r["residual_m"] <= 5000 for r in rows),
                              median_km=round(float(np.median([r["residual_m"] for r in rows])) / 1000, 2))), flush=True)
    (HERE / "coverage.json").write_text(json.dumps(coverage, indent=2), encoding="utf8")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.5), gridspec_kw={"width_ratios": [1.35, 1]})
    ax = axes[0]
    for name, route in routes_.items():
        ax.plot(route[:, 0] / 1000, route[:, 1] / 1000, color="0.55", lw=2.2, marker="o", ms=3, label=name)
    for scene in coverage["scenes"]:
        data = np.load(POP / f"{scene['scene']}-population.npz")
        for row in scene["rows"]:
            p = data[row["icao24"] + "_baseline"]
            color = "#2E8B57" if row["residual_m"] <= 2000 else "#D79823" if row["residual_m"] <= 5000 else "#C0392B"
            ax.plot(p[:, 0] / 1000, p[:, 1] / 1000, color=color, lw=1.0, alpha=.6)
    ax.scatter([0], [0], marker="*", s=180, color="black", label="airport")
    ax.set_aspect("equal"); ax.grid(alpha=.25); ax.set_xlim(-110, 110); ax.set_ylim(-110, 110)
    ax.set_xlabel("east (km)"); ax.set_ylabel("north (km)")
    ax.set_title("(a) Evaluation arrivals vs official RWY20 STARs\n(green ≤2 km, orange 2–5 km, red >5 km)")
    ax.legend(fontsize=7, loc="upper right")
    ax = axes[1]
    scenes = [s["scene"][5:16] for s in coverage["scenes"]]
    near = [sum(r["residual_m"] <= 2000 for r in s["rows"]) for s in coverage["scenes"]]
    mid = [sum(2000 < r["residual_m"] <= 5000 for r in s["rows"]) for s in coverage["scenes"]]
    far = [sum(r["residual_m"] > 5000 for r in s["rows"]) for s in coverage["scenes"]]
    x = np.arange(len(scenes))
    ax.bar(x, near, color="#2E8B57", label="≤2 km")
    ax.bar(x, mid, bottom=near, color="#D79823", label="2–5 km")
    ax.bar(x, far, bottom=np.array(near) + np.array(mid), color="#C0392B", label=">5 km")
    ax.set_xticks(x); ax.set_xticklabels(scenes, fontsize=8); ax.set_ylabel("arrival tracks")
    ax.set_title("(b) Distance from the nearest published STAR"); ax.legend(fontsize=8)
    fig.tight_layout()
    (HERE / "figures").mkdir(exist_ok=True)
    fig.savefig(HERE / "figures" / "official-coverage.png", dpi=200)
    fig.savefig(HERE / "figures" / "official-coverage.svg")
    print("SAVED", HERE, flush=True)


if __name__ == "__main__":
    main()
