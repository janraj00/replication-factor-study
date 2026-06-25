# Paper outline

## Working title

When More Replicas Do Not Help: Conditions for Effective Replication-Factor Tuning in Distributed SQL and File Storage

## Central question

Under which architectural and workload conditions does changing the replication
factor provide a performance benefit large enough to justify its storage,
network, coordination, and reconfiguration costs?

The paper does not propose a new replication algorithm. It evaluates whether
replication-factor adaptation is a useful control action in two systems where
the same parameter has different operational meaning.

## Proposed structure

### 1. Introduction and related motivation

- Replication-factor and replica-placement changes are established control
  mechanisms in distributed file systems.
- GFS and HDFS expose replicated blocks/chunks as a durability and locality
  mechanism.
- Scarlett adapts replication to skewed content popularity.
- Copysets shows that replica placement, not only replica count, changes
  durability and recovery behavior.
- Motivate the gap: the file-system intuition that another copy is another
  possible read source does not transfer directly to consensus-based SQL.
- State the paper's narrow objective: determine whether and when changing RF
  is worthwhile, rather than design another adaptive policy.

### 2. Architectural contrast

#### 2.1 HDFS: metadata coordination and data-serving workers

- The NameNode manages namespace, block locations, and placement decisions.
- DataNodes store blocks and serve client reads directly.
- More replicas may provide locality, parallel read sources, load spreading,
  and resilience across failure domains.
- Costs include storage capacity, replication traffic, write-pipeline length,
  re-replication, and rebalancing.

#### 2.2 CockroachDB: replicated state machines

- Data is divided into ranges; each range is a Raft replication group.
- A Raft leader orders replicated log entries, while a leaseholder coordinates
  most strong reads and writes for a range.
- More voting replicas change fault tolerance, quorum topology, replication
  fan-out, and placement options; they do not automatically create independent
  strong-read paths.
- Follower reads are a separate consistency/performance mode and should not be
  mixed with strong-read results.

#### 2.3 Mechanism-level comparison

| Question | HDFS | CockroachDB |
|---|---|---|
| What is replicated? | File blocks | Transactional key ranges and Raft log/state |
| Who serves normal reads? | A selected DataNode replica | Usually the range leaseholder for strong reads |
| What can another replica add? | Locality, read source, failure-domain coverage | Fault tolerance, placement flexibility, possible follower-read locality |
| Main incremental cost | Storage and data-transfer/write-pipeline cost | Storage, replication fan-out, quorum/coordination and rebalancing cost |
| When is performance benefit plausible? | Concurrent or geographically local reads | Local follower reads, better leaseholder placement, or resilience-driven placement |

### 3. Scope and research questions

RQ1. How does HDFS RF affect read throughput as reader parallelism increases?

RQ2. How does CockroachDB RF affect throughput and latency under strong
read-only and mixed read/write workloads?

RQ3. Which observed effects come from RF itself, and which are dominated by
reader count, leaseholder placement, saturation, caching, or shared-host
contention?

RQ4. Under which workload, consistency, and geographic conditions is an RF
change likely to repay its cost?

### 4. Experimental methodology

- CockroachDB: RF ladder, workload read/write ratios, actual QPS, latency,
  errors, randomized order, repetitions, and validation.
- HDFS: RF 1..5, parallel readers, read and write throughput, randomized order,
  repetitions, and validation.
- Separate pipeline checks, preliminary evidence, and paper-grade evidence.
- Report low achieved QPS as saturation rather than silently treating target
  throughput as controlled.

### 5. Results

- CockroachDB strong-read and mixed-workload throughput/latency.
- HDFS read throughput by RF and reader count, plus write cost by RF.
- Report uncertainty and non-monotonic behavior.
- Do not claim that RF improves file-system reads unless larger multi-host
  evidence isolates locality or load-spreading effects.

### 6. When changing RF pays off

An RF increase is most defensible when at least one of these mechanisms is
active:

1. A higher failure tolerance or failure-domain requirement is itself worth
   the cost.
2. Additional replicas can actually serve reads and are placed near readers or
   computation.
3. A hot object or range persists long enough for re-replication and
   rebalancing costs to be amortized.
4. Geographic placement avoids remote reads without placing every strong write
   on a slower WAN quorum path.
5. The system is bottlenecked at replica-serving nodes rather than at a shared
   disk, client, leaseholder, or host scheduler.

It is unlikely to pay for short-lived bursts, write-heavy workloads, strong
reads pinned to one leaseholder, or local single-host experiments where all
logical replicas share the same physical resources.

### 7. Threats to validity

- Shared Docker host and cache effects.
- Simplified synthetic workloads.
- Placement and leaseholder changes after RF reconfiguration.
- Preliminary datasets have too few repetitions for strong inference.
- HDFS locality cannot be demonstrated convincingly without multiple physical
  hosts/racks or controlled network topology.

### 8. Conclusion

- RF is not a universal performance knob.
- Replica count is useful only through a concrete mechanism: failure-domain
  coverage, locality, parallel service, or consistency-aware placement.
- The architectural mechanism should be identified before building an
  adaptive RF controller.

## Initial references

1. Ghemawat, Gobioff, and Leung. *The Google File System*. SOSP 2003.
2. Shvachko, Kuang, Radia, and Chansler. *The Hadoop Distributed File System*.
   MSST 2010.
3. Ananthanarayanan et al. *Scarlett: Coping with Skewed Content Popularity in
   MapReduce Clusters*. EuroSys 2011.
4. Cidon et al. *Copysets: Reducing the Frequency of Data Loss in Cloud
   Storage*. USENIX ATC 2013.
5. Ongaro and Ousterhout. *In Search of an Understandable Consensus Algorithm*.
   USENIX ATC 2014.
6. Taft et al. *CockroachDB: The Resilient Geo-Distributed SQL Database*.
   SIGMOD 2020.
7. Corbett et al. *Spanner: Google's Globally-Distributed Database*. OSDI 2012.
