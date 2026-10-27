"""Encode the bundled example or an already sampled ENU trajectory."""
import argparse
from pathlib import Path
import numpy as np
from trajectory_encoder.common import ROOT
from trajectory_encoder.inference import FrozenEncoder

p = argparse.ArgumentParser()
p.add_argument("--checkpoint", type=Path, default=ROOT / "encoder" / "encoder.pt")
p.add_argument("--input", type=Path, default=ROOT / "encoder" / "example_input_output.npz")
a = p.parse_args()
value = np.load(a.input, allow_pickle=False)
if isinstance(value, np.lib.npyio.NpzFile):
    with value:
        points = value["enu_m"]
else:
    points = value
result = FrozenEncoder(a.checkpoint).encode(points)
print("token vectors:", result["tokens"].shape)
print("trajectory vector:", result["embedding"])
