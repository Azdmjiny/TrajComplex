"""Temporal pooling shared by the legacy loader and scene inference APIs."""

import torch

if __package__:
    from .config import EmbeddingConfig
else:
    from config import EmbeddingConfig


def pool_hidden(hidden, valid_mask=None, *, pooling="sum", gem_p=2.0):
    """Pool (B,T,D) to (B,D); True marks valid tokens, never padding.

    TUNE: sum is the main candidate; mean and signed GeM-p2 are controls.
    No post-pooling normalization is applied. Fix it separately in complexity.
    """
    EmbeddingConfig(pooling=pooling, gem_p=gem_p)
    if hidden.ndim != 3 or not hidden.is_floating_point() or hidden.shape[-1] == 0:
        raise ValueError("hidden must be a floating tensor of shape (B, T, D), D >= 1")
    if valid_mask is None:
        valid_mask = ~torch.isnan(hidden).all(dim=-1)
    if valid_mask.shape != hidden.shape[:2] or valid_mask.dtype != torch.bool:
        raise ValueError("valid_mask must be a boolean tensor of shape (B, T)")
    valid_mask = valid_mask.to(hidden.device)
    if not valid_mask.any(dim=1).all():
        raise ValueError("each trajectory needs at least one valid time step")
    if not torch.isfinite(hidden[valid_mask]).all():
        raise ValueError("valid hidden representations must be finite")
    rows = []
    for sequence, mask in zip(hidden, valid_mask):
        values = sequence[mask]
        if pooling == "sum":
            pooled = values.sum(dim=0)
        elif pooling == "mean":
            pooled = values.mean(dim=0)
        elif pooling == "gem":
            # Signed GeM as defined in doc/, not clamp-to-positive image GeM.
            # Scale each coordinate first to avoid unnecessary power overflow.
            scale = values.abs().amax(dim=0).clamp_min(torch.finfo(values.dtype).tiny)
            scaled = values / scale
            moment = (scaled.sign() * scaled.abs().pow(gem_p)).mean(dim=0)
            pooled = scale * moment.sign() * moment.abs().pow(1.0 / gem_p)
        elif pooling == "max":
            pooled = values.max(dim=0).values
        elif pooling == "first":
            pooled = values[0]
        else:
            pooled = values[-1]
        rows.append(pooled)
    result = torch.stack(rows) if rows else hidden.new_empty((0, hidden.shape[-1]))
    if not torch.isfinite(result).all():
        raise ValueError("pooled embeddings overflow; check features and pooling")
    return result
