"""Initial research settings from doc/encoder-training-plan.md, not tuned optima."""

from dataclasses import asdict, dataclass
import math


def _positive_int(name, value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _positive_float(name, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")


@dataclass(frozen=True)
class EncoderConfig:
    input_dims: int = 9  # Frozen preprocessing: ENU xyz + direction xyz + polar r/sin/cos.
    output_dims: int = 8  # TUNE: compare 4/8/16; not the old illustrative 128 or original 320.
    embed_dim: int = 256  # TUNE (later): backbone capacity; initially freeze this and the next 3 fields.
    num_heads: int = 4
    num_layers: int = 4
    hidden_dim: int = 512
    dropout: float = 0.35  # TUNE: regularization; changes require retraining.
    mask_probability: float = 0.2  # TUNE: fraction of tokens masked, TRAINING ONLY.

    def __post_init__(self):
        for name in ("input_dims", "output_dims", "embed_dim", "num_heads", "num_layers", "hidden_dim"):
            _positive_int(name, getattr(self, name))
        if self.output_dims < 2:
            raise ValueError("output_dims must be >= 2 (legacy auxiliary projection)")
        if self.embed_dim % self.num_heads:
            raise ValueError("embed_dim must be divisible by num_heads")
        for name in ("dropout", "mask_probability"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value < 1:
                raise ValueError(f"{name} must be in [0, 1)")

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class EmbeddingConfig:
    pooling: str = "sum"  # TUNE: sum (primary), mean, gem (sensitivity); freeze before comparison.
    gem_p: float = 2.0  # TUNE: signed GeM exponent; p=1 matches mean, p=2 is the planned control.
    batch_size: int = 16  # Execution knob: inference batches do not define scene boundaries.

    def __post_init__(self):
        if self.pooling not in ("sum", "mean", "gem", "max", "first", "last"):
            raise ValueError("pooling must be sum, mean, gem, max, first or last")
        _positive_float("gem_p", self.gem_p)
        _positive_int("batch_size", self.batch_size)

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class TrainingConfig:
    epochs: int = 30  # TUNE: upper bound; select using held-out validation, not test complexity.
    batch_size: int = 16  # TUNE: start at 8/16 for 8 GB; accumulation is NOT more negatives.
    learning_rate: float = 1e-5  # TUNE: AdamW learning rate.
    weight_decay: float = 1e-5  # TUNE: AdamW regularization.
    temperature: float = 0.01  # TUNE FIRST: compare 0.01 and 0.05 with fixed epsilon/backbone.
    rdp_epsilon: float = 0.1  # TUNE FIRST: PLACEHOLDER; calibrate to ENU coordinate units.
    downsample: int = 5  # TUNE/FREEZE: sampling affects lengths, RDP and sum magnitudes.
    seed: int = 0  # TUNE/REPEAT: run >=3 fixed seeds; do not select only the best seed.
    max_steps: int = 500_000  # TUNE: compute budget, recorded with the checkpoint.

    def __post_init__(self):
        for name in ("epochs", "batch_size", "downsample", "max_steps"):
            _positive_int(name, getattr(self, name))
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or not 0 <= self.seed < 2**32:
            raise ValueError("seed must be an integer in [0, 2**32)")
        for name in ("learning_rate", "temperature", "rdp_epsilon"):
            _positive_float(name, getattr(self, name))
        if (isinstance(self.weight_decay, bool) or not isinstance(self.weight_decay, (int, float))
                or not math.isfinite(self.weight_decay) or self.weight_decay < 0):
            raise ValueError("weight_decay must be finite and nonnegative")

    def to_dict(self):
        return asdict(self)
