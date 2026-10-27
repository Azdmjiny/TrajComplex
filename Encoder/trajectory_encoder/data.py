"""Feature construction for already sampled ENU trajectories."""
import numpy as np


def features(p):
    delta = np.diff(p, axis=0)
    delta = np.concatenate([delta, delta[-1:]])
    unit = delta / np.maximum(np.linalg.norm(delta, axis=1, keepdims=True), 1e-9)
    theta = np.arctan2(p[:, 1], p[:, 0])
    return np.column_stack([p, unit, np.linalg.norm(p[:, :2], axis=1), np.sin(theta), np.cos(theta)])
