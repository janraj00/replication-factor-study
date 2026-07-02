# Preliminary result data

This directory contains small, curated result files committed for visibility. They are not the full generated `results/` tree and should be treated as preliminary evidence only.

Included files:

- `cockroach_rf_sweep_bg_20260617_runs.csv` - per-run results for a completed local CockroachDB sweep.
- `cockroach_rf_sweep_bg_20260617_summary_grouped.csv` - grouped CockroachDB summary with mean/std/count fields.
- `cockroach_rf_ladder_safe_20260625_runs.csv` - per-run results for the validated RF=3,5,7 safe ladder.
- `cockroach_rf_ladder_safe_20260625_summary_grouped.csv` - grouped throughput and validation summary for the safe ladder.
- `hdfs_smoke_runs.csv` - per-run HDFS smoke-test results.
- `hdfs_smoke_summary_grouped.csv` - grouped HDFS smoke-test summary.
- `hdfs_rf_sweep_seed_20260623_runs.csv` - per-run results for a completed local HDFS RF seed sweep.
- `hdfs_rf_sweep_seed_20260623_summary_grouped.csv` - grouped HDFS seed summary with mean/std/count fields.

The safe ladder completed 27/27 runs with zero workload and metric errors, but
it remains preliminary evidence: runs lasted 90 seconds on one shared Docker
host and the 150 QPS target capped the read-only and most 80:20 observations.
Its legacy metrics files contain cumulative quantiles from node 1 rather than
cluster-wide per-run histogram deltas. They are preserved in the raw result
directory but are not curated or used for latency claims.

Both committed CockroachDB datasets predate the corrected all-node histogram
collector. Their grouped CSV files therefore retain QPS and validation fields
but intentionally omit the former `sql_p90_avg` and `kv_p90_avg` columns.

The raw `results/` directory remains ignored because it contains generated logs, plots, per-run metrics, and intermediate files. Larger or final paper-grade datasets should be published separately or added here only as curated summary artifacts.
