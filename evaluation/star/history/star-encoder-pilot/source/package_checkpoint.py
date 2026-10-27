"""Package the fixed-epoch-90 last checkpoint with its preprocessing metadata.

train.py stores ``preprocess`` only in best.pt. The approved protocol for this
comparison is the fixed final epoch, so last.pt is used and the prepared
preprocess.json is attached explicitly. No model selection by validation loss
is introduced.
"""
from pathlib import Path
import json
import shutil
import torch

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "encoder-10s" / "source"
RUN = SOURCE / "runs" / "star90_seed43"
OUT = SOURCE / "encoder_star"


def main():
    state = torch.load(RUN / "last.pt", map_location="cpu", weights_only=False)
    if state["epoch"] != 90:
        raise ValueError(f"expected fixed epoch 90, got {state['epoch']}")
    state["preprocess"] = json.loads((SOURCE / "prepared_star" / "preprocess.json").read_text(encoding="utf8"))
    state["checkpoint_protocol"] = "fixed epoch 90; not selected by validation loss"
    OUT.mkdir(parents=True, exist_ok=True)
    torch.save(state, OUT / "encoder.pt")
    (OUT / "preprocess.json").write_text(json.dumps(state["preprocess"], indent=2), encoding="utf8")
    (OUT / "settings.json").write_text(json.dumps(state["settings"], indent=2), encoding="utf8")
    history = json.loads((RUN / "history.json").read_text(encoding="utf8"))
    print(json.dumps(dict(epoch=state["epoch"], final_train=history[-1]["train_loss"],
                          final_validation=history[-1]["validation_loss"],
                          checkpoint=str(OUT / "encoder.pt")), indent=2))


if __name__ == "__main__":
    main()
