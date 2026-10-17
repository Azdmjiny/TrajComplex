"""Run from the workspace root: python -m Complexity scene.npy -o result.json."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

from .calculator import ComplexityConfig, estimate_complexity


def main(argv=None):
    parser = argparse.ArgumentParser(description="Estimate correlation dimension of pooled scene embeddings")
    parser.add_argument("input", type=Path, help=".npy: one (N,D) scene; .npz: scene_id -> (N,D)")
    parser.add_argument("-o", "--output", type=Path, help="JSON file; default stdout")
    parser.add_argument("--normalize", action="store_true", help="L2 normalize each embedding before Euclidean distance")
    parser.add_argument("--fit-range", nargs=2, type=float, metavar=("R_MIN", "R_MAX"))
    parser.add_argument("--min-samples", type=int, default=30)
    parser.add_argument("--n-radii", type=int, default=64)
    parser.add_argument("--min-r-squared", type=float, default=0.98)
    parser.add_argument("--max-pairs", type=int, default=5_000_000)
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.resolve() == args.input.resolve():
            raise ValueError("output must not overwrite input")
        cfg = ComplexityConfig(
            normalize=args.normalize, min_samples=args.min_samples,
            n_radii=args.n_radii, min_r_squared=args.min_r_squared, max_pairs=args.max_pairs,
        )
        suffix = args.input.suffix.lower()
        if suffix not in (".npy", ".npz"):
            raise ValueError("input must be .npy or .npz (pickle is not accepted)")
        results = []
        if suffix == ".npy":
            scenes = [(args.input.stem, np.load(args.input, allow_pickle=False))]
            for scene_id, points in scenes:
                results.append(estimate_complexity(
                    points, config=cfg, fit_range=args.fit_range, scene_id=scene_id,
                ).to_dict())
        else:
            with np.load(args.input, allow_pickle=False) as scenes:
                if not scenes.files:
                    raise ValueError("input archive contains no scenes")
                for scene_id in scenes.files:
                    try:
                        results.append(estimate_complexity(
                            scenes[scene_id], config=cfg, fit_range=args.fit_range, scene_id=scene_id,
                        ).to_dict())
                    except ValueError as exc:
                        raise ValueError(f"scene {scene_id!r}: {exc}") from exc
        payload = {
            "schema_version": 1,
            "method": "empirical_correlation_dimension",
            "metric": "euclidean",
            "input": str(args.input),
            "results": results,
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
    except (ValueError, OSError, TypeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
