"""Exact finite-sample correlation dimension estimation; no Encoder dependency."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.spatial.distance import pdist


@dataclass(frozen=True)
class ComplexityConfig:
    """Heuristic quality gates, not a statistical guarantee of a fractal regime."""

    normalize: bool = False
    n_radii: int = 64
    min_samples: int = 30
    min_fit_points: int = 8
    min_pairs: int = 10
    correlation_bounds: Tuple[float, float] = (0.02, 0.3)
    min_radius_ratio: float = 2.0
    min_r_squared: float = 0.94
    max_pairs: int = 5_000_000

    def __post_init__(self):
        if not isinstance(self.normalize, bool):
            raise ValueError("normalize must be a boolean")
        for name, minimum in (("n_radii", 3), ("min_samples", 2),
                              ("min_fit_points", 3), ("min_pairs", 1), ("max_pairs", 1)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")
            object.__setattr__(self, name, int(value))
        if len(self.correlation_bounds) != 2:
            raise ValueError("correlation_bounds must contain two values")
        low, high = self.correlation_bounds
        if not (0 < low < high < 1):
            raise ValueError("correlation_bounds must satisfy 0 < low < high < 1")
        if not np.isfinite(self.min_radius_ratio) or self.min_radius_ratio <= 1:
            raise ValueError("min_radius_ratio must be finite and > 1")
        if not np.isfinite(self.min_r_squared) or not 0 <= self.min_r_squared <= 1:
            raise ValueError("min_r_squared must be in [0, 1]")


@dataclass
class ComplexityResult:
    status: str
    reason: Optional[str]
    n_samples: int
    embedding_dim: int
    n_unique: int
    n_pairs: int
    zero_distance_pairs: Optional[int]
    config: Dict[str, Any]
    scene_id: Optional[str] = None
    dimension: Optional[float] = None
    fit_slope: Optional[float] = None
    intercept: Optional[float] = None
    r_squared: Optional[float] = None
    fit_radius_range: Optional[Tuple[float, float]] = None
    fit_indices: List[int] = field(default_factory=list)
    radii: List[float] = field(default_factory=list)
    correlation: List[float] = field(default_factory=list)
    pair_counts: List[int] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    selection: str = "auto_correlation_bounds"
    requested_fit_range: Optional[Tuple[float, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return JSON-compatible diagnostics (unavailable values are None)."""
        return asdict(self)


def _points(embeddings, normalize):
    raw = np.asarray(embeddings)
    if raw.ndim != 2 or raw.shape[1] == 0:
        raise ValueError("embeddings must have shape (N, D), D >= 1; pool time steps first")
    if raw.dtype.kind not in "iuf":
        raise ValueError("embeddings must contain real numeric values")
    points = np.array(raw, dtype=np.float64, copy=True)
    if not np.isfinite(points).all():
        raise ValueError("embeddings must be finite; remove padding before pooling")
    if normalize and len(points):
        # Scale first to avoid overflow/underflow in the L2 norm.
        scale = np.max(np.abs(points), axis=1, keepdims=True)
        if np.any(scale == 0):
            raise ValueError("L2 normalization is undefined for a zero embedding")
        points /= scale
        points /= np.linalg.norm(points, axis=1, keepdims=True)
    return points


def _radii(values):
    raw = np.asarray(values)
    if raw.dtype.kind not in "iuf":
        raise ValueError("radii must be real numbers")
    radii = np.asarray(raw, dtype=np.float64)
    if (radii.ndim != 1 or radii.size == 0 or not np.isfinite(radii).all()
            or np.any(radii <= 0) or np.any(np.diff(radii) <= 0)):
        raise ValueError("radii must be a nonempty, finite, positive, strictly increasing vector")
    return radii


def _distances(points, max_pairs):
    count = len(points) * (len(points) - 1) // 2
    if count > max_pairs:
        raise ValueError(f"{count} pairs exceed max_pairs={max_pairs}; split scenes or explicitly raise the limit")
    distances = pdist(points, metric="euclidean")
    if not np.isfinite(distances).all():
        raise ValueError("pairwise distances overflow; rescale embeddings consistently")
    distances.sort()
    return distances


def correlation_integral(embeddings, radii, *, normalize=False, max_pairs=5_000_000):
    """C(r) = count(i < j and distance(i,j) < r) / choose(N,2).

    Exact Euclidean distances, no self pairs, no automatic deduplication.
    Returns a float64 array matching radii. At least two points are required.
    """
    if not isinstance(normalize, bool):
        raise ValueError("normalize must be a boolean")
    if isinstance(max_pairs, bool) or not isinstance(max_pairs, (int, np.integer)) or max_pairs < 1:
        raise ValueError("max_pairs must be a positive integer")
    points = _points(embeddings, normalize)
    scales = _radii(radii)
    if len(points) < 2:
        raise ValueError("correlation integral requires at least two points")
    distances = _distances(points, max_pairs)
    return np.searchsorted(distances, scales, side="left") / distances.size


def estimate_complexity(embeddings, *, config=None, radii=None, fit_range=None, scene_id=None):
    """Estimate one scene's empirical correlation dimension.

    Input is pooled embeddings (N, D), one aircraft-window per row. No training,
    temporal pooling or hour segmentation occurs here. Invalid input raises
    ValueError; valid but unestimable scenes return status='unestimable'.

    Auto mode fits ALL scales inside configured C(r) bounds with enough pairs.
    Explicit fit_range=(r_min,r_max) overrides C bounds, not quality gates.
    No search for a small high-R² sub-window is performed.
    """
    cfg = config if config is not None else ComplexityConfig()
    if not isinstance(cfg, ComplexityConfig):
        raise ValueError("config must be ComplexityConfig")
    if scene_id is not None and not isinstance(scene_id, str):
        raise ValueError("scene_id must be a string or None")
    points = _points(embeddings, cfg.normalize)
    scales = _radii(radii) if radii is not None else None
    requested = None
    if fit_range is not None:
        bounds = _radii(fit_range)
        if len(bounds) != 2:
            raise ValueError("fit_range must contain exactly (r_min, r_max)")
        requested = (float(bounds[0]), float(bounds[1]))
    n, d = points.shape
    unique = len(np.unique(points, axis=0))
    result = ComplexityResult(
        status="unestimable", reason=None, n_samples=n, embedding_dim=d,
        n_unique=unique, n_pairs=n * (n - 1) // 2, zero_distance_pairs=None,
        config=asdict(cfg), scene_id=scene_id,
        selection="explicit_radius_range" if requested else "auto_correlation_bounds",
        requested_fit_range=requested,
    )
    if unique < n:
        result.warnings.append("duplicate_embeddings: retained as distinct aircraft; geometry may be biased")
    if n < cfg.min_samples:
        result.reason = "insufficient_samples"
        return result
    distances = _distances(points, cfg.max_pairs)
    result.zero_distance_pairs = int(np.searchsorted(distances, 0, side="right"))
    if result.zero_distance_pairs:
        result.warnings.append("zero_distance_pairs: included in C(r) for every positive radius")
    positive = distances[distances > 0]
    if positive.size == 0:
        result.reason = "collapsed_point_cloud"
        return result
    if scales is None:
        if requested:
            scales = np.geomspace(*requested, num=cfg.n_radii)
        elif positive[0] == positive[-1]:
            result.reason = "no_distance_scale_range"
            return result
        else:
            scales = np.geomspace(positive[0], positive[-1], cfg.n_radii)
    counts = np.searchsorted(distances, scales, side="left")
    correlation = counts / distances.size
    result.radii = scales.tolist()
    result.pair_counts = counts.tolist()
    result.correlation = correlation.tolist()
    eligible = (counts >= cfg.min_pairs) & (correlation > 0) & (correlation < 1)
    if requested:
        eligible &= (scales >= requested[0]) & (scales <= requested[1])
    else:
        low, high = cfg.correlation_bounds
        eligible &= (correlation >= low) & (correlation <= high)
    indices = np.flatnonzero(eligible)
    result.fit_indices = indices.tolist()
    if len(indices) < cfg.min_fit_points:
        result.reason = "insufficient_fit_scales"
        return result
    selected = scales[indices]
    result.fit_radius_range = (float(selected[0]), float(selected[-1]))
    if np.log(selected[-1]) - np.log(selected[0]) < np.log(cfg.min_radius_ratio):
        result.reason = "insufficient_scale_span"
        return result
    log_r = np.log(selected)
    log_c = np.log(correlation[indices])
    centered_r = log_r - log_r.mean()
    centered_c = log_c - log_c.mean()
    total = float(centered_c @ centered_c)
    if total <= np.finfo(float).eps:
        result.reason = "flat_correlation_curve"
        return result
    slope = float((centered_r @ centered_c) / (centered_r @ centered_r))
    intercept = float(log_c.mean() - slope * log_r.mean())
    residual = log_c - (slope * log_r + intercept)
    r_squared = float(1 - (residual @ residual) / total)
    if not np.isfinite([slope, intercept, r_squared]).all():
        result.reason = "nonfinite_fit"
        return result
    result.fit_slope = slope
    result.intercept = intercept
    result.r_squared = r_squared
    if slope <= 0:
        result.reason = "nonpositive_slope"
    elif r_squared < cfg.min_r_squared:
        result.reason = "poor_linear_fit"
    else:
        result.status = "ok"
        result.dimension = slope
    return result
