"""Train an airport-specific checkpoint using the original month-stratified splits."""

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path

from eval._training import MODEL, SPLITS, read_training, sample_rank, train

TARGETS = {"train": 22386, "val": 2821, "test": 2730}


def select_trajectories(index, airport, months):
    grouped = defaultdict(lambda: defaultdict(list))
    samples, flights = set(), set()
    with index.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            month, sample = row["month"], row["sample_id"]
            if row["airport"] != airport or month not in months:
                raise ValueError(f"Unexpected airport or month in {index}")
            flight = (row["icao24"], row["firstseen"], row["lastseen"])
            if sample in samples or flight in flights:
                raise ValueError(f"Duplicate sample or flight in {index}")
            samples.add(sample)
            flights.add(flight)
            if len(range(0, int(row["resampled_length"]), 10)) >= 30:
                grouped[SPLITS[row["split"]]][month].append(sample)

    selected = {}
    for split, target in TARGETS.items():
        by_month = grouped[split]
        n_available = sum(map(len, by_month.values()))
        if n_available < target:
            raise ValueError(f"Too few eligible {airport} {split} trajectories")
        quotas = {month: len(ids) * target // n_available for month, ids in by_month.items()}
        priority = sorted(by_month, key=lambda m: (-(len(by_month[m]) * target % n_available), m))
        for month in priority[:target - sum(quotas.values())]:
            quotas[month] += 1
        for month, ids in by_month.items():
            ranked = sorted(ids, key=lambda sample: (sample_rank(sample), sample))
            selected.update((sample, (split, month)) for sample in ranked[:quotas[month]])
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("airport", choices=("RJTT", "WMKK", "RKSI"))
    parser.add_argument("--source", type=Path, required=True, help="Cleaned training archive directory")
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("--output must be a new directory")

    airport = args.airport
    manifest = json.loads((args.source / "manifest.json").read_text(encoding="utf-8-sig"))
    origin = manifest["airports"][airport]
    if manifest["sampling_interval_s"] != 1 or origin["rmax_m"] != 120000:
        raise ValueError("Expected 1 Hz coordinates scaled by 120,000 m")
    selected = select_trajectories(args.source / f"{airport}_INDEX.csv", airport,
                                   manifest["months_per_airport"][airport])
    tracks = read_training(args.source / f"{airport}_CLEANED.jsonl.gz", airport, selected)
    preprocess = {"origin": dict(lat=origin["lat"], lon=origin["lon"], elevation_m=origin["elev_m"])}
    args.output.mkdir(parents=True)
    train(tracks, airport, 16, MODEL, preprocess, args.output / f"{airport}_encoder_60.pt")


if __name__ == "__main__":
    main()
