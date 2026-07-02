# Project Status

Last updated: 2026-06-25.

## Research direction

The project compares the performance meaning of replication factor in
consensus-based distributed SQL and replicated file storage. The working
argument is architectural: additional HDFS block copies may provide more
read-serving opportunities, while additional CockroachDB voting replicas do
not form generic independent strong-read paths and may add coordination cost.

The current evidence is local and preliminary. Final claims still require
longer, repeated, validated experiments and careful reporting of shared-host
limitations.

## Completed clean datasets

### CockroachDB preliminary seed

- Directory: `results/cockroach_rf_sweep_bg_20260617`
- RF: 3, 4, 5
- Ratios: 100:0, 80:20, 50:50
- Two repetitions, 90 seconds, target 250 QPS
- 18/18 runs completed
- Zero workload errors
- Validation: PASS
- Curated CSV: `paper/data/preliminary/cockroach_rf_sweep_bg_20260617_*`

### HDFS preliminary seed

- Directory: `results/hdfs_rf_sweep_seed_20260623`
- RF: 1 through 5
- Four 64 MB files
- Readers: 1, 2, 4, 8
- Two repetitions
- 40/40 measurements completed
- Validation: PASS
- Curated CSV: `paper/data/preliminary/hdfs_rf_sweep_seed_20260623_*`

### CockroachDB safe RF ladder

- Directory: `results/cockroach_rf_ladder_safe_20260625`
- RF: 3, 5, 7
- Ratios: 100:0, 80:20, 50:50
- Three repetitions
- 90-second workload, 30-second cooldown
- Target 150 QPS, two workers per node, strong reads, shuffled order
- Logs:
  - `results/cockroach_rf_ladder_safe_20260625.stdout.log`
  - `results/cockroach_rf_ladder_safe_20260625.stderr.log`
- 27/27 runs completed
- Zero connect, read, write, and metrics-collection errors
- Validation: PASS
- Cluster after completion: 9/9 containers running
- Curated CSV: `paper/data/preliminary/cockroach_rf_ladder_safe_20260625_*`

Mean actual QPS (standard deviation):

| Ratio | RF=3 | RF=5 | RF=7 |
|---|---:|---:|---:|
| 100:0 | 149.71 (0.30) | 149.71 (0.27) | 149.47 (0.67) |
| 80:20 | 149.37 (0.57) | 149.80 (0.16) | 145.24 (6.00) |
| 50:50 | 133.20 (6.84) | 138.50 (13.33) | 129.86 (16.14) |

The read-only series and most 80:20 runs reached the configured 150 QPS cap,
so they demonstrate stability but not maximum capacity. The 50:50 series shows
saturation, substantial run-to-run variation, and no monotonic RF benefit.

The ladder used the legacy metrics collector, which stored cumulative p90/p99
snapshots from node 1. Those values cannot be interpreted as cluster-wide
per-run latency and are excluded from curated metric summaries and paper
claims. The collector now records raw histogram buckets and counters from all
nodes, while the workload records client-observed latency. A repeat run is
needed for valid latency figures. Treat the current ladder as strong
preliminary target-attainment evidence, not paper-grade proof.

## Diagnostic RF=9 attempt

`results/cockroach_rf_ladder_seed_20260623` contains a partial/failed RF=9
attempt that destabilized the local nine-node CockroachDB cluster. Preserve the
data and logs. Treat them only as diagnostic evidence of a local environment
limit; do not mix them into throughput curves or paper-grade comparisons.

## Known follow-up work

- Repeat key CockroachDB cases with at least 180-second runs and a load sweep
  that exposes the saturation boundary instead of capping results at 150 QPS.
- Add CockroachDB latency figures after checking metric resolution and
  aggregation semantics.
- Run a larger HDFS paper-grade sweep with larger data, at least three
  repetitions, and documented cache handling.
- Decide whether follower reads belong in the main comparison or future work.
- Add and verify related-work citations before submission.

## Useful files

- Experiment design: `docs/experiment_plan.md`
- Validation: `scripts/validate_results.py`
- CockroachDB analysis: `experiments/cockroach/analyze_results.py`
- HDFS analysis: `experiments/hdfs/analyze_results.py`
- Figure generation: `scripts/plot_preliminary_figures.py`
- Paper draft: `paper/short_paper_draft.md`
