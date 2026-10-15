# ATSCC project environment

This repository includes the original `requirements.txt`, which records a Conda environment with CUDA-specific PyTorch builds. For this Apple Silicon machine, use the pip-compatible CPU/MPS environment described by `requirements-venv.txt`.

## Create and activate

From the repository root:

```bash
cd ATSCC
/usr/bin/python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade 'pip<25'
python -m pip install -r requirements-venv.txt
```

The environment is Python 3.9 and uses the matching PyTorch 2.4.1/torchaudio 2.4.1/torchvision 0.19.1 releases. CUDA packages are intentionally not used on macOS arm64; PyTorch can use CPU or MPS when available.

## Verify

From `ATSCC/` with the environment activated:

```bash
python -c "import atscc, datautils, model.GPT, losses.losses, tasks; print('ATSCC imports: OK')"
python -c "import torch; from model.GPT import TSGPTEncoder; from losses.losses import flat_snnl; m=TSGPTEncoder(9, 16, 32, 4, 1, 64, 0.0).cpu(); x=torch.randn(2, 8, 9); labels=torch.tensor([[0.,0.,1.,1.,2.,2.,3.,3.],[4.,4.,5.,5.,6.,6.,7.,7.]]); y=m(x); loss=flat_snnl(y, labels, temperature=5.0, portion=1.0); loss.backward(); assert y.shape == (2, 8, 16) and torch.isfinite(loss) and m.pre_proj.weight.grad is not None; print('CPU forward/loss/backward: OK', tuple(y.shape), float(loss))"
```

The configured training scaffold no longer requires W&B login. It needs audited,
pre-split ENU trajectory `.npy` files; run `python train.py --help` from `ATSCC/`
or `python -m ATSCC.train --help` from the workspace root. Real data/GPU training
and research-quality evaluation remain outside the environment smoke test.
See `../doc/atscc-handoff.md` for tuning, checkpoints and complexity integration.
