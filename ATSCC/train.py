"""Configured ATSCC-inspired training scaffold, without W&B/network side effects.

Run from the workspace root: python -m ATSCC.train --help
Input splits are supplied by the caller; no random split or test-set selection.
"""

import argparse
import json
from pathlib import Path
import random

import numpy as np
import torch
from torch.utils.data import DataLoader

if __package__:
    from .config import EncoderConfig, EmbeddingConfig, TrainingConfig
    from .inference import build_model, save_model
    from .losses.losses import flat_snnl
else:
    from config import EncoderConfig, EmbeddingConfig, TrainingConfig
    from inference import build_model, save_model
    from losses.losses import flat_snnl


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def make_dataset(positions, *, config=None):
    """Existing ATSCC feature/RDP recipe: ENU xyz -> xyz + direction + polar.

    TUNE/FREEZE: downsample and epsilon depend on sampling/coordinate units.
    No coordinate conversion, scaler fit, or normalization is silently performed.
    Use exactly this recipe for inference too; data must already be verified ENU.
    """
    if __package__:
        from .datautils import ATPCCDataset
    else:
        from datautils import ATPCCDataset
    config = TrainingConfig() if config is None else config
    if not isinstance(config, TrainingConfig):
        raise ValueError("config must be TrainingConfig")
    positions = np.asarray(positions)
    if positions.ndim != 3 or positions.shape[-1] != 3 or positions.dtype.kind not in "iuf" or not len(positions):
        raise ValueError("positions must be a nonempty real numeric (N,T,3) array")
    cleaned = []
    for row in positions:
        row = row[~np.isnan(row).all(axis=1)]
        if not np.isfinite(row).all():
            raise ValueError("only full-NaN rows are padding; partial NaNs/Inf are invalid")
        row = row[::config.downsample]
        if len(row) < 2:
            raise ValueError("each trajectory needs >=2 valid tokens AFTER downsampling for RDP/direction")
        cleaned.append(row)
    padded = np.full((len(cleaned), max(map(len, cleaned)), 3), np.nan, dtype=np.float32)
    for index, row in enumerate(cleaned):
        padded[index, :len(row)] = row
    if not np.isfinite(padded[~np.isnan(padded).all(axis=2)]).all():
        raise ValueError("positions overflow float32")
    return ATPCCDataset(padded, epsilon=config.rdp_epsilon, eval=False, device="cpu",
                        direction=True, polar=True)


def _run_epoch(model, loader, device, config, optimizer=None, max_batches=None):
    training = optimizer is not None
    model.train(training)
    losses = []
    with torch.set_grad_enabled(training):
        for batch_index, batch in enumerate(loader):
            if max_batches is not None and batch_index >= max_batches:
                break
            features, labels = batch[:2]
            features, labels = features.to(device), labels.to(device)
            valid = ~labels.isnan()
            if (features.ndim != 3 or labels.shape != features.shape[:2] or not valid.any()
                    or not valid.any(dim=1).all() or not torch.isfinite(features[valid]).all()
                    or not torch.isfinite(labels[valid]).all()
                    or not torch.equal(valid, ~features.isnan().any(dim=-1))):
                raise ValueError("features/procedural labels must have matching, finite valid tokens")
            out = model(features)
            # TUNE (later): token subsampling is NOT currently used; all in-batch
            # tokens are negatives, so loss memory can grow quadratically in B*T.
            loss = flat_snnl(out, labels, temperature=config.temperature, portion=1.0)
            if not torch.isfinite(loss):
                raise ValueError("nonfinite flat SNNL; inspect features, RDP and temperature")
            if training:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
                    raise ValueError("nonfinite gradients; inspect features, masking and temperature")
                optimizer.step()
            losses.append(float(loss.detach()))
    if not losses:
        raise ValueError("training/validation loader must not be empty")
    return float(np.mean(losses)), len(losses)


def fit_encoder(model, train_loader, *, output_dir, validation_loader=None,
                config=None, embedding_config=None, metadata=None, device="cpu"):
    """Train from pre-split loaders and write last.pt, optional best.pt, history.json.

    best.pt uses held-out flat SNNL as a scaffold selection criterion, NOT a
    validated representation-quality claim. No complexity labels enter training.
    No optimizer resume/AMP/gradient accumulation is implemented in this scaffold.
    """
    config = TrainingConfig() if config is None else config
    embedding_config = EmbeddingConfig() if embedding_config is None else embedding_config
    if not isinstance(config, TrainingConfig) or not isinstance(embedding_config, EmbeddingConfig):
        raise ValueError("config/embedding_config must be TrainingConfig/EmbeddingConfig")
    seed_everything(config.seed)
    model.to(device)
    # TUNE: optimizer parameters are centralized in TrainingConfig.
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    output_dir = Path(output_dir)
    if any((output_dir / name).exists() for name in ('last.pt', 'best.pt', 'history.json')):
        raise ValueError('output_dir already contains a run; use a new directory (resume is not implemented)')
    output_dir.mkdir(parents=True, exist_ok=True)
    provenance = dict(metadata or {})
    provenance["training_config"] = config.to_dict()
    provenance["selection"] = "validation_flat_snnl" if validation_loader is not None else "last_only_no_validation"
    history, steps, best_loss = [], 0, float("inf")
    for epoch in range(1, config.epochs + 1):
        train_loss, count = _run_epoch(model, train_loader, device, config, optimizer,
                                       max_batches=config.max_steps - steps)
        steps += count
        val_loss = None
        if validation_loader is not None:
            val_loss, _ = _run_epoch(model, validation_loader, device, config)
        record = {"epoch": epoch, "steps": steps, "train_loss": train_loss, "validation_loss": val_loss}
        history.append(record)
        epoch_metadata = dict(provenance, **record)
        save_model(model, output_dir / "last.pt", embedding_config=embedding_config, metadata=epoch_metadata)
        if val_loss is not None and val_loss < best_loss:
            best_loss = val_loss
            save_model(model, output_dir / "best.pt", embedding_config=embedding_config, metadata=epoch_metadata)
        (output_dir / "history.json").write_text(json.dumps(history, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps(record, allow_nan=False))
        if steps >= config.max_steps:
            break
    return history


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-data", required=True, help="pre-split ENU (N,T,3) .npy; full-NaN row padding")
    parser.add_argument("--validation-data", help="separate held-out ENU .npy; never pass the test split")
    parser.add_argument("--config", help="JSON with encoder, training and embedding configuration sections")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--data-version", required=True, help="audited data/preprocessing version")
    parser.add_argument("--split-id", required=True, help="date/flight-group split manifest identifier")
    parser.add_argument("--device", default="cpu", help="cpu, cuda:0, mps; default cpu")
    args = parser.parse_args(argv)
    try:
        settings = json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {}
        if not isinstance(settings, dict) or set(settings) - {"encoder", "training", "embedding"}:
            raise ValueError("config sections must be encoder, training and embedding")
        encoder = EncoderConfig(**settings.get("encoder", {}))
        training = TrainingConfig(**settings.get("training", {}))
        embedding = EmbeddingConfig(**settings.get("embedding", {}))
        if encoder.input_dims != 9:
            raise ValueError("the built-in xyz/direction/polar recipe requires input_dims=9")
        seed_everything(training.seed)  # Seed BEFORE model initialization.
        if __package__:
            from .datautils import pad_stack_train
        else:
            from datautils import pad_stack_train
        train_path = Path(args.train_data).resolve()
        if args.validation_data and train_path == Path(args.validation_data).resolve():
            raise ValueError("training and validation must use different pre-split files")
        def loader(path, shuffle):
            dataset = make_dataset(np.load(path, allow_pickle=False), config=training)
            return DataLoader(dataset, batch_size=training.batch_size, shuffle=shuffle,
                              collate_fn=pad_stack_train, num_workers=0)
        train_loader = loader(args.train_data, True)
        validation_loader = loader(args.validation_data, False) if args.validation_data else None
        metadata = {
            "data_version": args.data_version, "split_id": args.split_id,
            "train_data": str(train_path), "validation_data": args.validation_data,
            "preprocessing": {"coordinate_frame": "caller_verified_ENU", "direction": True,
                              "polar": True, "scaling": "none", "recipe": "ATSCC.datautils.v1"},
        }
        fit_encoder(build_model(encoder), train_loader, validation_loader=validation_loader,
                    config=training, embedding_config=embedding, output_dir=args.output_dir,
                    metadata=metadata, device=args.device)
    except (ValueError, TypeError, OSError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
