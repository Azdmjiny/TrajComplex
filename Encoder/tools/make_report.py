"""Generate English delivery note and scientific plots from completed runs."""
import csv
import os
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".runtime_cache" / "matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from trajectory_encoder.common import ROOT, read_json, write_json


def main():
    sel = read_json(ROOT / "reports" / "selection.json")
    results = read_json(ROOT / "reports" / "test_results.json")
    initial = read_json(ROOT / "reports" / "untrained_test_results.json")
    targets = read_json(ROOT / "config.json")["evaluation"]["targets"]
    chosen = sel["selected_run"]["run_id"]
    labels = {"path_m": "Path length", "curvature_rad": "Accumulated turn", "sinuosity": "Sinuosity", "duration_s": "Duration"}
    rows = []
    for job in sel["grid"]:
        name = job["run_id"]
        for pooling in ("sum", "mean", "gem2"):
            result = results[name][pooling]
            for target in targets:
                rows.append({"run_id": name, "dimension": job["dimension"], "seed": job["seed"], "pooling": pooling,
                    "target": target, "validation_R2": result["probes"]["global_validation_R2"][target],
                    "test_R2": result["probes"]["global_test_R2"][target],
                    "within_STAR_test_macro_R2": result["probes"]["within_STAR_test_macro_R2"][target],
                    "untrained_test_R2": initial[name][pooling]["global_test_R2"][target],
                    "untrained_within_STAR_test_macro_R2": initial[name][pooling]["within_STAR_test_macro_R2"][target]})
    with (ROOT / "reports" / "probe_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    summary = {}
    for dimension in (4, 8, 16):
        for pooling in ("sum", "mean", "gem2"):
            values = [r for r in rows if r["dimension"] == dimension and r["pooling"] == pooling]
            entry = {}
            for metric in ("test_R2", "within_STAR_test_macro_R2", "untrained_test_R2", "untrained_within_STAR_test_macro_R2"):
                entry[metric] = {t: {"mean": float(np.mean([r[metric] for r in values if r["target"] == t])),
                                     "std_ddof1": float(np.std([r[metric] for r in values if r["target"] == t], ddof=1))} for t in targets}
            summary[f"d{dimension}_{pooling}"] = entry
    write_json(ROOT / "reports" / "three_seed_summary.json", summary)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 140})
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    for j, target in enumerate(targets):
        ax = axes.flat[j]
        dims = np.array([4, 8, 16])
        for pooling, color, offset in (("sum", "#1769aa", -.7), ("mean", "#e98b29", 0), ("gem2", "#39886b", .7)):
            values = [summary[f"d{d}_{pooling}"]["within_STAR_test_macro_R2"][target] for d in dims]
            ax.errorbar(dims+offset, [v["mean"] for v in values], yerr=[v["std_ddof1"] for v in values], color=color, marker="o", capsize=3, label=pooling)
        ax.set(title=labels[target], xlabel="Embedding dimension", ylabel="Within-STAR TEST R²", xticks=dims)
        ax.axhline(0, color="gray", lw=.6); ax.grid(alpha=.2)
    axes.flat[0].legend(ncol=3)
    fig.suptitle("Held-out geometric proxies: mean ± SD over 3 seeds (choices fixed on validation)")
    fig.savefig(ROOT / "reports" / "dimension_pooling.png"); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for job in sel["grid"]:
        history = read_json(ROOT / "runs" / job["run_id"] / "history.json")
        for ax, metric in zip(axes, ("train_loss", "validation_loss")):
            ax.plot([r["epoch"] for r in history], [r[metric] for r in history], label=f"D{job['dimension']} seed{job['seed']}", alpha=.75, lw=1)
            ax.set(xlabel="Epoch", ylabel="Flat-SNN loss", title=metric); ax.grid(alpha=.2)
    axes[1].legend(fontsize=7, ncol=2)
    fig.savefig(ROOT / "reports" / "training_curves.png"); plt.close(fig)
    confounding = read_json(ROOT / "reports" / "confounding_and_route.json")
    length_baseline = confounding["length_only_cubic_ridge"]["within_STAR_test_macro_R2"]
    trained_proxy = results[chosen]["sum"]["probes"]["within_STAR_test_macro_R2"]
    random_proxy = initial[chosen]["sum"]["within_STAR_test_macro_R2"]
    fig, ax = plt.subplots(figsize=(10, 4.5), constrained_layout=True)
    positions = np.arange(len(targets))
    for offset, name, values, color in [(-.25, "Trained Encoder", trained_proxy, "#1769aa"),
                                       (0., "Random Encoder", random_proxy, "#e98b29"),
                                       (.25, "Length-only ridge", length_baseline, "#7d7d7d")]:
        ax.bar(positions + offset, [values[t] for t in targets], width=.24, label=name, color=color)
    ax.set(xticks=positions, xticklabels=[labels[t] for t in targets], ylabel="Within-STAR TEST macro R²",
           title="Selected frozen Encoder vs initialization and length baselines")
    ax.axhline(0, color="black", lw=.6); ax.grid(axis="y", alpha=.2); ax.legend(ncol=3, fontsize=9)
    fig.savefig(ROOT / "reports" / "baseline_comparison.png"); plt.close(fig)
    histories = [read_json(ROOT / "runs" / j["run_id"] / "history.json") for j in sel["grid"]]
    epoch_count = sum(len(h) for h in histories)
    selected = results[chosen]["sum"]
    main_rows = [r for r in rows if r["run_id"] == chosen and r["pooling"] == "sum"]
    header = "| Geometric proxy | TEST R² | Within-STAR TEST macro R² | Random initialization within-STAR R² | Length baseline within-STAR R² |\n|---|---:|---:|---:|---:|\n"
    table = header + "\n".join(f"| {r['target']} | {r['test_R2']:.4f} | {r['within_STAR_test_macro_R2']:.4f} | {r['untrained_within_STAR_test_macro_R2']:.4f} | {length_baseline[r['target']]:.4f} |" for r in main_rows)
    stronger = [t for t in targets if trained_proxy[t] > max(random_proxy[t], length_baseline[t])]
    baseline_interpretation = ("The selected model numerically exceeds both baselines on these proxies: " + ", ".join(stronger) + "; the remaining proxies do not show improvement over the stronger baseline.") if stronger else "The selected model does not exceed the stronger of the two baselines on any of the four proxies. These tests therefore do not establish additional geometric-proxy prediction capability from self-supervised training."
    write_json(ROOT / "reports" / "quality_summary.json", {"training_complete": True, "selected_run": chosen,
               "within_STAR_trained": trained_proxy, "within_STAR_untrained": random_proxy,
               "within_STAR_length_only": length_baseline, "proxies_numerically_above_both_baselines": stronger,
               "complexity_application_validated": False, "interpretation": baseline_interpretation})
    note = f"""# Encoder training results

Encoder training specified in PLAN.md and the representation assessments supported by the available data are complete. Validation selected the main model: **{sel['selected_dimension']} dimensions, sum pooling, seed {sel['selected_run']['seed']}**. Frozen weights are in `encoder/encoder.pt`, corresponding to `{chosen}`. The nine best-validation checkpoints for three dimensions and three seeds are in `checkpoints/`.

## Completed work

- Hyperparameter screening: eight dimensions, seed42, ε=120/1200m × τ=.01/.05; four independent 30-epoch runs.
- Dimension/stability comparison: selected ε={sel['selected_run']['epsilon']}m and τ={sel['selected_run']['temperature']}; 4/8/16 dimensions with three seeds each, nine 30-epoch runs. One screening run is reused, giving 12 independent models and 360 epochs in total.
- Batch size 16 and bf16 mixed precision. Two processes initially ran in parallel; after one stopped progressing, training resumed serially from checkpoints without gradient accumulation. Final TEST evaluation followed validation-based checkpoint selection.
- Train/validation/test: 6877/1214/8092 full trajectories, sampled every five seconds with the endpoint retained. The original environment and raw data were not modified.

## Independent test of the representative checkpoint

{table}

{baseline_interpretation}

All probes are fitted on training data, with ridge alpha selected on validation data. Within-STAR macro averaging reduces the influence of route discrimination alone. Three-seed results and mean/GeM sensitivity are in `three_seed_summary.json` and `probe_summary.csv`. These targets are geometric proxies, not complexity ground truth. The randomly initialized baseline measures changes due to training; signals already predictable at initialization must not all be attributed to self-supervised training.

## Representation diagnostics

The representative model has TEST effective rank {selected['diagnostics']['effective_rank']:.4f} / {sel['selected_dimension']}, with {selected['diagnostics']['collapsed_dimensions']} low-variance dimensions at threshold 1e-8. The correlation between sum-vector norm and sample length is {selected['diagnostics']['norm_length_pearson']:.4f}. Effective rank below output dimension suggests information may be concentrated in fewer directions. Per-dimension variance, distance distributions, and length-stratified probes are saved in `test_results.json`; nonzero vectors alone do not establish the absence of representation degradation. Interpret sum/length confounding alongside mean/GeM and length-stratified results.

## Delivery and limitations

Weights, preprocessing, configuration, raw-file SHA256 values, per-trajectory split assignments, seeds, epoch logs, validation-selection records, test results, randomly initialized baselines, the callable frozen interface, and a real example have been saved. `export_verification.json` checks loading, freezing, and feature-reconstruction consistency; `checkpoint_manifest.json` records hashes for nine checkpoints.

The data lack absolute timestamps and real flight IDs, so real flight/date-level separation and stable hourly point-cloud/correlation-dimension ranges have not been validated. This delivery is a trained ATSCC/ITSC-inspired Encoder, not a complete hourly complexity system or a strict reproduction of the original paper. A PowerShell telemetry interruption is recorded in PROTOCOL.md; training subsequently resumed from checkpoints in a process with outbound networking disabled.
"""
    (ROOT / "reports" / "RESULTS_5s_ZH.md").write_text(note, encoding="utf-8")
    print("Report written: reports/RESULTS_5s_ZH.md (historical five-second run)")


if __name__ == "__main__":
    main()
