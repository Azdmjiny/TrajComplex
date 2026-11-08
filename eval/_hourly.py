"""Shared encoding and ungated D for the two hourly arrival evaluations."""

from pathlib import Path

import numpy as np
import pandas as pd
import torch
from scipy.spatial.distance import pdist

from Encoder.trajectory_encoder.data import features
from Encoder.trajectory_encoder.model import TrajectoryEncoder

FEATURE_ORDER = [
    "east_m", "north_m", "up_m", "direction_e", "direction_n", "direction_u",
    "radius_m", "sin_theta", "cos_theta",
]


def configure_inference():
    torch.set_num_threads(2)
    torch.manual_seed(43)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False


class HourlyEncoder:
    def __init__(self, checkpoint, airport, dimension, device):
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        settings = state["settings"]
        self.preprocess = state["preprocess"]
        if (state["epoch"] != 60 or settings["dimension"] != dimension
                or settings["pooling"] != "sum" or self.preprocess["airport"] != airport
                or self.preprocess["feature_order"] != FEATURE_ORDER):
            raise ValueError(f"Unexpected encoder configuration in {checkpoint}")

        self.mean = np.asarray(self.preprocess["mean"])
        self.std = np.asarray(self.preprocess["std"])
        if (self.mean.shape != (9,) or self.std.shape != (9,)
                or not np.isfinite([self.mean, self.std]).all() or (self.std <= 0).any()):
            raise ValueError(f"Invalid feature normalization in {checkpoint}")
        self.dimension = dimension
        self.device = device
        architecture = settings["model"]
        parameters = {k: architecture[k] for k in ("input_dim", "model_dim", "ffn_dim", "heads", "layers")}
        self.model = TrajectoryEncoder(dimension, **parameters)
        self.model.load_state_dict(state["state_dict"], strict=True)
        self.model.to(device).eval().requires_grad_(False)

    @torch.inference_mode()
    def encode(self, tracks):
        parts = []
        for start in range(0, len(tracks), 16):
            batch = tracks[start:start + 16]
            x = np.zeros((len(batch), max(map(len, batch)), 9), np.float32)
            valid = np.zeros(x.shape[:2], bool)
            for index, track in enumerate(batch):
                x[index, :len(track)] = (features(track) - self.mean) / self.std
                valid[index, :len(track)] = True
            tokens = self.model(
                torch.from_numpy(x).to(self.device), torch.from_numpy(valid).to(self.device),
            )
            parts.append(tokens.sum(1).cpu().numpy())
        return np.concatenate(parts) if parts else np.empty((0, self.dimension), np.float32)


def raw_dimension(cloud):
    """Fit every scale with 0 < C(r) < 1 in the original epoch-60 protocol."""
    result = dict(dimension=None, status="unestimable", reason=None, r_squared=None,
                  fit_scales=0, fit_slope=None, fit_intercept=None, radius_ratio=None)
    if not np.isfinite(cloud).all():
        raise ValueError("Nonfinite embeddings")
    if len(cloud) < 2:
        return dict(result, reason="fewer_than_two_embeddings")
    distances = np.sort(pdist(cloud.astype(np.float64), metric="euclidean"))
    if not np.isfinite(distances).all():
        raise ValueError("Nonfinite distances")
    positive = distances[distances > 0]
    if not len(positive) or positive[0] == positive[-1]:
        return dict(result, reason="no_positive_distance_scale_range")

    radii = np.geomspace(positive[0], positive[-1], 64)
    correlation = np.searchsorted(distances, radii, side="left") / len(distances)
    keep = (correlation > 0) & (correlation < 1)
    result["fit_scales"] = int(keep.sum())
    if result["fit_scales"] < 2:
        return dict(result, reason="fewer_than_two_log_fit_points")

    x, y = np.log(radii[keep]), np.log(correlation[keep])
    dx, dy = x - x.mean(), y - y.mean()
    denominator = float(dx @ dx)
    if denominator <= 0:
        return dict(result, reason="zero_log_radius_variance")
    slope = float((dx @ dy) / denominator)
    intercept = float(y.mean() - slope * x.mean())
    residual = y - (slope * x + intercept)
    variance = float(dy @ dy)
    r_squared = float(1 - (residual @ residual) / variance) if variance > np.finfo(float).eps else None
    selected_radii = radii[keep]
    return dict(result, dimension=slope, status="computed", fit_slope=slope,
                fit_intercept=intercept, r_squared=r_squared,
                radius_ratio=float(selected_radii[-1] / selected_radii[0]))


def load_plan(directory, airport):
    plan = pd.read_csv(directory / "prepared_hours.csv").sort_values("hour_utc")
    dates = plan.hour_local
    if (len(plan) != 720 or not plan.airport.eq(airport).all()
            or not np.all(np.diff(plan.hour_utc) == 3600)
            or not dates.str.startswith("2026-09-").all()
            or not dates.iloc[0].startswith("2026-09-01T00:00")
            or not dates.iloc[-1].startswith("2026-09-30T23:00")
            or any(pd.Timestamp(row.hour_local).timestamp() != row.hour_utc for row in plan.itertuples())):
        raise ValueError(f"Expected all 720 local September 2026 hours for {airport}")
    return plan


def read_hour(directory, row):
    # Resolve relative to the supplied directory, including manifests exported on Windows.
    name = Path(row.prepared_path.replace("\\", "/")).name
    path = directory / "hours" / name
    with np.load(path, allow_pickle=False) as data:
        xyz, offsets, times, ids = (data[key] for key in ("enu_m", "offsets", "time", "flight_ids"))
        if "traffic_label" in data and not np.all(data["traffic_label"] == "arrival"):
            raise ValueError(f"Non-arrival trajectory in {path}")
    if (xyz.shape != (len(times), 3) or offsets.shape != (len(ids) + 1,)
            or not np.issubdtype(offsets.dtype, np.integer) or offsets[0] != 0 or offsets[-1] != len(xyz)
            or len(np.unique(ids)) != len(ids) or not np.isfinite(xyz).all()
            or not np.all(np.diff(offsets) >= 25)
            or not np.all((times >= row.hour_utc) & (times < row.hour_utc + 3600) & (times % 10 == 0))
            or any(not np.all(np.diff(times[a:b]) == 10) for a, b in zip(offsets[:-1], offsets[1:]))):
        raise ValueError(f"Invalid hourly arrival arrays in {path}")
    return xyz.astype(np.float64), offsets


def score_month(directory, plan, encoder, enu_transform=None):
    rows = []
    for row in plan.itertuples(index=False):
        xyz, offsets = read_hour(directory, row)
        if enu_transform is not None:
            rotation, shift = enu_transform
            xyz = xyz @ rotation + shift
        tracks = [xyz[a:b] for a, b in zip(offsets[:-1], offsets[1:])]
        rows.append(dict(airport=row.airport, hour_utc=row.hour_utc, hour_local=row.hour_local,
                         N=len(tracks), **raw_dimension(encoder.encode(tracks))))
    return pd.DataFrame(rows)
