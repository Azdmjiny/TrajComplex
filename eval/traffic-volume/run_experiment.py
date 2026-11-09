"""Run the reproducible Experiment IV-A pipeline from prepared tracks or embeddings."""
from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
import subprocess
import time

from compute_results import compute_results
from encode_scenes import encode_prepared_scenes
from prepare_scenes import DEFAULT_CONFIG, prepare_archive, read_json, sha256_file, write_json


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]


def _git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def plot_results(results_dir: Path, output_dir: Path, config_path: Path = DEFAULT_CONFIG) -> list[Path]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Plotting requires matplotlib; install the repository requirements") from exc

    results_dir = Path(results_dir).resolve()
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}")
    curves = read_json(results_dir / "d-vs-n-no-gate.json")["rows"]
    binned = read_json(results_dir / "binned-summary.json")
    config = read_json(config_path)
    output_dir.mkdir(parents=True)
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "font.size": 9,
        "axes.labelsize": 10,
        "xtick.labelsize": 8,
        "ytick.labelsize": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.75,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    })

    bins = [tuple(pair) for pair in config["display"]["paper_bins"]]
    bin_rows = binned["bins"]
    if [tuple(row["bin"]) for row in bin_rows] != bins:
        raise ValueError("Binned results do not match the fixed paper bin definitions")
    values = [[item["median"] for item in row["scene_values"]] for row in bin_rows]
    medians = [row["median"] for row in bin_rows]
    counts = [row["hours"] for row in bin_rows]
    if any(not sample for sample in values):
        raise ValueError("A configured display bin has no contributing hours")

    fig, (ax, lower) = plt.subplots(
        2, 1, figsize=(7.16, 4.65), sharex=True,
        gridspec_kw={"height_ratios": [3.4, 1], "hspace": 0.10},
    )
    fig.subplots_adjust(left=0.10, right=0.985, bottom=0.115, top=0.975)
    x = np.arange(len(bins))
    box = ax.boxplot(
        values, positions=x, widths=0.60, patch_artist=True, showfliers=False,
        manage_ticks=False,
        medianprops={"color": "#183746", "linewidth": 1.1},
        whiskerprops={"color": "#566570", "linewidth": 0.85},
        capprops={"color": "#566570", "linewidth": 0.85},
        boxprops={"edgecolor": "#566570", "linewidth": 0.85},
    )
    palette = np.linspace(0.0, 1.0, len(box["boxes"]))
    for index, patch in enumerate(box["boxes"]):
        patch.set_facecolor(plt.cm.GnBu(0.42 + 0.34 * palette[index]))
    ax.plot(x, medians, "o-", color="#204e70", lw=1.3, ms=3.5, label="Median across hours")
    ax.set_ylabel(r"Correlation-integral slope, $D$")
    ax.legend(frameon=False, fontsize=9, loc="lower right", handlelength=2.1, borderaxespad=0.6)
    lower.bar(x, counts, width=0.60, color="#9eb4c8")
    lower.set_xticks(x, [f"{lo}–{hi}" for lo, hi in bins])
    lower.set_xlabel(r"Number of sampled arrival trajectories, $n$")
    lower.set_ylabel("Contributing\nhours")
    lower.set_ylim(0, max(counts) * 1.18)
    for index, count in enumerate(counts):
        lower.text(index, count + max(counts) * 0.025, str(count), ha="center", va="bottom", fontsize=7.5)
    for axis in (ax, lower):
        axis.grid(axis="y", color="#e1e5e8", lw=0.5)
        axis.set_axisbelow(True)
        axis.tick_params(length=3, width=0.75)
    paper_path = output_dir / "figure4_sample_size_binned.pdf"
    fig.savefig(paper_path, facecolor="white", bbox_inches="tight")
    fig.savefig(output_dir / "figure4_sample_size_binned.png", dpi=400, facecolor="white", bbox_inches="tight")
    plt.close(fig)

    available_n = []
    hourly_values = []
    for n in range(5, max((row["N"] for row in curves), default=4) + 1):
        values_n = [row["curve"][n - 5] for row in curves
                    if row["N"] >= n and row["curve"][n - 5] is not None]
        if values_n:
            available_n.append(n)
            hourly_values.append(values_n)
    if not available_n:
        raise ValueError("No estimable sample sizes in the full-range results")
    full_fig, (full_ax, count_ax) = plt.subplots(
        2, 1, figsize=(10.5, 6.2), sharex=True,
        gridspec_kw={"height_ratios": [3.4, 1], "hspace": 0.08},
    )
    full_box = full_ax.boxplot(
        hourly_values, positions=available_n, widths=0.62, patch_artist=True,
        showfliers=True, manage_ticks=False,
        medianprops={"color": "#173f59", "linewidth": 0.9},
        flierprops={"marker": ".", "markersize": 2, "alpha": 0.25,
                    "markerfacecolor": "#728792", "markeredgecolor": "none"},
        whiskerprops={"color": "#81919a", "linewidth": 0.65},
        capprops={"color": "#81919a", "linewidth": 0.65},
    )
    for patch in full_box["boxes"]:
        patch.set(facecolor="#a7c9ce", edgecolor="#6b939f", linewidth=0.7)
    exact_medians = [float(np.median(values_n)) for values_n in hourly_values]
    count_ax.bar(available_n, [len(values_n) for values_n in hourly_values], color="#9bb8c7", width=0.72)
    full_ax.plot(available_n, exact_medians, color="#176783", lw=1.5, marker="o", ms=2.6)
    full_ax.set_ylabel(r"Raw correlation-integral slope $S_{\mathrm{raw}}$")
    count_ax.set_ylabel("Contributing\nhours")
    count_ax.set_xlabel(r"Number of sampled arrival trajectories, $n$")
    count_ax.set_xticks(sorted(set([5, *range(10, max(available_n) + 1, 5), max(available_n)])))
    for axis in (full_ax, count_ax):
        axis.grid(axis="y", color="#e1e5e8", lw=0.5)
        axis.set_axisbelow(True)
    diagnostic_path = output_dir / "figure_sample_size_full_range.pdf"
    full_fig.savefig(diagnostic_path, facecolor="white", bbox_inches="tight")
    full_fig.savefig(output_dir / "figure_sample_size_full_range.png", dpi=300, facecolor="white", bbox_inches="tight")
    plt.close(full_fig)
    return [paper_path, output_dir / "figure4_sample_size_binned.png",
            diagnostic_path, output_dir / "figure_sample_size_full_range.png"]



def run_experiment(
    output_dir: Path,
    config_path: Path = DEFAULT_CONFIG,
    *,
    archive_path: Path | None = None,
    checkpoint_path: Path | None = None,
    embeddings_path: Path | None = None,
    metadata_path: Path | None = None,
    device: str = "auto",
) -> dict:
    output_dir = Path(output_dir).resolve()
    config_path = Path(config_path).resolve()
    config = read_json(config_path)
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}")
    full_inputs = archive_path is not None or checkpoint_path is not None
    cached_inputs = embeddings_path is not None or metadata_path is not None
    if full_inputs == cached_inputs:
        raise ValueError("Provide either --archive with --checkpoint, or --embeddings with --metadata")
    if full_inputs and (archive_path is None or checkpoint_path is None):
        raise ValueError("The full pipeline requires both --archive and --checkpoint")
    if cached_inputs and (embeddings_path is None or metadata_path is None):
        raise ValueError("The cached-embedding path requires both --embeddings and --metadata")

    output_dir.mkdir(parents=True)
    started = time.time()
    protocol = {
        "experiment": config["experiment"],
        "status": "running",
        "command_template": (
            "run_experiment.py --archive <prepared-trajectory-zip> --checkpoint <epoch-60-checkpoint>"
            if archive_path is not None else
            "run_experiment.py --embeddings <embedding-npz> --metadata <encoding-summary.json>"
        ),
        "git_head": _git_head(),
        "python": platform.python_version(),
        "config_sha256": sha256_file(config_path),
        "config": config,
        "input_mode": "prepared_archive_and_checkpoint" if full_inputs else "cached_embeddings",
        "started_unix": started,
    }
    write_json(output_dir / "protocol.json", protocol)
    try:
        if full_inputs:
            archive_path = Path(archive_path).resolve()
            checkpoint_path = Path(checkpoint_path).resolve()
            protocol.update({
                "archive_sha256": sha256_file(archive_path),
                "checkpoint_sha256": sha256_file(checkpoint_path),
                "archive_name": archive_path.name,
                "checkpoint_name": checkpoint_path.name,
            })
            write_json(output_dir / "protocol.json", protocol)
            prepare_dir = output_dir / "prepared"
            prepare_archive(archive_path, prepare_dir, config_path)
            encoded_dir = output_dir / "encoded"
            metadata = encode_prepared_scenes(
                prepare_dir, checkpoint_path, encoded_dir, config_path, device=device,
            )
            embeddings_path = encoded_dir / "embeddings.npz"
            metadata_path = encoded_dir / "encoding-summary.json"
        else:
            embeddings_path = Path(embeddings_path).resolve()
            metadata_path = Path(metadata_path).resolve()
            protocol.update({
                "embeddings_name": embeddings_path.name,
                "embeddings_sha256": sha256_file(embeddings_path),
                "metadata_name": metadata_path.name,
                "metadata_sha256": sha256_file(metadata_path),
            })
            write_json(output_dir / "protocol.json", protocol)
            metadata = read_json(metadata_path)

        results_dir = output_dir / "results"
        summary = compute_results(embeddings_path, metadata_path, results_dir, config_path)
        figure_dir = output_dir / "figures"
        figures = plot_results(results_dir, figure_dir, config_path)
        validation = read_json(results_dir / "validation.json")
        protocol.update({
            "status": "complete" if validation["status"] == "PASS" else "failed_validation",
            "elapsed_seconds": time.time() - started,
            "embedding_archive_sha256": sha256_file(embeddings_path),
            "encoding_metadata_sha256": sha256_file(metadata_path),
            "results_summary_sha256": sha256_file(results_dir / "summary.json"),
            "figures": [str(path.relative_to(output_dir)) for path in figures],
        })
        write_json(output_dir / "protocol.json", protocol)
        write_json(output_dir / "validation.json", {
            "status": validation["status"],
            "paper_count_and_paired_result_checks": validation["checks"],
            "verified_embedding_metadata": {
                "hours": len(metadata["rows"]),
                "eligible_fragments": metadata["total_embeddings"],
                "checkpoint_epoch": metadata["checkpoint_epoch"],
                "checkpoint_sha256": metadata["checkpoint_sha256"],
            },
            "paired_n5_to_n30": summary["paired_n5_to_n30"],
        })
        return protocol
    except Exception as exc:
        protocol.update({
            "status": "failed",
            "elapsed_seconds": time.time() - started,
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
        write_json(output_dir / "protocol.json", protocol)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--archive", type=Path, help="Prepared hourly trajectory ZIP for the full encoding pipeline")
    group.add_argument("--embeddings", type=Path, help="Cached NPZ with one 16-D vector array per hour")
    parser.add_argument("--checkpoint", type=Path, help="Frozen WSSS epoch-60 checkpoint; required with --archive")
    parser.add_argument("--metadata", type=Path, help="Matching encoding-summary.json; required with --embeddings")
    parser.add_argument("--output", type=Path, required=True, help="New run directory; existing directories are never overwritten")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--device", default="auto", help="auto, cpu, or cuda")
    args = parser.parse_args()
    if args.archive is not None and args.checkpoint is None:
        parser.error("--checkpoint is required with --archive")
    if args.embeddings is not None and args.metadata is None:
        parser.error("--metadata is required with --embeddings")
    result = run_experiment(
        args.output, args.config,
        archive_path=args.archive, checkpoint_path=args.checkpoint,
        embeddings_path=args.embeddings, metadata_path=args.metadata,
        device=args.device,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "config"}, indent=2))


if __name__ == "__main__":
    main()
