"""Check the bundled checkpoint and its reference inference output."""
import numpy as np
from trajectory_encoder.common import ROOT, file_hash, read_json
from trajectory_encoder.inference import FrozenEncoder

EXPECTED_CHECKPOINT_SHA256 = "c0d98e6cde14baf99d28b7d336c282eb245f1ce485c248c32a58fd9ccf5358e5"


def verify():
    config = read_json(ROOT / "encoder" / "config.json")
    checkpoint = ROOT / "encoder" / "encoder.pt"
    digest = file_hash(checkpoint)
    if digest != EXPECTED_CHECKPOINT_SHA256:
        raise RuntimeError("Checkpoint checksum differs from the configured model")
    if config["selected_epoch"] != 60 or config["checkpoint_sha256"] != digest:
        raise RuntimeError("Checkpoint epoch or checksum differs from encoder/config.json")
    if config["dimension"] != 16 or config["pooling"] != "sum":
        raise RuntimeError("Encoder configuration must specify a 16-D sum-pooled vector")
    encoder = FrozenEncoder(checkpoint, pooling="sum", device="cpu")
    if encoder.preprocess["preprocessor_id"] != config["preprocessor_id"]:
        raise RuntimeError("Preprocessing ID differs from the exported config")
    if encoder.settings["dimension"] != config["dimension"]:
        raise RuntimeError("Embedding dimension differs from the exported config")
    if any(p.requires_grad for p in encoder.model.parameters()) or encoder.model.training:
        raise RuntimeError("Inference model must be frozen and in evaluation mode")
    with np.load(ROOT / "encoder" / "example_input_output.npz", allow_pickle=False) as example:
        enu_m = example["enu_m"]
        if enu_m.ndim != 2 or enu_m.shape[1] != 3 or len(enu_m) < 30:
            raise RuntimeError("Saved example must be a trajectory with shape (T, 3), T >= 30")
        if example["embedding"].shape != (config["dimension"],):
            raise RuntimeError("Saved example has an unexpected embedding shape")
        out = encoder.encode(enu_m)
        np.testing.assert_allclose(out["embedding"], example["embedding"], rtol=1e-4, atol=1e-3)
    print("SHA256 OK encoder/encoder.pt", digest)
    print("FROZEN ENCODER EXAMPLE OK", out["n_points"], out["embedding"].shape)


if __name__ == "__main__":
    verify()
