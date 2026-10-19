# Historical experiment logs

[Encoder overview](../README.md)

The 12 run directories preserve screening and dimension/seed evidence. Each contains `settings.json`, `history.json`, `status.json`, `validation.json`, `untrained_validation.json`, and `console.log`.

The four screening combinations and the nine dimension/seed candidates overlap in one run, giving 12 unique directories. See [screening selection](../reports/screening_selection.json) and [final selection](../reports/selection.json).

These are historical delivered logs, not resumable training state. Live training writes to the separately ignored `../runs/` directory. Do not delete screening runs merely because they were not selected, or rename these logs to `runs/`.
