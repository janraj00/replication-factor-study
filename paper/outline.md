# Paper outline

## Working title

When More Replicas Do Not Help: Testing File-Storage Replication Intuition in Distributed SQL

## Central question

Does replication-factor adaptation, a familiar technique in distributed file
storage, provide a useful performance control in a consensus-based distributed
SQL database?

CockroachDB is the primary object of study. HDFS is used as an architectural
and experimental contrast that explains where the intuition behind changing RF
comes from and why it may not transfer to distributed SQL.

The paper does not propose a new adaptation algorithm. It first tests whether
RF is a sufficiently effective and predictable database control action to
justify such an algorithm.

## Proposed structure

### 1. Introduction and motivation from file storage

- Replication-factor and replica-placement changes are established techniques
  in distributed file systems.
- GFS and HDFS use replicated blocks for durability, locality, and aggregate
  read service.
- Scarlett adapts replication to content popularity; Copysets shows that
  replica placement changes durability and recovery behavior.
- This success creates a tempting systems intuition: a read-heavy workload
  should benefit from more replicas.
- State the gap: database replicas participate in consensus and transactions,
  so this intuition may not apply.
- State the paper's objective: evaluate RF as a database tuning action, using
  file storage as the contrast rather than as an equal research target.

### 2. Why file-system intuition may fail in distributed SQL

#### 2.1 File storage as the source of the intuition

- The HDFS NameNode manages metadata and block placement.
- DataNodes store blocks and serve client reads directly.
- Another replica can become another local or parallel read source.
- The relevant trade-off is read locality and service capacity versus storage,
  replication traffic, and write cost.

#### 2.2 The database execution path

- CockroachDB divides data into ranges represented by Raft groups.
- A Raft leader orders replicated log entries.
- A leaseholder coordinates most strong reads and writes for a range.
- Another voting replica increases fault tolerance and placement flexibility,
  but does not automatically create another strong-read path.
- Follower reads are a separate bounded-staleness mode.

#### 2.3 Consequence for RF tuning

| Tuning question | File storage intuition | Distributed SQL implication |
|---|---|---|
| Can another replica serve reads? | Normally yes, subject to placement | Not for arbitrary strong reads |
| What does RF primarily change? | Number and location of block copies | Consensus group, fault tolerance, placement, and replication fan-out |
| Where can performance improve? | Locality and parallel service | Leaseholder placement or eligible follower reads |
| Main risk | Storage/write/re-replication cost | Coordination, quorum, rebalancing, and write cost |

### 3. Scope and research questions

RQ1. Does increasing RF improve CockroachDB throughput or latency under strong
read-only and mixed read/write workloads?

RQ2. Do the CockroachDB results exhibit the read-scaling behavior that
motivates RF adaptation in file storage?

RQ3. Under which consistency, placement, workload-duration, and geographic
conditions could RF adaptation still be worthwhile in distributed SQL?

### 4. Experimental methodology

#### 4.1 Primary database experiment

- CockroachDB RF ladder.
- Strong read-only and mixed read/write workloads.
- Actual QPS, SQL/KV latency, errors, placement-sensitive behavior.
- Randomized order, repetitions, validation, and saturation reporting.

#### 4.2 File-storage contrast

- HDFS RF 1..5 and parallel reader counts.
- Read and write throughput.
- Used to expose the different read-serving mechanism, not to provide a
  comprehensive comparison of the two products.

#### 4.3 Evidence quality

- Separate pipeline checks, preliminary evidence, and paper-grade evidence.
- Preserve the failed RF=9 local run as environment-limit diagnostics.
- Do not infer geographic locality from a single shared Docker host.

### 5. Results

#### 5.1 CockroachDB

- Throughput and latency by RF and read/write ratio.
- Emphasize the absence or presence of a repeatable monotonic benefit.
- Report achieved QPS, variance, and errors.

#### 5.2 HDFS contrast

- Show that reader parallelism is the dominant effect in the current local
  evidence.
- Explain that HDFS nevertheless has a direct architectural path by which an
  additional block copy may serve demand.
- Avoid turning the section into a product-performance contest.

### 6. Implications for RF tuning in distributed SQL

RF adaptation in the database is plausible only when a concrete database
mechanism is active:

1. stronger failure-domain coverage is itself required;
2. leaseholder placement is improved for the dominant access region;
3. follower reads are acceptable and additional replicas serve local reads;
4. the workload persists long enough to amortize range replication and
   rebalancing; or
5. geographic placement reduces remote reads without making the strong-write
   quorum prohibitively slow.

RF is unlikely to be a useful performance action for short bursts, write-heavy
workloads, strong reads pinned to one leaseholder, or deployments where all
replicas share the same physical bottleneck.

### 7. Threats to validity

- Shared Docker host and cache effects.
- Simplified synthetic CockroachDB workload.
- Placement and leaseholder changes after RF reconfiguration.
- Too few preliminary repetitions for strong inference.
- HDFS is an explanatory contrast, not proof that all file systems benefit
  monotonically from higher RF.

### 8. Conclusion

- File storage provides the motivation, but distributed SQL is the research
  target.
- RF is not automatically a read-scaling parameter in a consensus database.
- A future adaptive database policy is justified only after a repeatable
  benefit is connected to leaseholder, follower-read, geographic, or
  resilience mechanisms.

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
