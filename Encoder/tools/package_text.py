"""Export current Encoder text sources and model metadata as JSON."""
import argparse
import json
import sys
from package_delivery import delivery_paths, archive_name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    paths = [p for p in delivery_paths()
             if p.suffix in (".py", ".md", ".json", ".txt")]
    if args.list:
        print(json.dumps([archive_name(p) for p in paths], indent=2))
        return
    records = [{"path": archive_name(p), "mode": "100644", "type": "blob",
                "content": p.read_text(encoding="utf-8-sig")} for p in paths]
    print(json.dumps(records, ensure_ascii=False))


if __name__ == "__main__":
    main()
