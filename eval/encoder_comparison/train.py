"""Train the Changi embedding-dimension and training-month variants."""

import argparse
from collections import Counter
from pathlib import Path

import numpy as np
import torch

from eval._training import read_training, sample_rank, train, training_statistics

MONTHS = ("2025-03", "2025-04", "2025-05")
MONTH_TARGETS = {"train": 4522, "val": 566, "test": 521}
VARIANTS = {
    "pooled_d8": ("pooled", 8), "pooled_d32": ("pooled", 32),
    **{f"{month}_d16": (month, 16) for month in MONTHS},
}


def matched_month(tracks, month):
    selected = set()
    for split, count in MONTH_TARGETS.items():
        indices = [i for i, track in enumerate(tracks) if track.month == month and track.split == split]
        if len(indices) < count:
            raise ValueError(f"Too few {month} {split} trajectories")
        indices.sort(key=lambda i: (sample_rank(tracks[i].sample_id), i))
        selected.update(indices[:count])
    return [tracks[index] for index in sorted(selected)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="WSSS_CLEANED.jsonl.gz")
    parser.add_argument("--baseline", type=Path, required=True, help="Original 16-D epoch-60 checkpoint")
    parser.add_argument("--output", type=Path, required=True, help="New directory for variant checkpoints")
    parser.add_argument("--run", choices=VARIANTS, help="Train one variant instead of all five")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("--output must be a new directory")

    baseline = torch.load(args.baseline, map_location="cpu", weights_only=True)
    settings = baseline["settings"]
    if (baseline["epoch"] != 60 or settings["dimension"] != 16 or settings["pooling"] != "sum"
            or baseline["preprocess"]["airport"] != "WSSS"):
        raise ValueError("Expected the original WSSS 16-D epoch-60 baseline")
    tracks = read_training(args.source, "WSSS")
    if (Counter(track.split for track in tracks) != {"train": 22386, "val": 2821, "test": 2730}
            or set(track.month for track in tracks) != set(MONTHS)):
        raise ValueError("Expected the original March–May 2025 split")
    mean, std = training_statistics(tracks)
    np.testing.assert_allclose(mean, baseline["preprocess"]["mean"], rtol=1e-10, atol=1e-7)
    np.testing.assert_allclose(std, baseline["preprocess"]["std"], rtol=1e-10, atol=1e-7)

    args.output.mkdir(parents=True)
    for name in [args.run] if args.run else VARIANTS:
        group, dimension = VARIANTS[name]
        data = tracks if group == "pooled" else matched_month(tracks, group)
        train(data, "WSSS", dimension, settings["model"], {},
              args.output / name / "epoch_60.pt", tf32=True)


if __name__ == "__main__":
    main()
