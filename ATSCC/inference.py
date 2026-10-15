"""Checkpoint and scene embedding APIs; no plotting, W&B or complexity dependency."""

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
import torch

if __package__:
    from .config import EncoderConfig, EmbeddingConfig
    from .model.GPT import TSGPTEncoder
    from .pooling import pool_hidden
else:
    from config import EncoderConfig, EmbeddingConfig
    from model.GPT import TSGPTEncoder
    from pooling import pool_hidden


def build_model(config=None, *, device="cpu"):
    config = EncoderConfig() if config is None else config
    if not isinstance(config, EncoderConfig):
        raise ValueError("config must be EncoderConfig")
    return TSGPTEncoder(**config.to_dict()).to(device)


def save_model(model, path, *, embedding_config=None, metadata=None):
    """Save portable weights + complete architecture + JSON-only experiment provenance.

    This is an inference checkpoint, not an optimizer/RNG training-resume snapshot.
    """
    config = EncoderConfig(**model.get_config())
    embedding_config = embedding_config or getattr(model, "embedding_config", EmbeddingConfig())
    if not isinstance(embedding_config, EmbeddingConfig):
        raise ValueError("embedding_config must be EmbeddingConfig")
    metadata = getattr(model, 'checkpoint_metadata', {}) if metadata is None else metadata
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be a JSON-compatible dictionary")
    metadata = json.loads(json.dumps(metadata, allow_nan=False))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "schema_version": 1,
        "encoder_config": config.to_dict(),
        "embedding_config": embedding_config.to_dict(),
        "state_dict": {key: value.detach().cpu() for key, value in model.state_dict().items()},
        "metadata": metadata,
    }, path)


def load_model(path, *, config=None, device="cpu"):
    """Load strictly, in eval mode. Legacy weights REQUIRE explicit EncoderConfig.

    Never unpickle a full model. Supports bare state_dict and wrappers named
    state_dict/model_state_dict/model; weights are loaded on CPU before transfer.
    """
    if config is not None and not isinstance(config, EncoderConfig):
        raise ValueError("config must be EncoderConfig")
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict):
        raise ValueError("checkpoint must contain a state_dict, not a serialized model")
    if "schema_version" in checkpoint and checkpoint["schema_version"] != 1:
        raise ValueError("unsupported checkpoint schema_version")
    if "encoder_config" in checkpoint:
        saved = EncoderConfig(**checkpoint["encoder_config"])
        if config is not None and config != saved:
            raise ValueError("explicit config conflicts with checkpoint encoder_config")
        config = saved
    if config is None:
        raise ValueError("legacy checkpoint has no encoder_config; pass the ORIGINAL EncoderConfig explicitly")
    state = checkpoint
    for key in ("state_dict", "model_state_dict", "model"):
        if key in checkpoint:
            state = checkpoint[key]
            break
    if not isinstance(state, dict) or not state or not all(isinstance(v, torch.Tensor) for v in state.values()):
        raise ValueError("checkpoint state_dict must be a nonempty mapping of tensors")
    model = build_model(config)
    try:
        model.load_state_dict(state, strict=True)
    except RuntimeError as exc:
        raise ValueError(f"checkpoint does not match EncoderConfig: {exc}") from exc
    if not all(torch.isfinite(tensor).all() for tensor in model.state_dict().values()):
        raise ValueError("checkpoint contains nonfinite weights")
    model.embedding_config = EmbeddingConfig(**checkpoint.get("embedding_config", {}))
    model.checkpoint_metadata = checkpoint.get("metadata", {})
    model.checkpoint_path = str(Path(path))
    return model.to(device).eval()


@dataclass
class EmbeddingResult:
    embeddings: np.ndarray
    lengths: list
    scene_id: str
    encoder_config: dict
    config: dict

    def to_dict(self):
        return {
            "scene_id": self.scene_id, "n_samples": len(self.embeddings),
            "embedding_dim": self.embeddings.shape[1], "lengths": self.lengths,
            "encoder_config": self.encoder_config, "config": self.config,
            "embeddings": self.embeddings.tolist(),
        }

def _trajectories(trajectories, input_dims):
    if isinstance(trajectories, np.ndarray):
        if (trajectories.ndim != 3 or trajectories.shape[-1] != input_dims
                or trajectories.dtype.kind not in 'iuf'):
            raise ValueError(f"trajectories must have shape (N,T,{input_dims})")
    else:
        if not isinstance(trajectories, (list, tuple)):
            raise ValueError("trajectories must be a padded array or list of (T,F) arrays")
    sequences = []
    for sequence in trajectories:
        values = np.asarray(sequence)
        if values.ndim != 2 or values.shape[1] != input_dims or values.dtype.kind not in "iuf":
            raise ValueError(f"each trajectory must be real numeric (T,{input_dims})")
        padding = np.isnan(values).all(axis=1)
        values = values[~padding]
        if not len(values) or not np.isfinite(values).all():
            raise ValueError("each trajectory needs finite tokens; only full-NaN rows are padding")
        values = np.array(values, dtype=np.float32, copy=True)
        if not np.isfinite(values).all():
            raise ValueError("trajectory values overflow float32")
        sequences.append(values)
    return sequences


def encode_scene(model, trajectories, *, config=None, scene_id=None):
    """Already-windowed, already-preprocessed trajectories -> finite (N,D).

    One row per aircraft in ONE scene. No hour splitting, feature conversion,
    aircraft deduplication or post-pooling normalization occurs here. Input rows
    and model training mode are preserved, including on failure.
    """
    config = getattr(model, "embedding_config", EmbeddingConfig()) if config is None else config
    if not isinstance(config, EmbeddingConfig):
        raise ValueError("config must be EmbeddingConfig")
    if scene_id is not None and not isinstance(scene_id, str):
        raise ValueError("scene_id must be a string or None")
    sequences = _trajectories(trajectories, model.input_dims)
    parameter = next(model.parameters())
    was_training = model.training
    pooled_batches = []
    try:
        model.eval()
        with torch.inference_mode():
            for start in range(0, len(sequences), config.batch_size):
                batch = sequences[start:start + config.batch_size]
                features = torch.full((len(batch), max(map(len, batch)), model.input_dims),
                                      float("nan"), device=parameter.device, dtype=parameter.dtype)
                for index, values in enumerate(batch):
                    features[index, :len(values)] = torch.as_tensor(values, device=parameter.device,
                                                                   dtype=parameter.dtype)
                valid = ~features.isnan().any(dim=-1)
                hidden = model(features)
                pooled = pool_hidden(hidden, valid, pooling=config.pooling, gem_p=config.gem_p)
                pooled_batches.append(pooled.cpu().float().numpy())
    finally:
        model.train(was_training)
    embeddings = (np.concatenate(pooled_batches) if pooled_batches
                  else np.empty((0, model.output_dims), dtype=np.float32))
    return EmbeddingResult(embeddings, [len(x) for x in sequences], scene_id,
                           model.get_config(), config.to_dict())
