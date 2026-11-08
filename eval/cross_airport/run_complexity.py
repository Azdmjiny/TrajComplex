"""Estimate hourly arrival D with the airport-specific epoch-60 encoders."""

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from pyproj import Transformer

from eval._hourly import HourlyEncoder, configure_inference, load_plan, score_month

AIRPORTS = ("WSSS", "RJTT", "WMKK", "RKSI")


def enu_frame(origin, ecef):
    lat, lon, height = (origin[key] for key in ("lat", "lon", "elevation_m"))
    phi, lam = np.deg2rad([lat, lon])
    s, c, u, v = np.sin(phi), np.cos(phi), np.sin(lam), np.cos(lam)
    rotation = np.array([[-u, v, 0], [-s * v, -s * u, c], [c * v, c * u, s]])
    return np.array(ecef.transform(lon, lat, height)), rotation


def rebase_enu(source, target):
    ecef = Transformer.from_crs(4979, 4978, always_xy=True)
    a, ar = enu_frame(source, ecef)
    b, br = enu_frame(target, ecef)
    return ar @ br.T, (a - b) @ br.T


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True, help="Root of the prepared airport directories")
    parser.add_argument("--checkpoints", type=Path, required=True, help="Directory of the four epoch-60 checkpoints")
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("--output must be a new directory")

    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    configure_inference()
    torch.use_deterministic_algorithms(True)
    frames = []
    for airport in AIRPORTS:
        directory = args.prepared / airport
        plan = load_plan(directory, airport)
        filename = "epoch_60.pt" if airport == "WSSS" else f"{airport}_encoder_60.pt"
        encoder = HourlyEncoder(args.checkpoints / filename, airport, 16, args.device)
        rules = json.loads((directory / "cleaning_rules.json").read_text(encoding="utf-8-sig"))
        origin = rules["origin"]
        target = encoder.preprocess.get("origin")
        if target is None and airport != "WSSS":
            raise ValueError(f"{airport} checkpoint is missing its training ENU origin")
        frames.append(score_month(directory, plan, encoder, rebase_enu(origin, target or origin)))
        del encoder
        print(f"Scored {airport}: {len(plan)} hours", flush=True)

    hourly = pd.concat(frames, ignore_index=True)
    summary = hourly.groupby("airport", sort=False).dimension.agg(
        total_hours="size", computed_D_hours="count", median_D="median",
        Q05=lambda scores: scores.quantile(.05), Q25=lambda scores: scores.quantile(.25),
        Q75=lambda scores: scores.quantile(.75), Q95=lambda scores: scores.quantile(.95),
    )
    args.output.mkdir(parents=True)
    hourly.to_csv(args.output / "hourly_D.csv", index=False)
    summary.to_csv(args.output / "airport_summary.csv")


if __name__ == "__main__":
    main()
