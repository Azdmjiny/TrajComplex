"""Package the current frozen Encoder, inference sources and dependencies."""
import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trajectory_encoder.common import file_hash


def delivery_paths():
    paths = [ROOT / name for name in
             ("README.md", "example.py", "verify_delivery.py")]
    paths.append(ROOT.parent / "requirements.txt")
    for directory in ("trajectory_encoder", "tools", "encoder"):
        paths.extend(p for p in (ROOT / directory).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts
                     and p.suffix not in (".pyc", ".pyo"))
    paths = sorted(set(paths))
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    return paths


def archive_name(path):
    return path.relative_to(ROOT.parent).as_posix()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list files without writing a ZIP")
    parser.add_argument("--output", type=Path, default=ROOT / "encoder_delivery.zip",
                        help="new ZIP path; relative paths use the working directory")
    args = parser.parse_args()
    paths = delivery_paths()
    if args.list:
        print(json.dumps([archive_name(p) for p in paths], indent=2))
        return
    with zipfile.ZipFile(args.output, "x", zipfile.ZIP_DEFLATED, compresslevel=5) as output:
        for path in paths:
            output.write(path, archive_name(path))
    print(json.dumps({"filename": str(args.output), "bytes": args.output.stat().st_size,
                      "sha256": file_hash(args.output), "files": len(paths)}, indent=2))


if __name__ == "__main__":
    main()
