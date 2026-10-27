"""Emit publishable UTF-8 source/records; never reads raw TSV or model arrays."""
import argparse
import json
import sys
from package_delivery import ROOT, delivery_paths, archive_name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--final", action="store_true", help="also include local runs' JSON/log records")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    paths = [p for p in delivery_paths(include_runs=args.final)
             if p.suffix in (".py", ".md", ".json", ".txt", ".log") or p.name == ".gitignore"]
    if args.list:
        print(json.dumps([archive_name(p) for p in paths], indent=2))
        return
    records = []
    for path in paths:
        content = path.read_text(encoding="utf-8-sig")
        if path.name == "public_data_verification.json":
            value = json.loads(content)
            value.pop("user_publication_instruction", None)
            content = json.dumps(value, indent=2)
        records.append({"path": archive_name(path), "mode": "100644", "type": "blob", "content": content})
    print(json.dumps(records, ensure_ascii=False))


if __name__ == "__main__":
    main()
