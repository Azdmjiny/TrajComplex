"""Paths and immutable-input checks for the published 10-second workflows."""
from pathlib import Path
import hashlib
import sys

REPO=Path(__file__).resolve().parents[2]
RUNS=REPO/'evaluation/runs'
sys.path.insert(0,str(REPO))
CHECKPOINT_SHA256='bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976'
PREPROCESSOR_ID='52fabdb80ff5221882becc2e326e0e51089dbcf324a155bf7330f41442fa1477'

def new_output(path):
    """Published inputs and prior output directories may never be overwritten."""
    path=Path(path).resolve()
    if path==RUNS.resolve() or RUNS.resolve() in path.parents:
        raise ValueError('Choose a new output directory outside evaluation/runs')
    path.mkdir(parents=True,exist_ok=False)
    return path

def checked_encoder(checkpoint):
    """Never silently substitute the repository's older 5-second checkpoint."""
    checkpoint=Path(checkpoint)
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=CHECKPOINT_SHA256:
        raise ValueError('Expected the frozen strict-10-second epoch-90 checkpoint')
    import torch
    from Encoder.trajectory_encoder.inference import FrozenEncoder
    encoder=FrozenEncoder(checkpoint,pooling='sum',device='cuda' if torch.cuda.is_available() else 'cpu')
    policy=encoder.preprocess['preprocessing']
    if policy['stride_s']!=10 or policy['include_endpoint'] is not False or encoder.preprocess['preprocessor_id']!=PREPROCESSOR_ID:
        raise ValueError('Checkpoint preprocessing does not match the published strict-10-second run')
    return encoder
