"""Build hourly OpenSky embedding scenes for the existing Encoder/Complexity pipeline.

This is an explicit WSSS-to-RKSI transfer diagnostic, not a validated model deployment.
Generated data artifacts are written below the ignored data/ directory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from Complexity import ComplexityConfig, estimate_complexity
from Encoder.trajectory_encoder.inference import FrozenEncoder

DEFAULT_INPUT = ROOT / "data" / "OpenSky_Changi_2026-09" / "sampled_10s"
DEFAULT_OUTPUT = ROOT / "data" / "OpenSky_Changi_2026-09" / "encoder_scenes"
REQUIRED = {"time", "icao24", "lat", "lon", "geoaltitude", "onground"}
AIRPORT_LAT = 1.3592111111111111
AIRPORT_LON = 103.98932500000001
AIRPORT_ELEVATION_M = 6.66
WGS84_A = 6378137.0
WGS84_E2 = 6.69437999014e-3


def to_enu(lat, lon, altitude_m):
    """Convert WGS84 positions to local ENU; up uses geometric altitude."""
    lat = np.deg2rad(np.asarray(lat, dtype=np.float64))
    lon = np.deg2rad(np.asarray(lon, dtype=np.float64))
    height = np.asarray(altitude_m, dtype=np.float64)

    def ecef(phi, lam, h):
        prime_vertical = WGS84_A / np.sqrt(1.0 - WGS84_E2 * np.sin(phi) ** 2)
        return np.stack(((prime_vertical + h) * np.cos(phi) * np.cos(lam),
                         (prime_vertical + h) * np.cos(phi) * np.sin(lam),
                         (prime_vertical * (1.0 - WGS84_E2) + h) * np.sin(phi)), axis=-1)

    lat0, lon0 = np.deg2rad(AIRPORT_LAT), np.deg2rad(AIRPORT_LON)
    origin = ecef(np.asarray(lat0), np.asarray(lon0), np.asarray(AIRPORT_ELEVATION_M))
    delta = ecef(lat, lon, height) - origin
    east = -np.sin(lon0) * delta[:, 0] + np.cos(lon0) * delta[:, 1]
    north = (-np.sin(lat0) * np.cos(lon0) * delta[:, 0]
             - np.sin(lat0) * np.sin(lon0) * delta[:, 1] + np.cos(lat0) * delta[:, 2])
    up = (np.cos(lat0) * np.cos(lon0) * delta[:, 0]
          + np.cos(lat0) * np.sin(lon0) * delta[:, 1] + np.sin(lat0) * delta[:, 2])
    return np.column_stack((east, north, up))


def resample_10s_to_5s(times, coords):
    """Linearly interpolate ENU between observations on the model's 5s grid."""
    times = np.asarray(times, dtype=np.float64)
    coords = np.asarray(coords, dtype=np.float64)
    grid = np.arange(times[0], times[-1], 5.0, dtype=np.float64)
    grid = np.append(grid, times[-1])
    points = np.column_stack([np.interp(grid, times, coords[:, axis]) for axis in range(3)])
    return grid, points


def hourly_tracks(path: Path, max_gap_s: float, min_observed_points: int):
    frame = pd.read_csv(path, dtype={"icao24": "string", "callsign": "string"})
    missing = REQUIRED.difference(frame.columns)
    if missing:
        raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
    frame["time"] = pd.to_numeric(frame["time"], errors="coerce")
    for col in ("lat", "lon", "geoaltitude"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    airborne = frame["onground"].astype("string").str.strip().str.lower().isin(("false", "0"))
    usable = frame.loc[airborne].dropna(subset=["icao24", "time", "lat", "lon", "geoaltitude"])
    usable = usable.sort_values(["icao24", "time"]).drop_duplicates(["icao24", "time"], keep="last")
    longest = {}
    for aircraft, rows in usable.groupby("icao24", sort=True):
        rows = rows.sort_values("time")
        times = rows["time"].to_numpy(dtype=np.float64)
        coords = to_enu(rows["lat"], rows["lon"], rows["geoaltitude"])
        for indices in np.split(np.arange(len(rows)), np.flatnonzero(np.diff(times) > max_gap_s) + 1):
            # 16 genuine 10s positions yield 31 positions after 5s interpolation.
            if len(indices) < min_observed_points:
                continue
            if len(indices) > 1 and not np.all(np.diff(times[indices]) <= max_gap_s):
                continue
            if str(aircraft) not in longest or len(indices) > len(longest[str(aircraft)][0]):
                longest[str(aircraft)] = (times[indices], coords[indices])
    return frame, longest


def process_file(path: Path, encoder: FrozenEncoder, cfg: ComplexityConfig, max_gap_s: float):
    match = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2})Z\.csv\.gz$", path.name)
    if not match:
        raise ValueError(f"Unexpected hourly filename: {path.name}")
    scene_id = match.group(1) + "Z"
    min_tokens = int(encoder.preprocess["preprocessing"]["min_points"])
    min_observed = (min_tokens + 1) // 2 + 1
    frame, tracks = hourly_tracks(path, max_gap_s, min_observed)
    vectors, accepted = [], []
    for aircraft, (times, enu) in tracks.items():
        times_5s, enu_5s = resample_10s_to_5s(times, enu)
        encoded = encoder.encode(enu_5s, resample_from_1hz=False)
        vectors.append(encoded["embedding"])
        accepted.append({"icao24": aircraft, "observations": len(times),
                         "start_unix": float(times[0]), "end_unix": float(times[-1]),
                         "duration_seconds": float(times[-1] - times[0]),
                         "encoder_points": int(encoded["n_points"]),
                         "interpolated_points": int(len(times_5s) - len(times))})
    dim = int(encoder.settings["dimension"])
    embeddings = np.stack(vectors).astype(np.float32) if vectors else np.empty((0, dim), dtype=np.float32)
    complexity = estimate_complexity(embeddings, config=cfg, scene_id=scene_id).to_dict()
    valid = frame.dropna(subset=["icao24", "time", "lat", "lon", "geoaltitude"])
    audit = {
        "scene_id": scene_id, "source_file": path.name, "status": complexity["status"],
        "complexity": complexity, "source_rows": int(len(frame)),
        "aircraft_observed": int(frame["icao24"].nunique(dropna=True)),
        "finite_position_altitude_rows": int(len(valid)),
        "encoded_aircraft": len(accepted), "tracks": accepted,
        "observed_sampling_seconds": 10, "encoder_sampling_seconds": 5,
        "resampling": "piecewise-linear ENU between observations; endpoint preserved; no extrapolation",
        "max_segment_gap_seconds": max_gap_s,
        "selection": "longest airborne segment per icao24 within each UTC hour",
        "filters": ["onground=false", "finite lat/lon/geoaltitude/time",
                     f"split when consecutive observations exceed {max_gap_s:g}s",
                     f"at least {min_observed} genuine observations before interpolation"],
    }
    return scene_id, embeddings, audit


def main(argv=None):
    parser = argparse.ArgumentParser(description="Encode hourly OpenSky scenes and estimate Complexity")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "Encoder" / "encoder" / "encoder.pt")
    parser.add_argument("--pattern", default="*.csv.gz")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-gap-seconds", type=float, default=60.0)
    parser.add_argument("--max-pairs", type=int, default=5_000_000)
    args = parser.parse_args(argv)
    if args.max_gap_seconds <= 0:
        parser.error("--max-gap-seconds must be positive")
    sources = sorted(args.input_dir.glob(args.pattern))
    if not sources:
        parser.error(f"no inputs match {args.input_dir / args.pattern}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    encoder = FrozenEncoder(args.checkpoint, pooling="sum", device=args.device)
    cfg = ComplexityConfig(normalize=False, max_pairs=args.max_pairs)
    archive_path = args.output_dir / "hourly_embeddings.npz"
    results, arrays = [], {}
    for i, source in enumerate(sources, 1):
        scene_id, points, audit = process_file(source, encoder, cfg, args.max_gap_seconds)
        arrays[scene_id] = points
        results.append(audit)
        print(f"[{i}/{len(sources)}] {scene_id}: encoded={len(points)} complexity={audit['status']}", flush=True)
    np.savez_compressed(archive_path, **arrays)
    report = {
        "schema_version": 1, "method": "OpenSky hourly tracks -> FrozenEncoder sum -> Complexity",
        "source_dataset": "OpenSky_Changi_2026-09 sampled_10s",
        "source_airport_region": "WSSS; research circle around airport reference point",
        "encoder_training_airport": encoder.preprocess["airport"],
        "encoder_checkpoint": str(args.checkpoint),
        "preprocessor_id": encoder.preprocess["preprocessor_id"],
        "warnings": ["Domain shift: WSSS input differs from RKSI encoder training data.",
                       "10s observations are linearly interpolated to 5s; intermediate positions are estimates, not observations.",
                       "Up uses geometric altitude against airport elevation; vertical datum may differ.",
                       "OpenSky coverage is incomplete; inferred flight metadata is not used as ground truth.",
                       "Complexity is reported only when the existing estimator quality gates pass."],
        "output_embeddings": archive_path.name, "scene_count": len(results),
        "complexity_ok_scenes": sum(r["status"] == "ok" for r in results),
        "results": results,
    }
    report_path = args.output_dir / "hourly_complexity.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {archive_path} and {report_path}", flush=True)


if __name__ == "__main__":
    main()
