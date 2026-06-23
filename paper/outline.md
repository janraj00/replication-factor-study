# Paper outline

## Working title

When More Replicas Do Not Help: Replication Factor Tuning in Distributed SQL and File Storage Systems

## Core claim

Dynamic replication is well-motivated in distributed file systems, where additional replicas may directly improve read locality and throughput. In distributed SQL databases, replicas participate in consensus, and strong reads/writes are coordinated through leaseholders/Raft leaders. Therefore, increasing replication factor may increase coordination overhead without proportional read benefits.

## RQs

RQ1. Does increasing RF improve read-heavy workloads in CockroachDB?

RQ2. How do SQL-level and KV-level latency metrics differ under RF changes?

RQ3. Does RF tuning show different behavior in HDFS-like file storage?

RQ4. Which architectural differences explain the results?

## Experiments

1. CockroachDB RF sweep: RF 3..10, read/write ratios 0.0..1.0, SQL p90, KV p90, throughput, errors.
2. HDFS RF sweep: RF 1..5, write throughput and parallel read throughput.
3. Discussion: closest-replica reads in file systems vs leaseholder/Raft in distributed SQL.

## Preliminary smoke results

These results are smoke tests only. They verify that the local pipeline can start clusters, run workloads, collect metrics, write CSV files, validate results, and produce summaries. They are not sufficient for paper-grade claims.

CockroachDB smoke and small sweep:

- RF=3, ratio 80:20, 60s, target 300 QPS: completed with zero connect/read/write errors and about 246.8 actual QPS.
- RF=3, ratio 100:0, 60s, target 300 QPS: about 298.9 actual QPS, zero read/write/connect errors.
- RF=4, ratio 100:0, 60s, target 300 QPS: about 298.3 actual QPS, zero read/write/connect errors.
- RF=3, ratio 50:50, 60s, target 300 QPS: about 200.7 actual QPS, zero read/write/connect errors.
- RF=4, ratio 50:50, 60s, target 300 QPS: about 182.0 actual QPS, zero read/write/connect errors.

HDFS smoke:

- RF=1, 16 MB files, 2 files: write throughput about 2.70 MB/s; read throughput about 4.68 MB/s with 1 reader and 8.13 MB/s with 2 readers.
- RF=2, 16 MB files, 2 files: write throughput about 2.99 MB/s; read throughput about 4.79 MB/s with 1 reader and 8.03 MB/s with 2 readers.

Preliminary interpretation:

- The CockroachDB smoke does not show a read-heavy throughput benefit from RF=4 over RF=3.
- In the 50:50 mixed workload, RF=4 was lower throughput than RF=3 in the smoke run.
- The HDFS smoke confirms that the RF/readers measurement path works, but the files are too small and repetitions too few for final claims.

## Threats to validity

- Local Docker experiments run all nodes on one physical machine, so CPU, memory, disk, and network resources are shared.
- Docker Desktop and WSL2 can introduce scheduler and storage artifacts.
- CockroachDB RF changes can trigger rebalancing, replica movement, compaction, and other background work that affects adjacent runs.
- Strong reads in CockroachDB often go through leaseholders, so read-heavy SQL behavior should not be interpreted like nearest-replica file reads.
- Single-table and single-range smoke tests simplify interpretation but may underrepresent realistic distributed SQL workloads.
- HDFS smoke tests use small zero-filled files and may be strongly affected by page cache and Docker storage cache.
- Short duration and single repetition smoke tests cannot support statistical inference.
- Paper-grade runs need repeated randomized sweeps, validation, and mean/std/count summaries.
