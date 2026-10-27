# Saved experiment evidence

[Encoder overview](../README.md)

This archive contains saved evidence for both the current 10-second model and
historical five-second experiments. Archive means preserved records, not that
every result is obsolete. Numerical records, original plans, logs and model
bytes retain their original content; paths mentioned inside those records refer
to their original execution layout.

| Evidence | Location |
|---|---|
| Current 10-second results | [RESULTS_10s_ZH.md](reports/RESULTS_10s_ZH.md), [training report](reports/training-report-10s.md) |
| Current checkpoint identity | [selection](reports/result/selection_10s.json), [verification](reports/result/export_verification.json) |
| Five-second plans | [PLAN.md](PLAN.md), [PROTOCOL.md](PROTOCOL.md) |
| Nine five-second candidate weights | [checkpoints/](checkpoints/README.md) |
| Twelve historical text logs | [experiment_logs/](experiment_logs/README.md) |
| Reports, statistics and shared split provenance | [reports/](reports/README.md) |
| Old dataset-wide pooled embeddings | [encoder/embeddings-5s-old.npz](encoder/embeddings-5s-old.npz) |

## Original paths

The former `Encoder/checkpoints/`, `experiment_logs/`, `reports/`, `PLAN.md` and
`PROTOCOL.md` moved here intact. The former
`Encoder/encoder/embeddings-5s-old.npz` is now `archive/encoder/embeddings-5s-old.npz`.
Resolve candidate-manifest `checkpoints/...` paths relative to this archive.
The current frozen checkpoint remains outside the archive at `../encoder/encoder.pt`.

The current 10-second run reused the historical split membership. Saved split
records remain relevant even though most neighboring comparisons used five-second
sampling. Archived logs are not resumable training states.

The two 10-second reports contain different final-loss values. Both originals are
preserved; this layout change does not choose or recompute those values. Checkpoint
identity is established by its SHA-256 and selection/export records.

## Source and preprocessing notes

The experiment used the six local RKSIa TSV files and statistics labels from the
author-provided ATFMTraj dataset. Exact versions are identified by the original
file hashes in [data_audit.json](reports/result/data_audit.json).

According to the authors' dataset card, RKSI data originate from OpenSky and
Airportal. Upstream coordinates were converted to ENU, resampled at one-second
intervals, smoothed, divided by 120 km, and padded with NaN. The current model
restores metre units, samples every ten seconds, and does not append an off-grid
endpoint. Class labels combine STAR, IAF, and runway information; they are used
only for evaluation grouping, not self-supervised training.

Pages 3–4 of the supplied `ITSC_2026_ZhiJunLim.pdf` were used to check the smaller
backbone, input/output normalization, and signed GeM formula. That paper is not
redistributed here. Formal data/method references are in the
[Encoder README](../README.md#sources-and-citation).

The historical runtime issue references Microsoft's
[PowerShell telemetry documentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_telemetry).
The outbound-blocking launcher affects only the experiment process tree and does
not change the user's global configuration.
