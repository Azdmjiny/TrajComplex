#!/usr/bin/env python3
"""Encode trajectory .npy files into one scene embedding array.

Run from the repository root with: python encode_scene.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from Encoder.trajectory_encoder.inference import FrozenEncoder


def main() -> int:
    repo_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Encode trajectories in one folder into scene embeddings."
    )
    parser.add_argument(
        "--input-dir", type=Path, default=repo_root / "trajectories",
        help="folder of per-aircraft .npy ENU trajectory files (default: trajectories/)",
    )
    parser.add_argument(
        "--output", type=Path, default=repo_root / "artifacts/scene_001_embeddings.npy",
        help="output .npy path (default: artifacts/scene_001_embeddings.npy)",
    )
    parser.add_argument(
        "--checkpoint", type=Path, default=repo_root / "Encoder/encoder/encoder.pt",
        help="trained Encoder checkpoint path",
    )
    parser.add_argument(
        "--device", default="cpu", help="PyTorch device (default: cpu)"
    )
    args = parser.parse_args()

    input_dir = args.input_dir if args.input_dir.is_absolute() else repo_root / args.input_dir
    output = args.output if args.output.is_absolute() else repo_root / args.output
    checkpoint = (
        args.checkpoint if args.checkpoint.is_absolute() else repo_root / args.checkpoint
    )

    if not input_dir.is_dir():
        parser.error(f"trajectory input directory does not exist: {input_dir}")
    if not checkpoint.is_file():
        parser.error(f"Encoder checkpoint does not exist: {checkpoint}")
    paths = sorted(input_dir.glob("*.npy"))
    if not paths:
        parser.error(f"no .npy trajectory files found in: {input_dir}")

    encoder = FrozenEncoder(checkpoint, pooling="sum", device=args.device)
    vectors = []
    for path in paths:
        try:
            enu_m = np.load(path, allow_pickle=False)
            result = encoder.encode(enu_m)
        except Exception as exc:
            parser.error(f"failed to encode {path}: {exc}")
        vectors.append(result["embedding"])

    scene_embeddings = np.stack(vectors)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.save(output, scene_embeddings)
    print(f"Encoded {len(paths)} trajectories; saved {scene_embeddings.shape} to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
