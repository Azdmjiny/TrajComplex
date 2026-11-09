"""Prepare hourly WSSS scenes and encode them with the frozen trajectory model."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import platform
from pathlib import Path
import sys
import zipfile

import numpy as np


HERE = Path(__file__).resolve().parent
EXPERIMENT_CONFIG = json.loads(r'''
{
  "schema_version": 1,
  "experiment": "Experiment IV-A: sample-size sensitivity within hourly Changi arrival scenes",
  "airport": "WSSS",
  "local_timezone": "Asia/Singapore",
  "utc_offset_hours": 8,
  "local_date_start": "2026-09-01",
  "local_date_end_exclusive": "2026-10-01",
  "data": {
    "expected_sha256": "568556ab1924b8228bc189b933e2cb483d0c6f933a9e2cade95b747c5fe9c6db",
    "hour_member_prefix": "WSSS/hours/",
    "integrity_manifest_member": "WSSS/output_hashes.json",
    "expected_source_fragments": 16899,
    "minimum_source_points": 25,
    "minimum_encoder_points": 30,
    "sample_interval_seconds": 10
  },
  "encoder": {
    "checkpoint_epoch": 60,
    "checkpoint_sha256": "c0d98e6cde14baf99d28b7d336c282eb245f1ce485c248c32a58fd9ccf5358e5",
    "training_airport": "WSSS",
    "dimensions": 16,
    "pooling": "sum",
    "post_pooling_normalization": false,
    "preprocessor_id": "cee1251c8b373994d009bcda89ee14811623849e762f858b0abe0bb7fbd5b8a5"
  },
  "sampling": {
    "orders_per_hour": 20,
    "seed_base": 20261026,
    "start_n": 5,
    "seed_rule": "seed_base plus the chronological one-based index among all 720 hours; hours below start_n still occupy an index"
  },
  "estimator": {
    "metric": "euclidean",
    "strict_pair_rule": "distance < radius",
    "eligible_correlation_sum": "0 < C(r) < 1",
    "minimum_scales": 2,
    "fit_quality_gate": false,
    "radii": [
      0.21153999267980197,
      0.23823095699572105,
      0.26828964184093024,
      0.3021409678525847,
      0.34026346983989136,
      0.3831960615283777,
      0.43154565384275434,
      0.48599573442322275,
      0.5473160296584303,
      0.6163733858211284,
      0.6941440231262737,
      0.7817273359394488,
      0.8803614342204328,
      0.9914406459014895,
      1.116535227620434,
      1.2574135624466645,
      1.416067158395385,
      1.594738801118217,
      1.7959542587470096,
      2.0225579870821875,
      2.277753339867326,
      2.5651478525772102,
      2.888804239867669,
      3.253297827605916,
      3.6637812313617357,
      4.126057195678469,
      4.646660623806555,
      5.232950957502158,
      5.893216212805728,
      6.636790142488538,
      7.474184181418739,
      8.417236040075169,
      9.479277046781531,
      10.67532060427246,
      12.02227442468279,
      13.539179543192013,
      15.247479489108866,
      17.171323419497597,
      19.337907500554326,
      21.77785936262659,
      24.52567106367366,
      27.62018668169839,
      31.105151428937027,
      35.02983005028733,
      39.44970324788248,
      44.42725197672555,
      50.03284069847627,
      56.34571207939035,
      63.45510719382841,
      71.46152706894364,
      80.47815340420767,
      90.63244854959012,
      102.06795736027215,
      114.9463363995747,
      129.44963917566295,
      145.78288971697359,
      164.176980867374,
      184.89193827242252,
      208.22059619764116,
      234.492737141519,
      264.07975376234367,
      297.3998990215735,
      334.9241987617081,
      377.183110301039
    ],
    "radius_grid_sha256": "5e2031edb2d4dc75ce4fcdd53712b5c96dda16953c1b2a4c0be422441d1dfa25"
  },
  "display": {
    "paper_range": [
      5,
      35
    ],
    "paper_bins": [
      [
        5,
        6
      ],
      [
        7,
        9
      ],
      [
        10,
        11
      ],
      [
        12,
        14
      ],
      [
        15,
        16
      ],
      [
        17,
        19
      ],
      [
        20,
        22
      ],
      [
        23,
        24
      ],
      [
        25,
        27
      ],
      [
        28,
        29
      ],
      [
        30,
        32
      ],
      [
        33,
        35
      ]
    ],
    "full_range_diagnostic": true,
    "paper_range_selection": "post hoc in the manuscript; retain and report the complete observed n range separately"
  },
  "expected_results": {
    "hours": 720,
    "eligible_fragments": 16308,
    "unique_flights": 14394,
    "eligible_sample_points": 1331063,
    "hours_below_five_fragments": 18,
    "maximum_hourly_fragments": 49,
    "paired_hours_n5_to_n30": 199,
    "paired_median_difference_n30_minus_n5": 0.27016854949001057,
    "paired_increased_hours": 170,
    "paired_decreased_hours": 29,
    "paired_tied_hours": 0
  },
  "cached_embeddings": {
    "file": "embeddings.npz",
    "sha256": "ebd584789ceacba58be9444c926be7d6450d27f8e14d4d969c5e95eb24931d5d"
  }
}
''')
REPO_ROOT = HERE.parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path | None = None) -> dict:
    if path is None:
        return json.loads(json.dumps(EXPERIMENT_CONFIG))
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha256_config(value: dict) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_json(path: Path, value: dict) -> None:
    Path(path).write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _hour_datetime(key: str) -> datetime:
    return datetime.strptime(key, "%Y-%m-%dT%HZ").replace(tzinfo=timezone.utc)


def _string_ids(values: np.ndarray) -> list[str]:
    result = []
    for value in values.tolist():
        if isinstance(value, bytes):
            result.append(value.decode("utf-8"))
        else:
            result.append(str(value))
    return result


def _validate_internal_manifest(archive: zipfile.ZipFile, member: str) -> int:
    manifest = json.loads(archive.read(member).decode("utf-8-sig"))
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError("Archive integrity manifest is empty or malformed")
    checked = 0
    for relative_name, expected_hash in manifest.items():
        normalized = str(relative_name).replace("\\", "/").lstrip("/")
        archive_name = f"WSSS/{normalized}"
        try:
            actual_hash = sha256_bytes(archive.read(archive_name))
        except KeyError as exc:
            raise ValueError(f"Integrity manifest member is missing: {archive_name}") from exc
        if actual_hash.lower() != str(expected_hash).lower():
            raise ValueError(f"Integrity hash mismatch for {archive_name}")
        checked += 1
    return checked


def prepare_archive(
    archive_path: Path,
    output_dir: Path,
    config_path: Path | None = None,
    *,
    enforce_paper_counts: bool = True,
) -> dict:
    """Write one validated NPZ per UTC hour, retaining fragments with >=30 points."""
    config = read_json(config_path)
    data_cfg = config["data"]
    expected_cfg = config["expected_results"]
    archive_path = Path(archive_path).resolve()
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}")
    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)
    archive_hash = sha256_file(archive_path)
    expected_hash = data_cfg.get("expected_sha256")
    if expected_hash and archive_hash != expected_hash:
        raise ValueError("Prepared trajectory archive SHA-256 does not match the experiment protocol")

    output_dir.mkdir(parents=True)
    scene_dir = output_dir / "scenes"
    scene_dir.mkdir()
    rows = []
    all_eligible_ids: set[str] = set()
    source_count = 0
    eligible_count = 0
    eligible_points = 0
    manifest_count = 0
    member_prefix = data_cfg["hour_member_prefix"]
    min_source_points = int(data_cfg["minimum_source_points"])
    min_encoder_points = int(data_cfg["minimum_encoder_points"])
    cadence = int(data_cfg["sample_interval_seconds"])
    local_offset = timedelta(hours=int(config["utc_offset_hours"]))

    with zipfile.ZipFile(archive_path, "r") as archive:
        manifest_member = data_cfg["integrity_manifest_member"]
        if manifest_member not in archive.namelist():
            raise ValueError(f"Missing archive integrity manifest: {manifest_member}")
        manifest_count = _validate_internal_manifest(archive, manifest_member)
        hour_members = sorted(
            name for name in archive.namelist()
            if name.startswith(member_prefix) and name.lower().endswith(".npz")
        )
        if len(hour_members) != int(config["expected_results"]["hours"]):
            raise ValueError(f"Expected 720 hourly NPZ files; found {len(hour_members)}")

        previous_hour = None
        for hour_index, member in enumerate(hour_members, start=1):
            key = Path(member).stem
            hour_utc = _hour_datetime(key)
            if previous_hour is not None and hour_utc - previous_hour != timedelta(hours=1):
                raise ValueError(f"Hourly archive has a gap or duplicate before {key}")
            previous_hour = hour_utc
            local = hour_utc + local_offset
            if not (
                config["local_date_start"]
                <= local.strftime("%Y-%m-%d")
                < config["local_date_end_exclusive"]
            ):
                raise ValueError(f"Hour is outside the configured local month: {key}")
            hour_epoch = int(hour_utc.timestamp())

            with np.load(archive.open(member), allow_pickle=False) as source:
                required = {"enu_m", "time", "offsets", "flight_ids", "traffic_label", "estarrivalairport"}
                missing = required.difference(source.files)
                if missing:
                    raise ValueError(f"{member} is missing fields: {sorted(missing)}")
                positions = np.asarray(source["enu_m"], dtype=np.float64)
                times = np.asarray(source["time"], dtype=np.float64)
                offsets = np.asarray(source["offsets"], dtype=np.int64)
                ids = _string_ids(np.asarray(source["flight_ids"]))
                labels = np.asarray(source["traffic_label"]).astype(str)
                arrivals = np.asarray(source["estarrivalairport"]).astype(str)
                departures = (
                    np.asarray(source["estdepartureairport"]).astype(str)
                    if "estdepartureairport" in source.files else None
                )

            if positions.ndim != 2 or positions.shape[1] != 3 or len(times) != len(positions):
                raise ValueError(f"Invalid position/time arrays in {member}")
            if len(offsets) != len(ids) + 1 or len(offsets) < 1:
                raise ValueError(f"Invalid track offsets in {member}")
            if offsets[0] != 0 or offsets[-1] != len(times) or np.any(np.diff(offsets) < min_source_points):
                raise ValueError(f"Invalid source trajectory lengths in {member}")
            if len(set(ids)) != len(ids):
                raise ValueError(f"Duplicate flight IDs within {key}")
            if len(labels) != len(ids) or np.any(labels != "arrival"):
                raise ValueError(f"Non-arrival or misaligned flight labels in {member}")
            if len(arrivals) != len(ids) or np.any(arrivals != config["airport"]):
                raise ValueError(f"Arrival-airport mismatch in {member}")
            if departures is not None and (len(departures) != len(ids) or np.any(departures == config["airport"])):
                raise ValueError(f"Departure-airport filter mismatch in {member}")
            if not np.isfinite(positions).all() or not np.isfinite(times).all():
                raise ValueError(f"Non-finite trajectory input in {member}")
            if np.any(times < hour_epoch) or np.any(times >= hour_epoch + 3600):
                raise ValueError(f"Trajectory time is outside its UTC hour in {member}")

            lengths = np.diff(offsets)
            source_count += len(ids)
            eligible_indices = []
            for index, (start, stop) in enumerate(zip(offsets[:-1], offsets[1:])):
                track_times = times[start:stop]
                if np.any(np.diff(track_times) != cadence):
                    raise ValueError(f"Non-{cadence}-second sampling in {member}, trajectory {index}")
                if lengths[index] >= min_encoder_points:
                    eligible_indices.append(index)

            selected_positions = []
            selected_times = []
            selected_ids = []
            selected_lengths = []
            for index in eligible_indices:
                start, stop = int(offsets[index]), int(offsets[index + 1])
                selected_positions.append(positions[start:stop])
                selected_times.append(times[start:stop])
                selected_ids.append(ids[index])
                selected_lengths.append(int(lengths[index]))

            if selected_positions:
                packed_positions = np.concatenate(selected_positions, axis=0)
                packed_times = np.concatenate(selected_times)
                packed_offsets = np.concatenate(([0], np.cumsum(selected_lengths))).astype(np.int64)
            else:
                packed_positions = np.empty((0, 3), dtype=np.float64)
                packed_times = np.empty((0,), dtype=np.float64)
                packed_offsets = np.array([0], dtype=np.int64)

            destination = scene_dir / f"{key}.npz"
            np.savez_compressed(
                destination,
                # Preserve the archive's coordinates; the inference API converts them to float64.
                enu_m=packed_positions,
                time=packed_times,
                offsets=packed_offsets,
                flight_ids=np.asarray(selected_ids, dtype="U"),
                n_points=np.asarray(selected_lengths, dtype=np.int32),
            )
            eligible_count += len(selected_ids)
            eligible_points += int(sum(selected_lengths))
            all_eligible_ids.update(selected_ids)
            rows.append({
                "key": key,
                "hour_utc": hour_epoch,
                "local_date": local.strftime("%Y-%m-%d"),
                "local_hour": int(local.strftime("%H")),
                "source_fragments": len(ids),
                "excluded_below_30": len(ids) - len(selected_ids),
                "N": len(selected_ids),
                "unique_flights": len(set(selected_ids)),
                "eligible_points": int(sum(selected_lengths)),
                "scene_file": f"scenes/{key}.npz",
                "scene_sha256": sha256_file(destination),
            })
            if hour_index % 120 == 0:
                print(f"validated {hour_index}/720 hours", flush=True)

    summary = {
        "schema_version": 1,
        "source_archive_sha256": archive_hash,
        "integrity_manifest_entries_verified": manifest_count,
        "hours": len(rows),
        "source_fragments": source_count,
        "excluded_below_30": source_count - eligible_count,
        "eligible_fragments": eligible_count,
        "unique_flights": len(all_eligible_ids),
        "eligible_sample_points": eligible_points,
        "hours_below_five_fragments": sum(row["N"] < 5 for row in rows),
        "maximum_hourly_fragments": max((row["N"] for row in rows), default=0),
        "rows": rows,
    }
    if enforce_paper_counts:
        expected = {
            "hours": int(expected_cfg["hours"]),
            "source_fragments": int(data_cfg["expected_source_fragments"]),
            "excluded_below_30": int(data_cfg["expected_source_fragments"] - expected_cfg["eligible_fragments"]),
            "eligible_fragments": int(expected_cfg["eligible_fragments"]),
            "unique_flights": int(expected_cfg["unique_flights"]),
            "eligible_sample_points": int(expected_cfg["eligible_sample_points"]),
            "hours_below_five_fragments": int(expected_cfg["hours_below_five_fragments"]),
            "maximum_hourly_fragments": int(expected_cfg["maximum_hourly_fragments"]),
        }
        mismatches = {
            key: {"expected": value, "actual": summary[key]}
            for key, value in expected.items() if summary[key] != value
        }
        if mismatches:
            raise ValueError(f"Prepared data do not match the paper protocol: {mismatches}")
    write_json(output_dir / "scene-index.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))
    return summary


def encode_prepared_scenes(
    prepared_dir: Path,
    checkpoint_path: Path,
    output_dir: Path,
    config_path: Path | None = None,
    *,
    device: str = "auto",
) -> dict:
    config = read_json(config_path)
    prepared_dir = Path(prepared_dir).resolve()
    checkpoint_path = Path(checkpoint_path).resolve()
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}")
    scene_index_path = prepared_dir / "scene-index.json"
    if not scene_index_path.is_file() or not checkpoint_path.is_file():
        raise FileNotFoundError("Prepared scene index or encoder checkpoint is missing")
    scene_index = read_json(scene_index_path)
    checkpoint_hash = sha256_file(checkpoint_path)
    encoder_cfg = config["encoder"]
    if checkpoint_hash != encoder_cfg["checkpoint_sha256"]:
        raise ValueError("Checkpoint SHA-256 does not match the epoch-60 paper checkpoint")

    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        import torch
        from Encoder.trajectory_encoder.inference import FrozenEncoder
    except ImportError as exc:
        raise RuntimeError("Encoding requires the repository dependencies, including PyTorch") from exc

    state = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if int(state.get("epoch", -1)) != int(encoder_cfg["checkpoint_epoch"]):
        raise ValueError("Checkpoint epoch does not match embedded experiment protocol")
    settings = state.get("settings", {})
    preprocess = state.get("preprocess", {})
    if int(settings.get("dimension", -1)) != int(encoder_cfg["dimensions"]):
        raise ValueError("Checkpoint embedding dimension does not match embedded experiment protocol")
    if preprocess.get("airport") != encoder_cfg["training_airport"]:
        raise ValueError("Checkpoint training airport does not match embedded experiment protocol")
    if preprocess.get("preprocessor_id") != encoder_cfg["preprocessor_id"]:
        raise ValueError("Checkpoint preprocessor ID does not match embedded experiment protocol")
    torch.set_num_threads(2)
    torch.manual_seed(43)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    encoder = FrozenEncoder(checkpoint_path, pooling="sum", device=device)
    if encoder.model.training or any(parameter.requires_grad for parameter in encoder.model.parameters()):
        raise RuntimeError("Encoder must be frozen and in evaluation mode")
    if encoder.preprocess["preprocessor_id"] != encoder_cfg["preprocessor_id"]:
        raise ValueError("Loaded encoder preprocessing does not match the published model")

    output_dir.mkdir(parents=True)
    arrays = {}
    rows = []
    for index, row in enumerate(scene_index["rows"], start=1):
        scene_path = prepared_dir / row["scene_file"]
        if sha256_file(scene_path) != row["scene_sha256"]:
            raise ValueError(f"Prepared scene changed after validation: {row['key']}")
        with np.load(scene_path, allow_pickle=False) as scene:
            positions = scene["enu_m"]
            offsets = scene["offsets"]
            ids = scene["flight_ids"]
            n_points = scene["n_points"]
            embeddings = []
            for start, stop in zip(offsets[:-1], offsets[1:]):
                result = encoder.encode(positions[int(start):int(stop)])
                vector = np.asarray(result["embedding"], dtype=np.float32)
                if result.get("pooling") != encoder_cfg["pooling"]:
                    raise ValueError("FrozenEncoder returned an unexpected temporal pooling mode")
                if vector.shape != (int(encoder_cfg["dimensions"]),) or not np.isfinite(vector).all():
                    raise ValueError(f"Invalid embedding for {row['key']}")
                if int(result["n_points"]) < int(config["data"]["minimum_encoder_points"]):
                    raise ValueError(f"Encoder accepted a short trajectory in {row['key']}")
                embeddings.append(vector)
            vectors = np.asarray(embeddings, dtype=np.float32).reshape(-1, int(encoder_cfg["dimensions"]))
            if len(vectors) != int(row["N"]) or len(ids) != len(vectors) or len(n_points) != len(vectors):
                raise ValueError(f"Embedding count differs from scene manifest: {row['key']}")
        arrays[row["key"]] = vectors
        rows.append({
            key: row[key] for key in (
                "key", "hour_utc", "local_date", "local_hour", "source_fragments",
                "excluded_below_30", "N", "unique_flights", "eligible_points",
            )
        })
        if index % 120 == 0:
            print(f"encoded {index}/720 hours", flush=True)

    embedding_path = output_dir / "embeddings.npz"
    np.savez_compressed(embedding_path, **arrays)
    metadata = {
        "schema_version": 1,
        "airport": config["airport"],
        "local_date_start": config["local_date_start"],
        "local_date_end_exclusive": config["local_date_end_exclusive"],
        "total_embeddings": int(sum(row["N"] for row in rows)),
        "source_fragments": int(scene_index["source_fragments"]),
        "excluded_below_30": int(scene_index["excluded_below_30"]),
        "unique_flights": int(scene_index["unique_flights"]),
        "eligible_sample_points": int(scene_index["eligible_sample_points"]),
        "source_archive_sha256": scene_index["source_archive_sha256"],
        "prepared_scene_index_sha256": sha256_file(scene_index_path),
        "checkpoint_epoch": int(encoder_cfg["checkpoint_epoch"]),
        "checkpoint_sha256": checkpoint_hash,
        "training_airport": encoder_cfg["training_airport"],
        "dimensions": int(encoder_cfg["dimensions"]),
        "pooling": encoder_cfg["pooling"],
        "post_pooling_normalization": bool(encoder_cfg["post_pooling_normalization"]),
        "preprocessor_id": encoder.preprocess["preprocessor_id"],
        "embedding_archive_sha256": sha256_file(embedding_path),
        "device": str(device),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "rows": rows,
    }
    write_json(output_dir / "encoding-summary.json", metadata)
    return metadata
