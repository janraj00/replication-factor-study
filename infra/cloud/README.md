# Cloud phase: stage 2

Do cloud only after local CSV output is stable.

## CockroachDB

Recommended first cloud variant:

- CockroachDB Cloud or self-hosted CockroachDB.
- 3 load-generator VMs in different regions, e.g. eu-central-1, us-east-1, ap-southeast-1.
- Reuse `experiments/cockroach/load_workload.py` and `collect_metrics.py`.
- Move node host/port configuration from `NODE_PORTS` to environment/config file.

More advanced variant:

- Kubernetes deployment with CockroachDB operator/Helm.
- Use the same RF sweep runner, but setup users and metrics run against the cluster endpoint.

## HDFS

Meaningful HDFS cloud run should use multiple VMs, not one Docker host:

- 1 NameNode VM
- 5 DataNode VMs
- 1 benchmark client VM

Then replace Docker Compose calls in `experiments/hdfs/run_hdfs_sweep.py` with SSH commands.

## Why cloud later?

The local version validates:

- experimental loop,
- CSV schema,
- metric parser,
- plots,
- workload bugs.

Cloud should change deployment, not the experiment logic.
