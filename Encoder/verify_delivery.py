"""Check the current frozen export without training or historical records."""
import numpy as np
from trajectory_encoder.common import ROOT, file_hash, read_json
from trajectory_encoder.inference import FrozenEncoder

EXPECTED_CHECKPOINT_SHA256 = "bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976"


def verify():
    config = read_json(ROOT / "encoder" / "config.json")
    checkpoint = ROOT / "encoder" / "encoder.pt"
    digest = file_hash(checkpoint)
    if digest != EXPECTED_CHECKPOINT_SHA256:
        raise RuntimeError("Current checkpoint checksum differs from the frozen release")
    encoder = FrozenEncoder(checkpoint, pooling="sum", device="cpu")
    if encoder.preprocess["preprocessor_id"] != config["preprocessor_id"]:
        raise RuntimeError("Preprocessing ID differs from the exported config")
    if any(p.requires_grad for p in encoder.model.parameters()) or encoder.model.training:
        raise RuntimeError("Inference model must be frozen and in evaluation mode")
    with np.load(ROOT / "encoder" / "example_input_output.npz", allow_pickle=False) as example:
        out = encoder.encode(example["enu_m"])
        np.testing.assert_allclose(out["tokens"], example["tokens"], rtol=1e-5, atol=1e-6)
        np.testing.assert_allclose(out["embedding"], example["embedding"], rtol=1e-5, atol=1e-5)
    print("SHA256 OK encoder/encoder.pt", digest)
    print("FROZEN ENCODER EXAMPLE OK", out["tokens"].shape, out["embedding"].shape)


if __name__ == "__main__":
    verify()
