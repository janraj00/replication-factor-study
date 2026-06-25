# When More Replicas Do Not Help: Conditions for Effective Replication-Factor Tuning in Distributed SQL and File Storage

## Abstract

Replication factor is a familiar control parameter in distributed storage, but an additional replica does not provide the same capability in every architecture. In file systems, an extra block copy may improve durability, locality, load distribution, or parallel read capacity. In consensus-based distributed SQL, a replica participates in a replicated state machine, and strong reads and writes remain constrained by Raft, quorum formation, and leaseholder placement. This paper asks a deliberately narrower question than prior adaptive-replication work: not how to design a new replication algorithm, but whether and under which conditions changing replication factor is a useful performance action at all. We compare CockroachDB with HDFS using reproducible replication-factor sweeps. Preliminary local results show no clear monotonic CockroachDB throughput benefit under strong reads or mixed workloads; in HDFS, reader parallelism has a much larger effect than replication factor in the current single-host setup. These results are preliminary, but they motivate a mechanism-based decision rule: RF changes pay only when additional replicas enable useful failure-domain coverage, read locality, parallel service, or consistency-aware geographic placement that outweighs storage, transfer, rebalancing, and coordination costs.

Keywords: replication factor, distributed SQL, CockroachDB, HDFS, consensus, distributed storage, performance evaluation

## 1. Introduction and Related Motivation

Replication level and replica placement are established control mechanisms in distributed file systems. GFS stores chunks across commodity machines to provide fault tolerance and high aggregate performance [1]. HDFS similarly exposes a configurable per-file replication factor and uses rack-aware placement and nearest-replica selection to balance reliability, write traffic, and read locality [2]. Later systems made replication more explicitly workload-aware. Scarlett creates additional replicas for popular content in MapReduce clusters [3], while Copyset Replication demonstrates that the placement pattern of a fixed number of replicas can materially change durability and recovery behavior [4]. Together, this literature makes replica count and placement look like natural tuning dimensions.

That intuition is architecture-dependent. In a distributed file system, another block replica can become another physical read source. In a distributed SQL database, another voting replica joins a consistency and transaction protocol. Raft orders replicated state-machine updates through a leader and commits log entries after quorum agreement [5]. CockroachDB applies this model to replicated key ranges and combines it with leaseholders and distributed transaction processing [6]. Increasing RF therefore changes fault tolerance, replication fan-out, quorum topology, and placement choices, but it does not automatically create another independent path for strongly consistent reads.

This paper investigates the practical consequence of that difference. Instead of proposing another adaptive replication policy, it first asks whether changing RF is a useful action for the workload and architecture under study. The comparison uses HDFS as a block-replicated file system and CockroachDB as a consensus-based distributed SQL system. The goal is not to identify one universally optimal RF. It is to determine which mechanisms can make an RF change beneficial, which costs oppose it, and which measurements are needed before an adaptive controller would be justified.

The contribution of this short paper is threefold:

1. It provides a mechanism-level comparison of replication in HDFS and CockroachDB.
2. It evaluates RF as a candidate control action, without introducing a new adaptation algorithm.
3. It provides a reproducible experimental scaffold and a decision framework for identifying when an RF change can plausibly repay its cost.

## 2. Architectural Contrast

### 2.1 HDFS: Metadata Coordination and Data-Serving Workers

HDFS separates metadata coordination from the data path. The NameNode manages the file-system namespace, block locations, replication decisions, and placement policy. DataNodes store blocks and serve client reads and writes. After obtaining block locations from the NameNode, a client transfers data directly to or from DataNodes. This architecture is often described historically as master/slave, although metadata-master and data-serving worker roles are more precise terms and modern HDFS deployments can add NameNode high availability.

The RF is configurable per file and can be changed after creation [2]. An additional replica can improve resilience, place data in another rack or data center, give a reader a closer source, or distribute concurrent reads across more storage nodes. None of these benefits is automatic. They depend on placement, topology, scheduling, caching, and sufficient concurrent demand. The costs are also direct: additional storage, replication traffic, longer or more expensive write pipelines, and background work when RF is changed.

### 2.2 CockroachDB: Raft Groups, Leaders, and Leaseholders

CockroachDB partitions data into ranges, each represented by a Raft replication group [6]. The Raft leader orders log entries for the group. A range leaseholder coordinates most strongly consistent reads and proposes writes, although the Raft leader and leaseholder need not be conceptually identical. A write is not simply copied to passive storage nodes; it becomes a replicated state-machine operation that must reach a quorum before commitment.

Increasing the number of voting replicas changes the number and distribution of failure domains the range can tolerate. It also changes replication fan-out and, at some RF transitions, the majority size required for commitment. For strong reads, additional replicas do not behave like arbitrary nearest HDFS block sources because requests are normally constrained by leaseholder and transaction semantics. CockroachDB follower reads can use non-leaseholder replicas, including geographically closer replicas, but they use a bounded-staleness model and should therefore be evaluated as a separate consistency/performance mode.

### 2.3 Mechanism-Level Comparison

| Question | HDFS | CockroachDB |
|---|---|---|
| Replicated unit | File block | Transactional key range and Raft state |
| Normal read-serving path | Selected DataNode replica | Usually the range leaseholder for strong reads |
| Potential benefit of another replica | Locality, parallel read source, load spreading, failure-domain coverage | Failure tolerance, placement flexibility, and follower-read locality |
| Main incremental cost | Storage, transfer, write pipeline, and re-replication | Storage, replication fan-out, quorum/coordination, and rebalancing |
| Main condition for read benefit | The added copy is placed usefully and can serve demand | The read mode and placement permit the added replica to serve locally |

The central contrast is therefore not “file systems benefit from RF and databases do not.” It is that a replica is useful only through an active mechanism. HDFS exposes direct replica selection on the read path. CockroachDB exposes consensus participation and, under specific read modes and placement policies, geographically distributed read service. The experiments test whether those mechanisms are visible under controlled workloads.

## 3. Study Scope and Research Questions

The study intentionally stops before algorithm design. An adaptive controller is useful only if changing RF produces a repeatable benefit, the workload remains in the beneficial regime long enough to amortize reconfiguration, and the controller can observe the mechanism that causes the benefit. The paper therefore evaluates RF as a candidate action rather than proposing when or how a controller should trigger it.

This paper is organized around four research questions:

RQ1. How does HDFS RF affect read throughput as reader parallelism increases?

RQ2. How does CockroachDB RF affect throughput and latency under strong read-only and mixed read/write workloads?

RQ3. Which observed effects come from RF itself, and which are dominated by reader count, leaseholder placement, saturation, caching, or shared-host contention?

RQ4. Under which workload, consistency, and geographic conditions is an RF change likely to repay its storage, transfer, coordination, and rebalancing costs?

## 4. Experimental Methodology

### 4.1 CockroachDB Setup

The CockroachDB experiment uses a local Docker Compose cluster with nine CockroachDB nodes. A benchmark table is recreated before each run. The replication factor is varied, and workloads are generated with configurable read/write ratios. For each run, the experiment records target and actual throughput, read and write success counts, error counts, SQL-level latency metrics, KV execution latency metrics, and process memory metrics where available.

The current preliminary sweep uses replication factors 3, 4, and 5, read/write ratios 100:0, 80:20, and 50:50, two repetitions, randomized run order, 90 seconds of workload duration, 30 seconds of cooldown, and a target of 250 QPS. These settings are intentionally smaller than the intended paper-grade experiment, but they are sufficient to test the pipeline and expose early behavior.

Paper-grade runs should extend this design to more repetitions and longer durations. The current safe local ladder uses RF=3, 5, and 7. Higher RF values should be included only in an environment that can sustain them without destabilizing the cluster; the failed local RF=9 attempt is diagnostic evidence about an environment limit and must not be mixed into performance curves. Runs should remain randomized and should include validation that all containers remain live and all error counts remain zero.

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

## 6. When Changing Replication Factor Pays Off

The preliminary results do not support a rule such as “increase RF for read-heavy workloads.” They instead suggest a conditional decision: an RF change is useful only when it activates a concrete mechanism whose value exceeds the cost of creating and maintaining the replicas.

### 6.1 Reliability and Failure-Domain Requirements

The clearest reason to increase RF is not performance but a required failure-tolerance level. Additional replicas can protect against more node failures or allow placement across racks, availability zones, or regions. However, replica count alone is insufficient: Copysets shows that the correlation structure of placement can matter as much as the nominal number of copies [4]. In both HDFS and CockroachDB, the decision should therefore be expressed as a failure-domain and placement requirement, not merely as a larger integer.

### 6.2 Read Locality and Parallel Service

An RF increase can improve performance when new replicas are eligible to serve reads and are placed where they remove a bottleneck. In HDFS, the client can select a nearby block replica, and several readers may distribute work over multiple DataNodes. This mechanism is plausible for persistent hot files, rack-local analytics, and computation scheduled near data. Scarlett is an example of exploiting this mechanism by adding replicas for popular content [3].

The current local HDFS results do not yet demonstrate that effect. Reader count dominates RF, and all containers share one host, disk subsystem, and cache hierarchy. A paper-grade locality claim requires multiple physical hosts or an emulated topology in which replica placement and network distance are controlled.

### 6.3 Geographic Replication

Geography makes RF valuable when placement converts remote access into local access. In file storage, a regional copy can reduce read latency and WAN bandwidth if clients are allowed to read that copy. In distributed SQL, geographically distributed replicas primarily provide survivability and placement options. Strong writes still need a quorum, so spreading voters across distant regions can put WAN latency on the commit path. Systems such as Spanner demonstrate the value of explicit geographic placement and consistency-aware replication [7], but also show that global replication is a topology and protocol decision rather than a free consequence of increasing RF.

For CockroachDB, a geographically close replica becomes a performance asset only if the leaseholder is placed appropriately or the application can use follower reads with acceptable staleness. Otherwise, another remote voting replica may improve resilience without improving foreground read latency. The paper should therefore distinguish three cases: strong leaseholder reads, bounded-staleness follower reads, and writes requiring a geographically distributed quorum.

### 6.4 Amortizing Reconfiguration Cost

Dynamic RF changes create replicas, move data, and trigger rebalancing. The beneficial workload regime must last long enough to amortize that work. Replicating a persistently hot file may be worthwhile; reacting to a short burst may finish only after the burst has disappeared. The same issue applies to CockroachDB ranges, where RF changes can overlap with lease transfers, range movement, compaction, and background maintenance.

### 6.5 Conditions Where RF Is Unlikely to Help

An RF increase is unlikely to improve performance when:

1. strong reads remain concentrated at one leaseholder;
2. the workload is write-heavy and additional replicas mainly add replication work;
3. all logical replicas share the same physical disk, host scheduler, or network bottleneck;
4. the workload spike is shorter than replica creation and rebalancing;
5. placement does not put replicas near readers or across useful failure domains; or
6. achieved throughput is already limited by the client or workload generator.

These conditions explain why non-monotonic curves are not merely experimental inconvenience. RF changes interact with placement, cache state, range movement, memory pressure, and scheduling. Repeated randomized experiments and error bars are therefore necessary, but even statistically stable results must still be tied to a mechanism.

## 7. Threats to Validity

The current experiments run on a local Docker setup, so all nodes share the same physical CPU, memory, disk, and network resources. This limits the realism of network locality and can amplify local scheduler and storage effects. Docker Desktop and the host operating system may also introduce noise.

The CockroachDB workload currently uses a simplified table and controlled synthetic operations. This makes interpretation easier, but it may not represent application-level workloads with multiple tables, indexes, transactions, and skewed access patterns. RF changes can also trigger background rebalancing or compaction, which may affect adjacent runs.

The HDFS seed sweep uses synthetic zero-filled files, only two repetitions, and a local Docker deployment. This is useful for validating the comparison and observing parallel-reader behavior, but it remains vulnerable to cache effects and shared-host artifacts. Future runs should use larger files, more files, more repetitions, and ideally a multi-host HDFS deployment.

Finally, the present results are preliminary. They support the motivation and experimental direction, but paper-grade claims require longer runs, more repetitions, broader RF coverage, and a clearer comparison between strong CockroachDB reads, optional follower reads, and HDFS parallel reads.

## 8. Conclusion

This paper argues that replication factor should be treated as a mechanism-dependent control, not a universal performance knob. In HDFS, another block replica can provide failure-domain coverage, locality, or an additional read source. In CockroachDB, another voting replica primarily changes fault tolerance, placement, and the replicated state-machine topology; it improves read performance only when leaseholder or follower-read behavior allows the replica to serve useful demand.

The current preliminary evidence does not justify a new RF adaptation algorithm. CockroachDB shows no simple monotonic throughput improvement under strong reads and mixed workloads, while HDFS throughput in the local setup scales mainly with reader parallelism rather than RF. The practical conclusion is narrower and more useful: change RF only when an identified benefit—durability, failure-domain coverage, local read service, parallel service, or consistency-aware geographic placement—can plausibly exceed storage, network, write, coordination, and reconfiguration costs.

## References

1. S. Ghemawat, H. Gobioff, and S.-T. Leung. “The Google File System.” *Proceedings of the 19th ACM Symposium on Operating Systems Principles (SOSP)*, 2003. https://doi.org/10.1145/945445.945450
2. K. Shvachko, H. Kuang, S. Radia, and R. Chansler. “The Hadoop Distributed File System.” *2010 IEEE 26th Symposium on Mass Storage Systems and Technologies (MSST)*, 2010. https://doi.org/10.1109/MSST.2010.5496972
3. G. Ananthanarayanan, S. Agarwal, S. Kandula, A. Greenberg, I. Stoica, D. Harlan, and E. Harris. “Scarlett: Coping with Skewed Content Popularity in MapReduce Clusters.” *Proceedings of EuroSys*, 2011. https://doi.org/10.1145/1966445.1966472
4. A. Cidon, S. M. Rumble, R. Stutsman, S. Katti, J. Ousterhout, and M. Rosenblum. “Copysets: Reducing the Frequency of Data Loss in Cloud Storage.” *USENIX Annual Technical Conference*, 2013. https://www.usenix.org/conference/atc13/technical-sessions/presentation/cidon
5. D. Ongaro and J. Ousterhout. “In Search of an Understandable Consensus Algorithm.” *USENIX Annual Technical Conference*, 2014. https://www.usenix.org/conference/atc14/technical-sessions/presentation/ongaro
6. R. Taft et al. “CockroachDB: The Resilient Geo-Distributed SQL Database.” *Proceedings of the 2020 ACM SIGMOD International Conference on Management of Data*, 2020. https://doi.org/10.1145/3318464.3386134
7. J. C. Corbett et al. “Spanner: Google’s Globally-Distributed Database.” *10th USENIX Symposium on Operating Systems Design and Implementation (OSDI)*, 2012. https://www.usenix.org/conference/osdi12/technical-sessions/presentation/corbett
