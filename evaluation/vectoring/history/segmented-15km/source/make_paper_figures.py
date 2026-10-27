"""Recreate the paper's positive dose-response figure from stored results.

Reads only evaluation/runs/segmented-15km/results/*/summary.json and
experiment-results.json. No encoder calls, no new D estimates.
"""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

repo = Path(__file__).resolve().parents[4]
base = repo / "evaluation/runs/segmented-15km/results"
seg = json.load(open(base / "segmented/summary.json"))
smo = json.load(open(base / "smooth-control/summary.json"))
seg_exp = json.load(open(base / "segmented/experiment-results.json"))["qc500_safe"]["vectoring"]["scenes"]

scenes = [
    ("2026-09-15T07Z", "2026-09-15 15:00 UTC+08"),
    ("2026-09-19T07Z", "2026-09-19 15:00 UTC+08"),
    ("2026-09-27T05Z", "2026-09-27 13:00 UTC+08"),
]
colors = {"seg": "#D97706", "smo": "#2563EB", "thin": "#9CA3AF"}
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10.5,
    "axes.labelsize": 9.5, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
    "axes.spines.top": False, "axes.spines.right": False,
})
fig, axes = plt.subplots(2, 2, figsize=(11.6, 8.2))
axes = axes.ravel()
labels = ["A", "B", "C", "D"]
for ax, (sid, title), lab in zip(axes[:3], scenes, labels):
    rows = [s for s in seg_exp if s["scene_id"] == sid]
    bydose = {}
    for s in rows:
        for p in s["dose_curve"]:
            if p["status"] == "ok" and p["dimension"] is not None:
                bydose.setdefault(p["vectoring_aircraft"], []).append(p["dimension"])
    doses = sorted(bydose)
    med = [float(np.median(bydose[d])) for d in doses]
    for s in rows:
        pts = [(p["vectoring_aircraft"], p["dimension"]) for p in s["dose_curve"]
               if p["status"] == "ok" and p["dimension"] is not None]
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts],
                    color=colors["thin"], lw=1.0, alpha=.55, zorder=1)
    ax.plot(doses, med, color=colors["seg"], lw=2.8, marker="o", ms=5,
            zorder=3, label="Median of 5 orders")
    sc = next(x for x in seg["scenes"] if x["scene_id"] == sid)["retained"]
    n_air = next(x for x in seg["scenes"] if x["scene_id"] == sid)["n_aircraft"]
    ax.set_title(f"{title}\n$N$={n_air} aircraft · {max(doses)} injectable candidates",
                 loc="left", fontsize=9.5)
    ax.set_xlabel("Aircraft with 15 km vectoring")
    ax.set_ylabel("Correlation dimension $D$")
    ax.set_xticks(doses)
    ax.grid(True, color="#E5E7EB", lw=.7, zorder=0)
    ax.text(.03, .96,
            f"median $\\rho$ = {sc['median']:.2f}\n{sc['positive']}/{sc['n']} orders positive",
            transform=ax.transAxes, va="top", ha="left", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#D1D5DB", lw=.7))
    ax.text(-.13, 1.08, lab, transform=ax.transAxes, fontweight="bold", fontsize=14, va="top")
    ax.legend(loc="lower right", frameon=False, fontsize=7.5)

ax = axes[3]
rng = np.random.default_rng(7)
def vals(d, key):
    return [c["retained"][key] for c in d["curves"] if c["retained"][key] is not None]
for x, arm, color in [(0, smo, colors["smo"]), (1, seg, colors["seg"])]:
    v = np.array(vals(arm, "rho"), float)
    ax.scatter(x + rng.uniform(-.07, .07, len(v)), v, s=28, color=color,
               alpha=.8, edgecolor="white", linewidth=.5, zorder=3)
    ax.hlines(np.median(v), x - .22, x + .22, color=color, lw=2.5, zorder=4)
    ax.text(x + .25, np.median(v), f"median\n{np.median(v):.3f}",
            va="center", ha="left", fontsize=8.5, color=color)
    ax.text(x, 1.02, f"{int((v > 0).sum())}/{len(v)} positive",
            ha="center", va="bottom", fontsize=8.8, color=color, fontweight="bold")
ax.axhline(0, color="#374151", lw=1.0, ls="--")
ax.set_xticks([0, 1])
ax.set_xticklabels(["Smooth 15 km", "Segmented 15 km"])
ax.set_xlim(-.45, 1.45)
ax.set_ylim(-1.05, 1.12)
ax.set_ylabel("Spearman $\\rho$ (dose vs $D$)")
ax.set_title("All estimable curves: 3 scenes × 5 orders", loc="left", fontsize=9.5)
ax.grid(True, axis="y", color="#E5E7EB", lw=.7, zorder=0)
ax.text(.03, .04, "each dot = one order", transform=ax.transAxes,
        fontsize=7.5, color="#4B5563")
ax.text(-.13, 1.08, "D", transform=ax.transAxes, fontweight="bold", fontsize=14, va="top")
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.text(0.5, 0.012,
         "Thin grey lines: five injection orders. Thick line: median across orders. "
         "2026-09-14 has only 4 doses (<5 valid) and is not estimable.",
         ha="center", fontsize=8, color="#4B5563")
out = repo / "evaluation/figures"
out.mkdir(parents=True, exist_ok=True)
for ext in ["png", "pdf"]:
    fig.savefig(out / f"segmented-positive-dose-response.{ext}", dpi=300, bbox_inches="tight")
print("saved", out)
