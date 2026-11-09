"""Compute raw finite-grid slopes and paper-aligned summaries for Experiment IV-A."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial.distance import pdist

from prepare_scenes import DEFAULT_CONFIG, read_json, sha256_file, write_json


HERE = Path(__file__).resolve().parent


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
    metadata_path: Path,
    output_dir: Path,
    config_path: Path = DEFAULT_CONFIG,
    *,
    enforce_paper_counts: bool = True,
) -> dict:
    config = read_json(config_path)
    embeddings_path = Path(embeddings_path).resolve()
    metadata_path = Path(metadata_path).resolve()
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}")
    metadata = read_json(metadata_path)
    if metadata.get("embedding_archive_sha256") != sha256_file(embeddings_path):
        raise ValueError("Embedding archive SHA-256 does not match encoding-summary.json")
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
        raise ValueError("Embedding metadata source archive hash does not match config.json")

    radii_spec = config["estimator"]["radii"]
    grid_hash = hashlib.sha256(np.asarray(radii_spec, dtype="<f8").tobytes()).hexdigest()
    if grid_hash != config["estimator"]["radius_grid_sha256"]:
        raise ValueError("Fixed radius values do not match their hash in config.json")
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
            raise ValueError("Embedding archive keys do not match encoding-summary.json")
        writer = csv.DictWriter(stream, fieldnames=[
            "hour", "order", "n", "slope", "reason", "fit_scales", "r_squared", "first_radius", "last_radius",
        ])
        writer.writeheader()
        for hour_index, meta in enumerate(rows_meta, start=1):
            key = meta["key"]
            vectors = np.asarray(archive[key], dtype=np.float64)
            n_scene = int(meta["N"])
            if vectors.shape != (n_scene, int(enc_cfg["dimensions"])) or not np.isfinite(vectors).all():
                raise ValueError(f"Embedding shape or values do not match metadata for {key}")
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
            "unique_flights": summary["unique_flights"] == expected_counts["unique_flights"],
            "eligible_sample_points": summary["eligible_sample_points"] == expected_counts["eligible_sample_points"],
            "hours_below_five_fragments": summary["hours_below_five_fragments"] == expected_counts["hours_below_five_fragments"],
            "maximum_hourly_fragments": summary["maximum_hourly_fragments"] == expected_counts["maximum_hourly_fragments"],
            "paired_hours": summary["paired_n5_to_n30"]["hours"] == expected_counts["paired_hours_n5_to_n30"],
            "paired_median_difference": abs(summary["paired_n5_to_n30"]["median_difference_n30_minus_n5"] - expected_counts["paired_median_difference_n30_minus_n5"]) < 1e-8,
            "paired_increased": summary["paired_n5_to_n30"]["increased_hours"] == expected_counts["paired_increased_hours"],
            "paired_decreased": summary["paired_n5_to_n30"]["decreased_hours"] == expected_counts["paired_decreased_hours"],
        }
        write_json(output_dir / "validation.json", {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks})
        if not all(checks.values()):
            raise ValueError(f"Result validation failed: {[key for key, ok in checks.items() if not ok]}")
    print(json.dumps({k: v for k, v in summary.items() if k not in {"by_n", "paired_n5_to_n30", "fit_status_counts"}}, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embeddings", type=Path, required=True, help="NPZ with one 16-D array per hourly scene")
    parser.add_argument("--metadata", type=Path, required=True, help="encoding-summary.json matching the E60 embeddings")
    parser.add_argument("--output", type=Path, required=True, help="New output directory for curves and summaries")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--allow-nonpaper-counts", action="store_true", help="Keep diagnostics but skip paper-count acceptance checks")
    args = parser.parse_args()
    compute_results(args.embeddings, args.metadata, args.output, args.config,
                    enforce_paper_counts=not args.allow_nonpaper_counts)


if __name__ == "__main__":
    main()
