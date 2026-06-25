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

## Current CockroachDB RF ladder

- Directory: `results/cockroach_rf_ladder_safe_20260625`
- RF: 3, 5, 7
- Ratios: 100:0, 80:20, 50:50
- Three repetitions
- 90-second workload, 30-second cooldown
- Target 150 QPS, two workers per node, strong reads, shuffled order
- Logs:
  - `results/cockroach_rf_ladder_safe_20260625.stdout.log`
  - `results/cockroach_rf_ladder_safe_20260625.stderr.log`

At the last manual check, the first run (RF=7, ratio 50:50) completed with zero
errors and 129.75 actual QPS. The sweep was continuing with the next RF=7 run.
Do not stop it merely to inspect progress.

After completion:

1. Validate the full 27-run matrix for RF 3,5,7; ratios 100:0,80:20,50:50; and
   three repetitions.
2. Run the CockroachDB analyzer.
3. Inspect error counts, metrics error rows, actual-vs-target QPS, variance, and
   cluster stability.
4. Curate the run and grouped summary CSV only if the dataset is internally
   complete and suitable as preliminary paper evidence.
5. Regenerate figures and update `paper/short_paper_draft.md` without
   overstating the local result.

## Diagnostic RF=9 attempt

`results/cockroach_rf_ladder_seed_20260623` contains a partial/failed RF=9
attempt that destabilized the local nine-node CockroachDB cluster. Preserve the
data and logs. Treat them only as diagnostic evidence of a local environment
limit; do not mix them into throughput curves or paper-grade comparisons.

## Known follow-up work

- Complete and evaluate the safe RF=3,5,7 CockroachDB ladder.
- Add CockroachDB latency figures if metric coverage is consistent.
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
