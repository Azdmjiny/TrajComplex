"""Run the reproducible Experiment IV-A pipeline from prepared tracks or embeddings."""
from __future__ import annotations

import argparse
import csv
from datetime import timedelta
import gzip
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import time

import numpy as np
from scipy.spatial.distance import pdist

from prepare_encode import (
    _hour_datetime, encode_prepared_scenes, prepare_archive,
    read_json, sha256_config, sha256_file, write_json,
)


def raw_slope(vectors: np.ndarray, radii: np.ndarray) -> tuple[float | None, dict]:
    """OLS slope over all fixed radii with 0<C(r)<1; retain fit diagnostics."""
    values = np.asarray(vectors, dtype=np.float64)
    radii = np.asarray(radii, dtype=np.float64)
    diag = {"reason": "OK", "fit_scales": 0, "r_squared": None,
            "first_radius": None, "last_radius": None}
    if values.ndim != 2 or len(values) < 2:
        return None, {**diag, "reason": "fewer_than_two_embeddings"}
    if not np.isfinite(values).all():
        return None, {**diag, "reason": "nonfinite_embeddings"}
    distances = np.sort(pdist(values, metric="euclidean"))
    if distances.size == 0 or not np.isfinite(distances).all():
        return None, {**diag, "reason": "nonfinite_or_empty_distances"}
    # The denominator includes every unordered pair, including zero-distance pairs.
    correlation = np.searchsorted(distances, radii, side="left") / distances.size
    keep = (correlation > 0.0) & (correlation < 1.0)
    x = np.log(radii[keep])
    y = np.log(correlation[keep])
    diag["fit_scales"] = int(len(x))
    if len(x) < 2:
        return None, {**diag, "reason": "fewer_than_two_eligible_scales"}
    centered_x = x - x.mean()
    centered_y = y - y.mean()
    denominator = float(centered_x @ centered_x)
    if denominator <= np.finfo(float).eps:
        return None, {**diag, "reason": "degenerate_log_radius"}
    slope = float((centered_x @ centered_y) / denominator)
    intercept = float(y.mean() - slope * x.mean())
    if not np.isfinite([slope, intercept]).all():
        return None, {**diag, "reason": "nonfinite_ols"}
    residual = y - (slope * x + intercept)
    total = float(centered_y @ centered_y)
    r_squared = float(1.0 - (residual @ residual) / total) if total > 0 else None
    return slope, {
        "reason": "OK",
        "fit_scales": int(len(x)),
        "r_squared": r_squared,
        "first_radius": float(radii[keep][0]),
        "last_radius": float(radii[keep][-1]),
    }


def make_orders(n: int, count: int, seed: int) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    return [rng.permutation(n) for _ in range(count)]


def _quantiles(values: list[float]) -> dict:
    if not values:
        return {"hours": 0, "q25": None, "median": None, "q75": None}
    q25, median, q75 = np.quantile(np.asarray(values, dtype=float), [0.25, 0.5, 0.75])
    return {"hours": len(values), "q25": float(q25), "median": float(median), "q75": float(q75)}


def summarize_rows(rows: list[dict], display_bins: list[list[int]]) -> tuple[dict, dict]:
    max_n = max((row["N"] for row in rows), default=0)
    exact = []
    for n in range(5, max_n + 1):
        values = [row["curve"][n - 5] for row in rows
                  if row["N"] >= n and row["curve"][n - 5] is not None]
        exact.append({"n": n, **_quantiles(values)})

    paired = []
    for row in rows:
        if row["N"] < 30 or len(row["curve"]) < 26:
            continue
        d5, d30 = row["curve"][0], row["curve"][25]
        if d5 is not None and d30 is not None:
            paired.append({"key": row["key"], "d_n5": d5, "d_n30": d30, "difference": d30 - d5})
    differences = [item["difference"] for item in paired]
    binned_rows = []
    for lo, hi in display_bins:
        scene_values = []
        for row in rows:
            available = [row["curve"][n - 5] for n in range(lo, min(hi, row["N"]) + 1)
                         if row["curve"][n - 5] is not None]
            if available:
                scene_values.append({
                    "key": row["key"],
                    "median": float(np.median(available)),
                    "available_n": len(available),
                })
        values = [item["median"] for item in scene_values]
        binned_rows.append({
            "bin": [lo, hi],
            **_quantiles(values),
            "scene_values": scene_values,
        })

    summary = {
        "hours": len(rows),
        "eligible_fragments": int(sum(row["N"] for row in rows)),
        "hours_below_five_fragments": int(sum(row["N"] < 5 for row in rows)),
        "maximum_hourly_fragments": int(max_n),
        "fit_status_counts": {},
        "by_n": {str(item["n"]): item for item in exact},
        "paired_n5_to_n30": {
            "hours": len(paired),
            "median_difference_n30_minus_n5": float(np.median(differences)) if differences else None,
            "increased_hours": int(sum(value > 0 for value in differences)),
            "decreased_hours": int(sum(value < 0 for value in differences)),
            "tied_hours": int(sum(value == 0 for value in differences)),
            "rows": paired,
        },
    }
    binned = {"display_range": [min(x[0] for x in display_bins), max(x[1] for x in display_bins)],
              "bins": binned_rows}
    return summary, binned


def compute_results(
    embeddings_path: Path,
    output_dir: Path,
    config_path: Path | None = None,
    *,
    encoding_metadata: dict | None = None,
    enforce_paper_counts: bool = True,
) -> dict:
    config = read_json(config_path)
    embeddings_path = Path(embeddings_path).resolve()
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}")
    archive_sha256 = sha256_file(embeddings_path)
    metadata = encoding_metadata
    using_bundled_cache = metadata is None
    if metadata is None:
        if archive_sha256 != config["cached_embeddings"]["sha256"]:
            raise ValueError("Cached embeddings do not match the bundled experiment cache")
        rows = []
        with np.load(embeddings_path, allow_pickle=False) as archive:
            for key in sorted(archive.files):
                vectors = np.asarray(archive[key])
                if vectors.ndim != 2 or vectors.shape[1] != int(config["encoder"]["dimensions"]):
                    raise ValueError(f"Invalid embedding array shape for {key}")
                local_time = _hour_datetime(key) + timedelta(hours=int(config["utc_offset_hours"]))
                rows.append({
                    "key": key,
                    "local_date": local_time.date().isoformat(),
                    "local_hour": local_time.hour,
                    "N": len(vectors),
                })
        metadata = {
            "total_embeddings": sum(row["N"] for row in rows),
            "source_fragments": int(config["data"]["expected_source_fragments"]),
            "excluded_below_30": int(config["data"]["expected_source_fragments"] - config["expected_results"]["eligible_fragments"]),
            "unique_flights": int(config["expected_results"]["unique_flights"]),
            "eligible_sample_points": int(config["expected_results"]["eligible_sample_points"]),
            "source_archive_sha256": config["data"]["expected_sha256"],
            "checkpoint_epoch": config["encoder"]["checkpoint_epoch"],
            "checkpoint_sha256": config["encoder"]["checkpoint_sha256"],
            "training_airport": config["encoder"]["training_airport"],
            "dimensions": config["encoder"]["dimensions"],
            "pooling": config["encoder"]["pooling"],
            "post_pooling_normalization": config["encoder"]["post_pooling_normalization"],
            "preprocessor_id": config["encoder"]["preprocessor_id"],
            "embedding_archive_sha256": archive_sha256,
            "rows": rows,
        }
    elif metadata.get("embedding_archive_sha256") != archive_sha256:
        raise ValueError("Generated embedding archive hash differs from its in-memory encoding metadata")
    enc_cfg = config["encoder"]
    expected_counts = config["expected_results"]
    for key, expected_value in (("checkpoint_epoch", enc_cfg["checkpoint_epoch"]),
                                ("checkpoint_sha256", enc_cfg["checkpoint_sha256"]),
                                ("training_airport", enc_cfg["training_airport"]),
                                ("dimensions", enc_cfg["dimensions"]),
                                ("pooling", enc_cfg["pooling"]),
                                ("preprocessor_id", enc_cfg["preprocessor_id"])):
        if metadata.get(key) != expected_value:
            raise ValueError(f"Embedding metadata mismatch for {key}: expected {expected_value!r}")
    if bool(metadata.get("post_pooling_normalization")) != bool(enc_cfg["post_pooling_normalization"]):
        raise ValueError("Embedding metadata has unexpected post-pooling normalization")
    metadata_counts = {
        "total_embeddings": expected_counts["eligible_fragments"],
        "source_fragments": config["data"]["expected_source_fragments"],
        "excluded_below_30": config["data"]["expected_source_fragments"] - expected_counts["eligible_fragments"],
        "unique_flights": expected_counts["unique_flights"],
        "eligible_sample_points": expected_counts["eligible_sample_points"],
    }
    for key, value in metadata_counts.items():
        if int(metadata.get(key, -1)) != int(value):
            raise ValueError(f"Embedding metadata count mismatch for {key}")
    if len(metadata.get("rows", [])) != int(expected_counts["hours"]):
        raise ValueError("Embedding metadata does not contain all 720 hourly scenes")
    if metadata.get("source_archive_sha256") != config["data"]["expected_sha256"]:
        raise ValueError("Embedding metadata source archive hash does not match embedded experiment protocol")

    radii_spec = config["estimator"]["radii"]
    grid_hash = hashlib.sha256(np.asarray(radii_spec, dtype="<f8").tobytes()).hexdigest()
    if grid_hash != config["estimator"]["radius_grid_sha256"]:
        raise ValueError("Fixed radius values do not match their hash in embedded experiment protocol")
    radii = np.asarray(radii_spec, dtype=np.float64)
    if radii.shape != (64,) or not np.isfinite(radii).all() or np.any(radii <= 0) or np.any(np.diff(radii) <= 0):
        raise ValueError("Expected 64 finite, positive, increasing fixed radii")

    rows_meta = metadata.get("rows", [])
    if not rows_meta:
        raise ValueError("Embedding metadata contains no hourly rows")
    keys = [row["key"] for row in rows_meta]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise ValueError("Hourly metadata must have unique chronological scene keys")
    orders_per_hour = int(config["sampling"]["orders_per_hour"])
    seed_base = int(config["sampling"]["seed_base"])
    start_n = int(config["sampling"]["start_n"])
    result_rows = []
    fit_statuses: dict[str, int] = {}
    attempted_fits = 0
    valid_fits = 0

    output_dir.mkdir(parents=True)
    results_path = output_dir / "d-vs-n-no-gate.json"
    sequence_path = output_dir / "sequence_results.csv.gz"
    with np.load(embeddings_path, allow_pickle=False) as archive, gzip.open(
        sequence_path, "wt", encoding="utf-8", newline=""
    ) as stream:
        archive_keys = set(archive.files)
        if archive_keys != set(keys):
            raise ValueError("Embedding archive keys do not match the scene metadata")
        writer = csv.DictWriter(stream, fieldnames=[
            "hour", "order", "n", "slope", "reason", "fit_scales", "r_squared", "first_radius", "last_radius",
        ])
        writer.writeheader()
        for hour_index, meta in enumerate(rows_meta, start=1):
            key = meta["key"]
            vectors = np.asarray(archive[key], dtype=np.float64)
            n_scene = int(meta["N"])
            if vectors.shape != (n_scene, int(enc_cfg["dimensions"])) or not np.isfinite(vectors).all():
                raise ValueError(f"Embedding shape or values do not match the scene metadata for {key}")
            permutations = make_orders(n_scene, orders_per_hour, seed_base + hour_index)
            curve, valid = [], []
            for n in range(start_n, n_scene + 1):
                slopes = []
                for order_index, permutation in enumerate(permutations, start=1):
                    slope, diagnostic = raw_slope(vectors[permutation[:n]], radii)
                    attempted_fits += 1
                    fit_statuses[diagnostic["reason"]] = fit_statuses.get(diagnostic["reason"], 0) + 1
                    if slope is not None:
                        slopes.append(slope)
                        valid_fits += 1
                    writer.writerow({
                        "hour": key,
                        "order": order_index,
                        "n": n,
                        "slope": "" if slope is None else format(slope, ".17g"),
                        **diagnostic,
                    })
                curve.append(float(np.median(slopes)) if slopes else None)
                valid.append(len(slopes))
            result_rows.append({
                "key": key,
                "local_date": meta["local_date"],
                "local_hour": int(meta["local_hour"]),
                "N": n_scene,
                "curve": curve,
                "valid": valid,
                "status": "BELOW_FIVE" if n_scene < start_n else "COMPUTED" if any(x is not None for x in curve) else "ALL_FITS_UNDEFINED",
            })

    write_json(results_path, {
        "orders": orders_per_hour,
        "start_n": start_n,
        "config": "Fixed shared radii; raw OLS slope over every scale with 0<C(r)<1; at least two scales; no fit-quality gate.",
        "radius_grid_sha256": grid_hash,
        "embedding_archive_sha256": sha256_file(embeddings_path),
        "rows": result_rows,
    })
    summary, binned = summarize_rows(result_rows, config["display"]["paper_bins"])
    summary["unique_flights"] = int(metadata.get("unique_flights", 0))
    summary["eligible_sample_points"] = int(metadata.get("eligible_sample_points", 0))
    summary["attempted_fits"] = attempted_fits
    summary["valid_fits"] = valid_fits
    summary["fit_status_counts"] = fit_statuses
    summary["embedding_archive_sha256"] = sha256_file(embeddings_path)
    summary["radius_grid_sha256"] = grid_hash
    write_json(output_dir / "summary.json", summary)
    binned.update({
        "paper_bin_edges": config["display"]["paper_bins"],
        "selection_note": config["display"]["paper_range_selection"],
        "full_observed_n_range": [start_n, max((row["N"] for row in result_rows), default=start_n - 1)],
    })
    write_json(output_dir / "binned-summary.json", binned)

    if enforce_paper_counts:
        checks = {
            "hours": summary["hours"] == expected_counts["hours"],
            "eligible_fragments": summary["eligible_fragments"] == expected_counts["eligible_fragments"],
            "hours_below_five_fragments": summary["hours_below_five_fragments"] == expected_counts["hours_below_five_fragments"],
            "maximum_hourly_fragments": summary["maximum_hourly_fragments"] == expected_counts["maximum_hourly_fragments"],
            "paired_hours": summary["paired_n5_to_n30"]["hours"] == expected_counts["paired_hours_n5_to_n30"],
            "paired_median_difference": abs(summary["paired_n5_to_n30"]["median_difference_n30_minus_n5"] - expected_counts["paired_median_difference_n30_minus_n5"]) < 1e-8,
            "paired_increased": summary["paired_n5_to_n30"]["increased_hours"] == expected_counts["paired_increased_hours"],
            "paired_decreased": summary["paired_n5_to_n30"]["decreased_hours"] == expected_counts["paired_decreased_hours"],
        }
        if using_bundled_cache:
            checks["bundled_cache_hash"] = archive_sha256 == config["cached_embeddings"]["sha256"]
        else:
            checks["unique_flights"] = summary["unique_flights"] == expected_counts["unique_flights"]
            checks["eligible_sample_points"] = summary["eligible_sample_points"] == expected_counts["eligible_sample_points"]
        write_json(output_dir / "validation.json", {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks})
        if not all(checks.values()):
            raise ValueError(f"Result validation failed: {[key for key, ok in checks.items() if not ok]}")
    print(json.dumps({k: v for k, v in summary.items() if k not in {"by_n", "paired_n5_to_n30", "fit_status_counts"}}, indent=2))
    return summary

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


def plot_results(results_dir: Path, output_dir: Path, config_path: Path | None = None) -> list[Path]:
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
    config_path: Path | None = None,
    *,
    archive_path: Path | None = None,
    checkpoint_path: Path | None = None,
    embeddings_path: Path | None = None,
    device: str = "auto",
) -> dict:
    output_dir = Path(output_dir).resolve()
    config_path = Path(config_path).resolve() if config_path is not None else None
    config = read_json(config_path)
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}")
    full_inputs = archive_path is not None or checkpoint_path is not None
    cached_inputs = embeddings_path is not None
    if full_inputs == cached_inputs:
        raise ValueError("Provide either --archive with --checkpoint, or the bundled --embeddings cache")
    if full_inputs and (archive_path is None or checkpoint_path is None):
        raise ValueError("The full pipeline requires both --archive and --checkpoint")
    output_dir.mkdir(parents=True)
    started = time.time()
    protocol = {
        "experiment": config["experiment"],
        "status": "running",
        "command_template": (
            "run_experiment.py --archive <prepared-trajectory-zip> --checkpoint <epoch-60-checkpoint>"
            if archive_path is not None else
            "run_experiment.py --embeddings <bundled-embedding-npz>"
        ),
        "git_head": _git_head(),
        "python": platform.python_version(),
        "config_sha256": sha256_config(config),
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
        else:
            embeddings_path = Path(embeddings_path).resolve()
            protocol.update({
                "embeddings_name": embeddings_path.name,
                "embeddings_sha256": sha256_file(embeddings_path),
            })
            write_json(output_dir / "protocol.json", protocol)
            metadata = None

        results_dir = output_dir / "results"
        compute_results(
            embeddings_path, results_dir, config_path, encoding_metadata=metadata,
        )
        figure_dir = output_dir / "figures"
        figures = plot_results(results_dir, figure_dir, config_path)
        validation = read_json(results_dir / "validation.json")
        protocol.update({
            "status": "complete" if validation["status"] == "PASS" else "failed_validation",
            "elapsed_seconds": time.time() - started,
            "embedding_archive_sha256": sha256_file(embeddings_path),
            "results_summary_sha256": sha256_file(results_dir / "summary.json"),
            "figures": [str(path.relative_to(output_dir)) for path in figures],
        })
        write_json(output_dir / "protocol.json", protocol)
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
    parser.add_argument("--output", type=Path, required=True, help="New run directory; existing directories are never overwritten")
    parser.add_argument("--config", type=Path, help="Optional JSON override for the embedded experiment protocol")
    parser.add_argument("--device", default="auto", help="auto, cpu, or cuda")
    args = parser.parse_args()
    if args.archive is not None and args.checkpoint is None:
        parser.error("--checkpoint is required with --archive")
    result = run_experiment(
        args.output, args.config,
        archive_path=args.archive, checkpoint_path=args.checkpoint,
        embeddings_path=args.embeddings,
        device=args.device,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "config"}, indent=2))


if __name__ == "__main__":
    main()
