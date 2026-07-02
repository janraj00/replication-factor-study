# Replication Factor Study: Distributed SQL vs HDFS

This repository contains a reproducible experiment scaffold for comparing replication-factor tuning in:

1. CockroachDB / distributed SQL
2. HDFS / distributed file systems

Core idea:

- In file systems, additional replicas may directly improve read locality and parallel read throughput.
- In distributed SQL databases, replicas participate in consensus; increasing RF may add write/coordination overhead and may not improve strong reads.

## Repository layout

```text
infra/
  local/
    cockroach/        # local 9-node CockroachDB cluster
    hdfs/             # local HDFS NameNode + 5 DataNodes + client
  cloud/              # cloud deployment notes / stage 2
experiments/
  common/
  cockroach/          # RF sweep, workload, metrics, analysis
  hdfs/               # HDFS RF sweep and analysis
paper/                # paper outline / notes
results/              # generated outputs, ignored by git
```

For the latest completed datasets, active experiments, and known limitations,
see `docs/project_status.md`.

## Python setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, use the Python launcher if `python` resolves to the Microsoft Store alias:

```powershell
py -m pip install -r requirements.txt
```

## Local CockroachDB

```bash
cd infra/local/cockroach
docker compose up -d
./init_cluster.sh
cd ../../..
```

Single setup:

```bash
python experiments/cockroach/setup_users.py --rows 90000 --rf 3 --ranges 1
```

## Smoke Tests

Smoke tests verify that the local cluster, workload, metrics, result writing, validation, and analysis paths work. They are intentionally short and are not sufficient for paper claims.

CockroachDB smoke:

```bash
python experiments/cockroach/run_rf_sweep.py \
  --rfs 3 \
  --ratios 80:20 \
  --duration 60 \
  --cooldown 20 \
  --qps-total 300 \
  --workers-per-node 2 \
  --repetitions 1 \
  --read-mode strong \
  --results-dir results/cockroach_smoke
```

CockroachDB small RF smoke sweep:

```bash
python experiments/cockroach/run_rf_sweep.py \
  --rfs 3,4 \
  --ratios 100:0,50:50 \
  --duration 60 \
  --cooldown 20 \
  --qps-total 300 \
  --workers-per-node 2 \
  --repetitions 1 \
  --read-mode strong \
  --results-dir results/cockroach_rf_sweep_small
```

HDFS smoke:

```bash
python experiments/hdfs/run_hdfs_sweep.py \
  --compose-dir infra/local/hdfs \
  --rfs 1,2 \
  --file-size-mb 16 \
  --num-files 2 \
  --readers 1,2 \
  --results-dir results/hdfs_smoke
```

## Paper-Grade Runs

See `docs/experiment_plan.md` for the full design. Recommended local CockroachDB run:

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

Follower-read series:

```bash
python experiments/cockroach/run_rf_sweep.py \
  --rfs 3,4,5,6,7,8,9,10 \
  --ratios 100:0,90:10,80:20,70:30 \
  --duration 180 \
  --cooldown 60 \
  --qps-total 1200 \
  --workers-per-node 2 \
  --repetitions 3 \
  --read-mode follower \
  --shuffle \
  --results-dir results/cockroach_rf_sweep_follower
```

Recommended local HDFS paper-grade run:

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

## Local HDFS

```bash
cd infra/local/hdfs
docker compose up -d
./wait_hdfs.sh
cd ../../..
```

Run RF sweep:

```bash
python experiments/hdfs/run_hdfs_sweep.py \
  --compose-dir infra/local/hdfs \
  --rfs 1,2,3,4,5 \
  --file-size-mb 128 \
  --num-files 8 \
  --readers 1,2,4,8,16 \
  --repetitions 1 \
  --results-dir results/hdfs_rf_sweep
```

## Validation and Analysis

Validate result directories without requiring Docker to be running:

```bash
python scripts/validate_results.py --kind cockroach --results-dir results/cockroach_rf_sweep_small
python scripts/validate_results.py --kind hdfs --results-dir results/hdfs_smoke
```

For paper-grade completeness checks, pass expected matrices:

```bash
python scripts/validate_results.py \
  --kind cockroach \
  --results-dir results/cockroach_rf_sweep_paper \
  --expected-rfs 3,4,5,6,7,8,9 \
  --expected-ratios 0:100,10:90,20:80,30:70,40:60,50:50,60:40,70:30,80:20,90:10,100:0 \
  --expected-repetitions 3 \
  --expected-metric-nodes 9

python scripts/validate_results.py \
  --kind hdfs \
  --results-dir results/hdfs_rf_sweep_paper \
  --expected-rfs 1,2,3,4,5 \
  --expected-readers 1,2,4,8,16 \
  --expected-repetitions 3
```

Analyze results:

```bash
python experiments/cockroach/analyze_results.py --results-dir results/cockroach_rf_sweep_small
python experiments/hdfs/analyze_results.py --results-dir results/hdfs_rf_sweep
```

Analysis writes per-run summaries plus grouped `summary_grouped.csv` / `.xlsx` files with mean, standard deviation, and count fields suitable for plotting error bars.

## Preliminary Data

Small curated preliminary CSV files are tracked under `paper/data/preliminary/` so the repository shows representative outputs without committing the full generated `results/` tree. These files are smoke/local-seed evidence only; final claims should use longer paper-grade runs with repetitions and validation.
## Interpretation Warning

Smoke results show that the pipeline works and can expose obvious failures or broad directional hints. They should not be used as evidence for final paper claims without longer durations, repetitions, validation, and grouped analysis.

## Cloud phase

Start locally first. Once CSV generation is stable, reuse the same experimental logic with remote hosts. See `infra/cloud/README.md`.

