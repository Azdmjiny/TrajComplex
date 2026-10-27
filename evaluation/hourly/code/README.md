# Hourly reporting code

`report_changi_hourly.py` reads the complete private saved-result package and
creates a new report directory. `hourly_report_text.py` supplies the report;
`test_changi_hourly_report.py` verifies saved attempts, counts and NA handling.
No Encoder, D fit, sampling or missing-value filling is performed by this builder.

```bash
python evaluation/hourly/code/report_changi_hourly.py --input LOCAL_SAVED_PACKAGE --preprocessing position-dedup --output NEW_DIRECTORY
```

Use `--preprocessing original` with the original package for the appendix.
Set `CHANGI_HOURLY_INPUT` and `CHANGI_HOURLY_POLICY` for saved-record tests.
