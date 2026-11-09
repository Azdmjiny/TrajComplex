"""Validate the prepared WSSS arrival archive and select encoder-eligible tracks."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np


HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "config.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


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
    config_path: Path = DEFAULT_CONFIG,
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
        raise ValueError("Prepared trajectory archive SHA-256 does not match config.json")

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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True, help="Audited ZIP containing WSSS hourly trajectory arrays")
    parser.add_argument("--output", type=Path, required=True, help="New output directory for selected scene arrays")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    prepare_archive(args.archive, args.output, args.config)


if __name__ == "__main__":
    main()
