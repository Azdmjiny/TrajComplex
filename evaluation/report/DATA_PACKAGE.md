# October 26 data ZIP versus current evaluation

Checked: `Changi_paper_datasets_2026-10-26.zip`, 613 entries, 82,808,873
uncompressed bytes, publication snapshot `fc848d4c741f45d7bd738b32eaad35f5bbfdf33b`.
It is a data handoff snapshot, not the input automatically read by current code.
Current runners take explicit local paths; the report builders read saved results.

| ZIP section | Relationship to current work |
|---|---|
| `01_raw_opensky_10s` | 64 sampled 10-second OpenSky hourly archives for the two 24h days, twelve Holding scenes and four Vectoring scenes; not receiver-level raw messages |
| `02_hourly_main` | 205 files byte-identical to the local deduplicated main package |
| `03_hourly_original_appendix` | 197 files byte-identical to the local original comparator |
| `04_holding` | 37 files byte-identical to the endpoint equal-duration package; does not contain the latest midpoint R²=0.94 report inputs as a complete run package |
| `05_vectoring_15km` | 96 files byte-identical to the original 19-candidate package; not the latest repaired 20-second/26-candidate package |
| `06_weather`, `07_encoder_contract` | Five files match local weather and preprocessing metadata; no checkpoint weights |
| `08_reports` | Four report snapshots still match their sources; the combined paper report has since changed |

All 609 source-file hashes in the ZIP matched its manifest; this is separate
from local availability. Raw members' manifest sources refer to members inside the original
monthly ZIP, not standalone file paths. Do not infer that a missing standalone
path means missing or corrupted observations.

The archive omits later 15/20-second quality matching, repaired route populations
and current 26-candidate evaluation outputs. It also omits STAR, model weights,
training data, and dependency environments. Sharing it alone cannot reproduce
all current main results. No data were unpacked, substituted or overwritten
during this folder organization.
