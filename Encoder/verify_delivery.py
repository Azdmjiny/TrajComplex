"""Check the frozen export and archived candidates without writing artifacts."""
import numpy as np
from trajectory_encoder.common import ROOT, file_hash, read_json
from trajectory_encoder.inference import FrozenEncoder


def verify():
    archive = ROOT / "archive"
    records = archive / "reports" / "result"
    for entry in read_json(records / "checkpoint_manifest.json"):
        checkpoint = archive / entry["path"]
        if file_hash(checkpoint) != entry["sha256"]:
            raise RuntimeError(f"Checksum mismatch: {checkpoint}")
        print("SHA256 OK", checkpoint.relative_to(ROOT).as_posix())

    spec = read_json(records / "export_verification.json")
    selection = read_json(records / "selection_10s.json")
    checkpoint = ROOT / "encoder" / "encoder.pt"
    digest = file_hash(checkpoint)
    if digest != spec["checkpoint_sha256"] or digest != selection["checkpoint_sha256"]:
        raise RuntimeError("Current checkpoint differs from its export/selection records")
    encoder = FrozenEncoder(checkpoint, pooling="sum", device="cpu")
    preprocess = read_json(ROOT / "encoder" / "preprocess.json")
    if encoder.preprocess != preprocess:
        raise RuntimeError("Exported preprocessing differs from the checkpoint")
    if encoder.preprocess["preprocessor_id"] != selection["preprocessor_id"]:
        raise RuntimeError("Preprocessing ID differs from the selection record")
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
