# When More Replicas Do Not Help: Replication Factor Tuning in Distributed SQL and File Storage Systems

## Abstract

Replication is commonly associated with higher availability and, in some storage systems, better read performance. This intuition is especially strong in distributed file systems, where additional replicas can improve data locality and allow more parallel read paths. In distributed SQL databases, however, replicas are not only passive copies of data: they participate in consensus, leaseholder placement, and coordinated read/write paths. This paper studies whether increasing the replication factor has comparable performance effects in these two architectural settings. We compare CockroachDB, a consensus-based distributed SQL database, with an HDFS-like replicated file storage setup. Preliminary local experiments show that increasing the replication factor in CockroachDB does not provide a clear monotonic throughput benefit under strong reads and mixed read/write workloads, while HDFS read throughput scales mainly with reader parallelism. The central claim is that replication factor is architecture-dependent: in consensus-based SQL systems it should not be treated as a generic read-scaling parameter. The current results should be treated as preliminary, but they support the broader argument that replication factor tuning must be interpreted through system architecture rather than as a universal performance knob.

Keywords: replication factor, distributed SQL, CockroachDB, HDFS, consensus, distributed storage, performance evaluation

## 1. Introduction

Replication is one of the central mechanisms used by distributed systems to improve fault tolerance and availability. A replicated system can continue operating after node failures, and in some architectures replicas can also improve performance by serving reads from multiple locations. Because of this, increasing the replication factor is often intuitively understood as a way to make a system "stronger": more copies should mean better durability, better availability, and potentially better read throughput.

This intuition is only partly correct. The meaning of an additional replica depends strongly on the architecture of the system. In distributed file systems, such as HDFS, replicas primarily represent additional physical copies of blocks. These copies may improve read locality and allow several readers to access different replicas in parallel. In distributed SQL databases, such as CockroachDB, replicas are part of a transactional and consensus-based execution path. Writes must be replicated through Raft, strong reads are affected by leaseholder placement, and additional replicas may increase coordination cost without improving the critical path for many queries.

This paper investigates the practical consequences of this difference. Instead of asking whether replication is good in general, we ask a narrower question: does increasing the replication factor improve performance in the same way for distributed SQL and distributed file storage systems? The motivation comes from earlier work on adaptive replication in CockroachDB, where replication-factor changes produced limited and workload-dependent benefits. Here, the focus shifts from designing an adaptive algorithm to comparing the architectural role of replicas across two system classes.

The contribution of this short paper is threefold:

1. It formulates replication factor tuning as an architectural comparison between consensus-based distributed SQL and replicated file storage.
2. It provides a reproducible experimental scaffold for CockroachDB and HDFS replication-factor sweeps.
3. It reports preliminary local results and identifies the additional measurements required for paper-grade conclusions.

## 2. Background and Motivation

### 2.1 Replication in File Storage Systems

In a distributed file system, data is commonly divided into blocks and each block is stored on multiple data nodes. The replication factor determines how many copies of each block are maintained. A higher replication factor can improve fault tolerance because the system can lose more nodes without losing the data. It can also improve read performance in some scenarios: if several replicas are available, the client or scheduler may choose a nearby or less loaded replica, and parallel readers may avoid competing for the same physical node.

The performance impact is not automatic. Writes become more expensive because each block must be copied to more nodes. Read improvements depend on block placement, network topology, cache effects, and the number of concurrent readers. Still, the architectural role of a replica in file storage is relatively direct: it is an additional copy that can potentially serve reads.

### 2.2 Replication in Distributed SQL

Distributed SQL databases use replication for fault tolerance and consistency, but the execution path is more constrained. CockroachDB stores data in ranges. Each range is replicated across nodes and coordinated using Raft. One replica acts as the leaseholder for a range, and strongly consistent reads and writes are tied to this coordination structure.

This means that increasing the replication factor does not simply create more independent read-serving copies. For writes, additional voting replicas can increase the cost of consensus and replication. For strong reads, requests may still be served through leaseholder-related paths rather than arbitrary nearest replicas. Follower reads can change this behavior, but they relax freshness guarantees and therefore represent a different read mode.

The key motivation of this paper is that the same parameter, replication factor, has different operational meaning in these two systems. A replication-factor sweep should therefore not be interpreted as a generic tuning experiment. It is also a probe of the underlying architecture.

### 2.3 Related Work Positioning

This work is positioned between three areas of prior work. The first is distributed database replication, where replication is closely tied to consistency, consensus, quorum formation, and transaction processing. In this setting, additional replicas are not merely extra read copies; they can change the coordination path of writes and strongly consistent reads.

The second area is distributed file storage, where block replication is traditionally used for durability, availability, and locality-aware reads. HDFS-style systems make the performance role of replication more direct, although the actual benefit still depends on block placement, parallelism, caching, and network topology.

The third area is adaptive replication and workload-aware placement. The present paper builds on earlier experiments with adaptive replication in CockroachDB, but shifts the main question. Instead of proposing a new adaptation algorithm, it asks why the same replication-factor knob behaves differently across system architectures.

## 3. Research Questions

This paper is organized around four research questions:

RQ1. Does increasing replication factor improve read-heavy workloads in CockroachDB under strong consistency?

RQ2. How does replication factor affect mixed read/write workloads in CockroachDB?

RQ3. Does replication factor show a different performance pattern in HDFS-style replicated file storage?

RQ4. Which architectural mechanisms explain the observed differences?

## 4. Experimental Methodology

### 4.1 CockroachDB Setup

The CockroachDB experiment uses a local Docker Compose cluster with nine CockroachDB nodes. A benchmark table is recreated before each run. The replication factor is varied, and workloads are generated with configurable read/write ratios. For each run, the experiment records target and actual throughput, read and write success counts, error counts, SQL-level latency metrics, KV execution latency metrics, and process memory metrics where available.

The current preliminary sweep uses replication factors 3, 4, and 5, read/write ratios 100:0, 80:20, and 50:50, two repetitions, randomized run order, 90 seconds of workload duration, 30 seconds of cooldown, and a target of 250 QPS. These settings are intentionally smaller than the intended paper-grade experiment, but they are sufficient to test the pipeline and expose early behavior.

Paper-grade runs should extend this design to more repetitions, longer durations, and a broader RF ladder such as 3, 5, 7, and 9 or the complete range 3 through 9. Runs should remain randomized and should include validation that all containers remain live and all error counts remain zero.

### 4.2 HDFS Setup

The HDFS experiment uses a local Docker Compose setup with one NameNode, five DataNodes, and one client container. For each replication factor, the benchmark writes a dataset to HDFS, waits for the requested replication factor to be applied, and then measures read throughput with different numbers of parallel readers.

The current HDFS seed sweep uses replication factors 1 through 5, four 64 MB files, reader counts 1, 2, 4, and 8, two repetitions, and randomized run order. This is still smaller than the intended paper-grade experiment, but it is substantially more informative than the initial smoke test because it covers the full local HDFS RF range and multiple parallel-read levels.

Paper-grade HDFS runs should extend this design to larger files, more files, higher reader counts where stable, and at least three repetitions.

### 4.3 Reproducibility and Validation

The repository includes scripts for running sweeps, collecting metrics, validating result directories, and generating grouped summaries. Each main sweep writes metadata describing the command line, platform, Python version, working directory, selected environment variables, and experiment parameters. Generated raw result directories are ignored by Git, while small curated preliminary CSV files are tracked under `paper/data/preliminary/`.

## 5. Preliminary Results

The current CockroachDB preliminary sweep completed 18 out of 18 planned runs with zero connect, read, and write errors. Table 1 summarizes actual throughput grouped by replication factor and read/write ratio.

Table 1. Preliminary CockroachDB throughput summary.

| Ratio | RF=3 mean QPS | RF=4 mean QPS | RF=5 mean QPS |
|---|---:|---:|---:|
| 100:0 | 232.15 | 242.34 | 248.99 |
| 80:20 | 184.28 | 180.41 | 218.39 |
| 50:50 | 172.55 | 148.94 | 162.21 |

![Figure 1. Preliminary CockroachDB throughput by replication factor.](figures/preliminary_cockroach_qps.png)

For the read-only workload, throughput remains in a similar range and increases slightly from RF=3 to RF=5. This does not show a large read-scaling effect from additional replicas. For the mixed workloads, the behavior is non-monotonic. In the 50:50 workload, RF=4 and RF=5 do not improve on RF=3 in the preliminary mean. In the 80:20 workload, RF=5 performs better than RF=3 and RF=4, but the standard deviation is also high, suggesting sensitivity to leaseholder placement, local resource contention, and background system activity.

These early results should therefore not be read as evidence that one specific RF is always optimal. A more careful interpretation is that increasing RF in CockroachDB under strong reads does not provide a simple or predictable throughput gain. The result is consistent with the architectural expectation that additional replicas participate in coordination rather than acting as independent read-serving copies.

The HDFS seed sweep completed 40 out of 40 planned measurements and passed validation. It used RF=1..5, two repetitions, four 64 MB files, and reader counts 1, 2, 4, and 8. Table 2 summarizes read throughput.

Table 2. Preliminary HDFS read throughput summary in MB/s.

| RF | 1 reader | 2 readers | 4 readers | 8 readers |
|---:|---:|---:|---:|---:|
| 1 | 14.67 | 26.13 | 40.69 | 49.73 |
| 2 | 15.87 | 25.05 | 38.59 | 43.92 |
| 3 | 16.56 | 27.86 | 40.06 | 48.82 |
| 4 | 17.48 | 27.24 | 40.46 | 53.24 |
| 5 | 16.21 | 26.01 | 39.87 | 50.12 |

![Figure 2. Preliminary HDFS read throughput by parallel readers.](figures/preliminary_hdfs_read_throughput.png)

The clearest HDFS pattern is not monotonic improvement with RF, but scaling with the number of parallel readers. Moving from one reader to eight readers increases read throughput by roughly three times across all RF settings. The RF effect is smaller and non-monotonic in the local Docker setup: RF=4 is best for one and eight readers, while RF=3 is best for two readers and RF=1 is close to the best case for four readers. This supports a careful interpretation: HDFS replication creates additional possible read-serving copies, but the observed benefit depends on local placement, caching, container scheduling, and reader parallelism.

## 6. Discussion

The preliminary CockroachDB results align with the central architectural argument. Strongly consistent distributed SQL workloads cannot be interpreted through the same lens as replicated file reads. A higher replication factor can improve fault tolerance, but it also changes the consensus group and may introduce additional replication and coordination work. If reads are routed through leaseholders or constrained by transactional consistency, more replicas do not automatically translate into more useful read paths.

By contrast, file storage replication creates additional block copies that can potentially serve reads. The HDFS seed results show a clear throughput increase with reader parallelism, while RF itself remains noisy and non-monotonic in the local setup. This is still useful for the paper: it shows that the file-storage experiment exposes a different performance axis from the CockroachDB experiment. In HDFS, the primary scaling dimension in this seed run is the number of concurrent readers over replicated blocks; in CockroachDB, strong SQL workloads remain constrained by consensus and leaseholder-related execution paths.

The non-monotonic behavior observed in preliminary CockroachDB data is also important. A clean monotonic curve would be easy to explain, but it would hide the complexity of the system. In practice, RF changes interact with leaseholder placement, range movement, memory pressure, local Docker scheduling, and background maintenance. This strengthens the case for repeated randomized experiments and error bars rather than single-run claims.

## 7. Threats to Validity

The current experiments run on a local Docker setup, so all nodes share the same physical CPU, memory, disk, and network resources. This limits the realism of network locality and can amplify local scheduler and storage effects. Docker Desktop and the host operating system may also introduce noise.

The CockroachDB workload currently uses a simplified table and controlled synthetic operations. This makes interpretation easier, but it may not represent application-level workloads with multiple tables, indexes, transactions, and skewed access patterns. RF changes can also trigger background rebalancing or compaction, which may affect adjacent runs.

The HDFS seed sweep uses synthetic zero-filled files, only two repetitions, and a local Docker deployment. This is useful for validating the comparison and observing parallel-reader behavior, but it remains vulnerable to cache effects and shared-host artifacts. Future runs should use larger files, more files, more repetitions, and ideally a multi-host HDFS deployment.

Finally, the present results are preliminary. They support the motivation and experimental direction, but paper-grade claims require longer runs, more repetitions, broader RF coverage, and a clearer comparison between strong CockroachDB reads, optional follower reads, and HDFS parallel reads.

## 8. Conclusion

This paper argues that replication factor tuning must be interpreted through the architecture of the target system. In file storage systems, replicas can directly provide additional read-serving copies. In distributed SQL databases, replicas participate in consensus and strongly consistent execution paths, so additional replicas may increase coordination cost without producing a proportional performance benefit. Therefore, RF should not be treated as a generic read-scaling parameter in consensus-based SQL systems.

The current repository provides a reproducible scaffold for evaluating this claim. Preliminary CockroachDB results show no simple monotonic throughput improvement from increasing RF under strong reads and mixed workloads. Preliminary HDFS results show that read throughput scales clearly with parallel readers, while RF effects remain smaller and noisy in the local Docker setup. The next step is to extend both sides with longer repeated runs: a CockroachDB RF ladder across higher RF values and a larger HDFS sweep with more data and repetitions.

## Next Writing Tasks

1. Replace preliminary tables with paper-grade grouped summaries once longer runs are available.
2. Add latency figures for SQL p90/KV p90 with error bars.
3. Replace the brief related-work positioning with cited related work.
4. Decide whether to include follower reads as a separate experiment or as future work.
5. Shorten the final version to the target venue length after the results section stabilizes.
