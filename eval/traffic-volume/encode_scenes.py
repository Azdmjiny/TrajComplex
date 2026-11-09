"""Encode prepared WSSS trajectory scenes with the frozen epoch-60 model."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import sys

import numpy as np

from prepare_scenes import DEFAULT_CONFIG, read_json, sha256_file, write_json


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]


def encode_prepared_scenes(
    prepared_dir: Path,
    checkpoint_path: Path,
    output_dir: Path,
    config_path: Path = DEFAULT_CONFIG,
    *,
    device: str = "auto",
) -> dict:
    config = read_json(config_path)
    prepared_dir = Path(prepared_dir).resolve()
    checkpoint_path = Path(checkpoint_path).resolve()
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}")
    scene_index_path = prepared_dir / "scene-index.json"
    if not scene_index_path.is_file() or not checkpoint_path.is_file():
        raise FileNotFoundError("Prepared scene index or encoder checkpoint is missing")
    scene_index = read_json(scene_index_path)
    checkpoint_hash = sha256_file(checkpoint_path)
    encoder_cfg = config["encoder"]
    if checkpoint_hash != encoder_cfg["checkpoint_sha256"]:
        raise ValueError("Checkpoint SHA-256 does not match the epoch-60 paper checkpoint")

    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        import torch
        from Encoder.trajectory_encoder.inference import FrozenEncoder
    except ImportError as exc:
        raise RuntimeError("Encoding requires the repository dependencies, including PyTorch") from exc

    state = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if int(state.get("epoch", -1)) != int(encoder_cfg["checkpoint_epoch"]):
        raise ValueError("Checkpoint epoch does not match config.json")
    settings = state.get("settings", {})
    preprocess = state.get("preprocess", {})
    if int(settings.get("dimension", -1)) != int(encoder_cfg["dimensions"]):
        raise ValueError("Checkpoint embedding dimension does not match config.json")
    if preprocess.get("airport") != encoder_cfg["training_airport"]:
        raise ValueError("Checkpoint training airport does not match config.json")
    if preprocess.get("preprocessor_id") != encoder_cfg["preprocessor_id"]:
        raise ValueError("Checkpoint preprocessor ID does not match config.json")
    torch.set_num_threads(2)
    torch.manual_seed(43)
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    encoder = FrozenEncoder(checkpoint_path, pooling="sum", device=device)
    if encoder.model.training or any(parameter.requires_grad for parameter in encoder.model.parameters()):
        raise RuntimeError("Encoder must be frozen and in evaluation mode")
    if encoder.preprocess["preprocessor_id"] != encoder_cfg["preprocessor_id"]:
        raise ValueError("Loaded encoder preprocessing does not match the published model")

    output_dir.mkdir(parents=True)
    arrays = {}
    rows = []
    for index, row in enumerate(scene_index["rows"], start=1):
        scene_path = prepared_dir / row["scene_file"]
        if sha256_file(scene_path) != row["scene_sha256"]:
            raise ValueError(f"Prepared scene changed after validation: {row['key']}")
        with np.load(scene_path, allow_pickle=False) as scene:
            positions = scene["enu_m"]
            offsets = scene["offsets"]
            ids = scene["flight_ids"]
            n_points = scene["n_points"]
            embeddings = []
            for start, stop in zip(offsets[:-1], offsets[1:]):
                result = encoder.encode(positions[int(start):int(stop)])
                vector = np.asarray(result["embedding"], dtype=np.float32)
                if result.get("pooling") != encoder_cfg["pooling"]:
                    raise ValueError("FrozenEncoder returned an unexpected temporal pooling mode")
                if vector.shape != (int(encoder_cfg["dimensions"]),) or not np.isfinite(vector).all():
                    raise ValueError(f"Invalid embedding for {row['key']}")
                if int(result["n_points"]) < int(config["data"]["minimum_encoder_points"]):
                    raise ValueError(f"Encoder accepted a short trajectory in {row['key']}")
                embeddings.append(vector)
            vectors = np.asarray(embeddings, dtype=np.float32).reshape(-1, int(encoder_cfg["dimensions"]))
            if len(vectors) != int(row["N"]) or len(ids) != len(vectors) or len(n_points) != len(vectors):
                raise ValueError(f"Embedding count differs from scene manifest: {row['key']}")
        arrays[row["key"]] = vectors
        rows.append({
            key: row[key] for key in (
                "key", "hour_utc", "local_date", "local_hour", "source_fragments",
                "excluded_below_30", "N", "unique_flights", "eligible_points",
            )
        })
        if index % 120 == 0:
            print(f"encoded {index}/720 hours", flush=True)

    embedding_path = output_dir / "embeddings.npz"
    np.savez_compressed(embedding_path, **arrays)
    metadata = {
        "schema_version": 1,
        "airport": config["airport"],
        "local_date_start": config["local_date_start"],
        "local_date_end_exclusive": config["local_date_end_exclusive"],
        "total_embeddings": int(sum(row["N"] for row in rows)),
        "source_fragments": int(scene_index["source_fragments"]),
        "excluded_below_30": int(scene_index["excluded_below_30"]),
        "unique_flights": int(scene_index["unique_flights"]),
        "eligible_sample_points": int(scene_index["eligible_sample_points"]),
        "source_archive_sha256": scene_index["source_archive_sha256"],
        "prepared_scene_index_sha256": sha256_file(scene_index_path),
        "checkpoint_epoch": int(encoder_cfg["checkpoint_epoch"]),
        "checkpoint_sha256": checkpoint_hash,
        "training_airport": encoder_cfg["training_airport"],
        "dimensions": int(encoder_cfg["dimensions"]),
        "pooling": encoder_cfg["pooling"],
        "post_pooling_normalization": bool(encoder_cfg["post_pooling_normalization"]),
        "preprocessor_id": encoder.preprocess["preprocessor_id"],
        "embedding_archive_sha256": sha256_file(embedding_path),
        "device": str(device),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "rows": rows,
    }
    write_json(output_dir / "encoding-summary.json", metadata)
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True, help="Directory created by prepare_scenes.py")
    parser.add_argument("--checkpoint", type=Path, required=True, help="Frozen WSSS epoch-60 checkpoint")
    parser.add_argument("--output", type=Path, required=True, help="New output directory for embeddings and metadata")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--device", default="auto", help="auto, cpu, or cuda")
    args = parser.parse_args()
    result = encode_prepared_scenes(args.prepared, args.checkpoint, args.output, args.config, device=args.device)
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
