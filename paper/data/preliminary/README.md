# Preliminary result data

This directory contains small, curated result files committed for visibility. They are not the full generated `results/` tree and should be treated as preliminary evidence only.

Included files:

- `cockroach_rf_sweep_bg_20260617_runs.csv` - per-run results for a completed local CockroachDB sweep.
- `cockroach_rf_sweep_bg_20260617_summary_grouped.csv` - grouped CockroachDB summary with mean/std/count fields.
- `hdfs_smoke_runs.csv` - per-run HDFS smoke-test results.
- `hdfs_smoke_summary_grouped.csv` - grouped HDFS smoke-test summary.
- `hdfs_rf_sweep_seed_20260623_runs.csv` - per-run results for a completed local HDFS RF seed sweep.
- `hdfs_rf_sweep_seed_20260623_summary_grouped.csv` - grouped HDFS seed summary with mean/std/count fields.

The raw `results/` directory remains ignored because it contains generated logs, plots, per-run metrics, and intermediate files. Larger or final paper-grade datasets should be published separately or added here only as curated summary artifacts.
