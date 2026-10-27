"""Inventory/package Encoder sources and evidence; raw data stays local."""
import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trajectory_encoder.common import read_json, write_json, file_hash

EXCLUDED = {"blob_receipts.json", "early_export_manifest.json", "pipeline_status.json",
            "completion_status.json", "artifact_transfer_checks.json", "repository_delivery.json",
            "delivery_archive.json"}


def delivery_paths(include_runs=False):
    top = ["README.md", "CITATION.md", "THIRD_PARTY_LICENSE_ATSCC.md", "config.json",
           ".gitignore", "example.py", "verify_delivery.py"]
    paths = [ROOT / name for name in top]
    paths.extend(ROOT.parent / name for name in ("README.md", "requirements.txt"))
    directories = ["trajectory_encoder", "tools", "encoder", "archive"]
    if include_runs:
        directories.extend(("reports", "checkpoints"))
    for directory in directories:
        paths.extend(p for p in (ROOT / directory).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts
                     and p.suffix not in (".pyc", ".writing") and p.name not in EXCLUDED)
    if include_runs and (ROOT / "runs").is_dir():
        paths.extend(p for p in (ROOT / "runs").glob("*/*")
                     if p.is_file() and p.suffix in (".json", ".log"))
    return sorted(set(paths))


def archive_name(path):
    return path.relative_to(ROOT.parent).as_posix()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="show the file inventory without writing a ZIP")
    args = parser.parse_args()
    paths = delivery_paths(include_runs=True)
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    if args.list:
        print(json.dumps([archive_name(p) for p in paths], indent=2))
        return
    # Preserve the legacy completion prerequisite. Archived logs are not live training state.
    status_path = ROOT / "reports" / "completion_status.json"
    if not status_path.is_file() or read_json(status_path).get("state") != "complete":
        raise RuntimeError("Packaging requires completed local training state in Encoder/reports/completion_status.json; use --list to inspect the saved delivery")
    archive = ROOT / "encoder_delivery.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=5) as output:
        for path in paths:
            name = archive_name(path)
            if path.name == "public_data_verification.json":
                value = read_json(path)
                value.pop("user_publication_instruction", None)
                output.writestr(name, json.dumps(value, indent=2))
            else:
                output.write(path, name)
    result = {"filename": archive.name, "bytes": archive.stat().st_size,
              "sha256": file_hash(archive), "files": len(paths),
              "raw_TSV_included": False, "optimizer_states_included": False}
    write_json(ROOT / "reports" / "delivery_archive.json", result)
    print(result)


if __name__ == "__main__":
    main()
