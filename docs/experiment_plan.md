# Experiment Plan

This project compares replication factor (RF) behavior in CockroachDB, a distributed SQL database with consensus replication, and HDFS, a distributed file system where replication primarily affects placement, durability, and read locality.

## Run Classes

Smoke tests are short runs used to verify that Docker Compose, workload generation, metrics collection, CSV writing, validation, and analysis work end to end. Smoke results may reveal obvious directionality, but they are not sufficient for paper claims.

Paper-grade runs are longer, repeated, randomized where practical, validated, and analyzed with summary statistics. They should be run on an otherwise idle machine with fixed software versions and recorded metadata.

## CockroachDB Design

Recommended local cluster:

- 9 CockroachDB nodes.
- One benchmark table, recreated for each RF.
- RF sweep: `3,4,5,6,7,8,9`.
- Optional RF=10 only if CockroachDB accepts the zone configuration on the 9-node cluster and the resulting quorum/placement behavior is documented.
- Read/write ratios: `0:100,10:90,20:80,30:70,40:60,50:50,60:40,70:30,80:20,90:10,100:0`.
- Duration: at least `180s` per run.
- Cooldown: at least `60s` before and after each workload.
- Repetitions: at least `3`; prefer `5` if total runtime is acceptable.
- QPS levels: start with `300` for local stability, then use `600` and `1200` as stress levels if zero-error operation is maintained.
- Workers: keep `--workers-per-node 2` unless the QPS target is not reached; document any change.
- Run order: use `--shuffle` for paper-grade runs to reduce bias from thermal effects, background compactions, and monotonic RF ordering.

Primary CockroachDB metrics:

- `qps_actual`
- `reads_ok`, `reads_err`, `writes_ok`, `writes_err`, `connect_err`
- `sql.service.latency-p90`
- `sql.service.latency-p99`
- `exec.latency-p90`
- `exec.latency-p99`
- `sql.select.count`
- `sql.insert.count`
- `sql.update.count`
- `sql.delete.count`
- `sys.rss`

Quality checks:

- All expected RF/ratio/repetition combinations exist.
- `reads_err`, `writes_err`, and `connect_err` are zero.
- Metrics CSV files exist, are readable, and contain no `__error__` rows.
- Actual QPS is reported for every run; if actual QPS is far below target, interpret throughput as saturation behavior rather than target-controlled behavior.
- Docker containers remain live after each batch.
- Metadata includes command line, platform, Python version, parameters, environment, and git state when available.

## HDFS Design

Recommended local cluster:

- 1 NameNode, 5 DataNodes, 1 client.
- RF sweep: `1,2,3,4,5`.
- File sizes: use `128 MB` for local paper-grade runs; if runtime permits, repeat key cases with `512 MB`.
- Number of files: at least `8`, preferably `16` for higher reader counts.
- Parallel readers: `1,2,4,8,16`.
- Repetitions: at least `3`; prefer `5` if total runtime is acceptable.
- Run order: use `--shuffle` to randomize RF and reader order within repetitions.

Primary HDFS metrics:

- `write_elapsed_s`
- `write_throughput_mb_s`
- `read_elapsed_s`
- `read_throughput_mb_s`
- `single_read_avg_s`
- `single_read_max_s`
- `rf`, `readers`, `rep`, `file_size_mb`, `num_files`

Quality checks:

- All expected RF/reader/repetition combinations exist.
- HDFS reports 5 live DataNodes before paper-grade runs.
- Write and read throughputs are positive.
- Replication is forced with `hdfs dfs -setrep -w`.
- Metadata file is present in the result directory.

## Recommended Commands

CockroachDB paper-grade local run:

```bash
python experiments/cockroach/run_rf_sweep.py \
  --rfs 3,4,5,6,7,8,9 \
  --ratios 0:100,10:90,20:80,30:70,40:60,50:50,60:40,70:30,80:20,90:10,100:0 \
  --duration 180 \
  --cooldown 60 \
  --qps-total 300 \
  --workers-per-node 2 \
  --repetitions 3 \
  --read-mode strong \
  --shuffle \
  --results-dir results/cockroach_rf_sweep_paper
```

HDFS paper-grade local run:

```bash
python experiments/hdfs/run_hdfs_sweep.py \
  --compose-dir infra/local/hdfs \
  --rfs 1,2,3,4,5 \
  --file-size-mb 128 \
  --num-files 8 \
  --readers 1,2,4,8,16 \
  --repetitions 3 \
  --shuffle \
  --results-dir results/hdfs_rf_sweep_paper
```

## Threats to Validity

- Local Docker experiments share CPU, memory, disk, and network resources on one host.
- Docker Desktop and WSL2 can add scheduling and I/O artifacts.
- CockroachDB RF changes can trigger rebalancing or background work that affects adjacent runs.
- Single-table and single-range setups simplify workload interpretation but may underrepresent realistic distributed SQL behavior.
- Strong reads in CockroachDB go through leaseholders, so read-heavy SQL results should not be interpreted like nearest-replica file reads.
- HDFS experiments use synthetic zero-filled files, not application-level file formats.
- OS page cache and Docker storage cache can affect HDFS read results.
- Smoke tests are short and have too few repetitions for statistical claims.
