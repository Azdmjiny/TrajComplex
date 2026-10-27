# Historical experiment logs

[Archive index](../README.md)

Twelve run directories preserve five-second screening and dimension/seed evidence.
Each contains settings, history, status, validation, untrained-validation and console
records. Four screening combinations and nine candidates overlap in one run.
See the [screening selection](../reports/result/screening_selection.json) and
[final selection](../reports/result/selection.json).

These delivered text records are not resumable training state. Local training
writes separately to `Encoder/runs/`; do not rename the archive to `runs/`.
