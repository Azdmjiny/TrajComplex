"""Training steps shared by the airport-specific and Changi evaluation encoders."""

import gzip
import hashlib
import json
import random
from typing import NamedTuple

import numpy as np
import torch

from Encoder.trajectory_encoder.data import features
from eval._hourly import FEATURE_ORDER
from eval._training_model import TrajectoryEncoder, flat_snn

SPLITS = {"train": "train", "validation": "val", "test": "test"}
MODEL = dict(input_dim=9, model_dim=256, ffn_dim=512, heads=4, layers=4,
             dropout=.35, mask_probability=.10)


class Track(NamedTuple):
    sample_id: str
    month: str
    split: str
    features: np.ndarray
    labels: np.ndarray


def sample_rank(sample_id):
    return hashlib.sha256(f"43:{sample_id}".encode()).digest()


def rdp_labels(positions):
    """Assign consecutive segments from the original 300 m RDP partition."""
    keep = np.zeros(len(positions), dtype=bool)
    keep[[0, -1]] = True
    stack = [(0, len(positions) - 1)]
    while stack:
        start, stop = stack.pop()
        if stop - start < 2:
            continue
        line = positions[stop] - positions[start]
        delta = positions[start + 1:stop] - positions[start]
        norm = np.linalg.norm(line)
        distances = (np.linalg.norm(delta, axis=1) if norm < 1e-12
                     else np.linalg.norm(np.cross(delta, line), axis=1) / norm)
        index = int(np.argmax(distances))
        if distances[index] > 300:
            mid = start + 1 + index
            keep[mid] = True
            stack.extend([(start, mid), (mid, stop)])
    labels = np.cumsum(keep).astype(np.int16) - 1
    labels[-1] = labels[-2]
    return labels


def read_training(path, airport, selected=None):
    tracks, seen, flights = [], set(), set()
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            sample = str(row["sample_id"])
            if selected is not None and sample not in selected:
                continue
            flight = (row["icao24"], row["firstseen"], row["lastseen"])
            if sample in seen or flight in flights:
                raise ValueError(f"Duplicate training flight in {path}")
            seen.add(sample)
            flights.add(flight)
            split, month = SPLITS[row["split"]], row["month"]
            if selected is not None and selected[sample] != (split, month):
                raise ValueError(f"Training index disagrees with archive for {sample}")
            if row["airport"] != airport or row.get("direction", "arrival") != "arrival":
                raise ValueError(f"Expected arrivals at {airport}")
            times = np.asarray(row["time"])
            if (any(len(row[axis]) != len(times) for axis in "xyz")
                    or not np.all(np.diff(times) == 1)):
                raise ValueError(f"Expected contiguous 1 Hz positions for {sample}")
            positions = np.column_stack([row[axis][::10] for axis in "xyz"]).astype(np.float64) * 120000
            if len(positions) < 30 or not np.isfinite(positions).all():
                raise ValueError(f"Invalid training trajectory {sample}")
            tracks.append(Track(sample, month, split, features(positions), rdp_labels(positions)))
    if selected is not None and seen != set(selected):
        raise ValueError("Some index-selected trajectories are missing from the archive")
    return tracks


def training_statistics(tracks):
    training = [track.features for track in tracks if track.split == "train"]
    n_tokens = sum(map(len, training))
    mean = sum((x.sum(0) for x in training), np.zeros(9)) / n_tokens
    variance = sum((np.square(x).sum(0) for x in training), np.zeros(9)) / n_tokens - mean ** 2
    std = np.sqrt(np.maximum(variance, 0))
    std[std < 1e-8] = 1
    return mean, std


def batches(indices, features_by_track, labels, *, shuffle=False, epoch=0):
    ids = indices.copy()
    rng = np.random.default_rng(43000 + epoch)
    if shuffle:
        rng.shuffle(ids)
    parts = []
    lengths = np.asarray([len(x) for x in features_by_track])
    for bucket in np.array_split(ids, max(1, int(np.ceil(len(ids) / 256)))):
        bucket = bucket[np.argsort(lengths[bucket], kind="stable")]
        parts.extend(bucket[i:i + 16] for i in range(0, len(bucket), 16))
    if shuffle:
        rng.shuffle(parts)
    for ids in parts:
        shape = (len(ids), int(lengths[ids].max()))
        x = np.zeros((*shape, 9), np.float32)
        y = np.zeros(shape, np.int64)
        valid = np.zeros(shape, bool)
        for index, track in enumerate(ids):
            n = lengths[track]
            x[index, :n], y[index, :n], valid[index, :n] = features_by_track[track], labels[track], True
        yield tuple(torch.from_numpy(array).cuda() for array in (x, y, valid))


def train(tracks, airport, dimension, architecture, preprocess, output, *, tf32=False):
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("Training requires BF16-capable CUDA")
    if output.exists():
        raise FileExistsError(output)
    random.seed(43)
    np.random.seed(43)
    torch.manual_seed(43)
    torch.cuda.manual_seed_all(43)
    torch.set_num_threads(2)
    torch.backends.cuda.matmul.allow_tf32 = tf32
    torch.backends.cudnn.allow_tf32 = True

    mean, std = training_statistics(tracks)
    center, scale = mean.astype(np.float32), std.astype(np.float32)
    x = [(track.features.astype(np.float32) - center) / scale for track in tracks]
    labels = [track.labels for track in tracks]
    splits = {s: np.flatnonzero([track.split == s for track in tracks]) for s in SPLITS.values()}
    model = TrajectoryEncoder(dimension, **architecture).cuda()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-5, weight_decay=1e-5)

    def loss_for(values, groups, valid):
        with torch.autocast("cuda", dtype=torch.bfloat16):
            return flat_snn(model(values, valid), groups, valid, 1.0, 7000, 512)

    for epoch in range(1, 61):
        model.train()
        for batch in batches(splits["train"], x, labels, shuffle=True, epoch=epoch):
            optimizer.zero_grad(set_to_none=True)
            loss, _ = loss_for(*batch)
            if not torch.isfinite(loss):
                raise FloatingPointError("Nonfinite training loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1, error_if_nonfinite=True)
            optimizer.step()
        model.eval()
        total = n_anchors = 0
        with torch.inference_mode():
            for batch in batches(splits["val"], x, labels):
                loss, n = loss_for(*batch)
                if not torch.isfinite(loss):
                    raise FloatingPointError("Nonfinite validation loss")
                total += float(loss) * n
                n_anchors += n
        validation_loss = total / n_anchors
        print(f"{output.stem}: epoch {epoch}/60, validation loss {validation_loss:.6f}", flush=True)

    preprocess = dict(preprocess, airport=airport, feature_order=FEATURE_ORDER,
                      mean=mean.tolist(), std=std.tolist())
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".writing")
    torch.save(dict(state_dict=model.state_dict(), epoch=60, preprocess=preprocess,
                    validation_loss=validation_loss,
                    settings=dict(dimension=dimension, model=architecture, pooling="sum"),
                    runtime=dict(torch=str(torch.__version__), numpy=np.__version__,
                                 cuda=torch.version.cuda, tf32_matmul=tf32)), temporary)
    temporary.replace(output)
