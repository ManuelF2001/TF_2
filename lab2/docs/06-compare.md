# Part 6 – Compare across groups

## Our rows for the class table (Part 1)

From `01-wait-for-some.md` (3 runs per cell; *lin* = linearizable runs out
of 3; *complete* = which operations clients could complete).

| configuration | scenario | predicted | observed |
|---|---|---|---|
| ROWA (1,3) | no faults | lin; all complete | **lin 3/3**; all complete |
| ROWA (1,3) | latency 50, rate 50 | NOT lin (divergent replicas); all complete | **NOT lin 0/3** |
| ROWA (1,3) | n1 crashes | lin (likely); no write completes after 5 s | **lin 3/3**; 0 writes ok after the crash || ROWA (1,3) | partitions | NOT lin; writes blocked during partitions | **NOT lin 2/3** (1/3 lin: a short partition); writes blocked |
| majority (2,2) | no faults | lin (likely; rare anomalies possible) | **lin 3/3** |
| majority (2,2) | latency 50, rate 50 | NOT lin | **NOT lin 0/3** |
| majority (2,2) | n1 crashes | lin (likely); all servers but n1 available | **lin 3/3** |
| majority (2,2) | partitions | NOT lin; minority side blocked | **lin 3/3** (stale-copy window not hit); minority blocked, rings block everyone |
| non-intersecting (1,2) | no faults | lin (likely) | **lin 3/3** |
| non-intersecting (1,2) | latency 50, rate 50 | NOT lin (stale reads) | **NOT lin 0/3** |
| non-intersecting (1,2) | n1 crashes | lin (likely) | **lin 3/3** |
| non-intersecting (1,2) | partitions | NOT lin (isolated server reads its stale copy) | **NOT lin 0/3** |

*(Replace this with the class table once the other groups have added
their rows.)*

## 1. Did all groups observe the same results? Where not, why?

We expect agreement on the **robust** cells and disagreement on the
**probabilistic** ones:

- **Robust**: every configuration under latency + load is non-linearizable
  (anomalies need concurrent operations on a key and a window of tens of
  ms; at 50 req/s with 50 ms latency there are hundreds of such windows).
  Availability results are robust too: they follow from counting answers
  (ROWA writes stop when any server is down, majority keeps working with
  one crash).
- **Probabilistic**: no faults and one crash at 10 req/s with ~0 latency.
  An anomaly needs two writes on the same key within ~1 ms of each other,
  or a read in the same window: rare but possible, so a group may see one
  NOT-linearizable run where we saw three linearizable ones. A valid run is
  *not* evidence of correctness, only of not having hit the window.
- **Partitions** depend on the random partitions Maelstrom chose (which
  node is isolated, when, for how long) and on what clients did meanwhile;
  two groups' runs are different executions.
- **Design choices** of Part 1 Q1 change results: a group whose reader
  returned "the most recent answer" or "a majority value" fails in other
  executions than ours (own copy first). With values only, every rule is
  wrong in some execution, so all groups should see failures under load.
- **Machine**: timing depends on load; on WSL the wall clock may jump
  (`worklog.md` §5), which does not change verdicts but can mislead
  timelines.

## 2. Taking over a lock whose holder may have crashed, without two holders

A waiting server cannot tell a crashed holder from a slow one (asynchrony),
so "the holder seems dead, I take the lock" can produce two holders if the
old one was only slow or partitioned and later finishes its cas. Two safe
ways:

1. **Fencing tokens / ballots (no timing assumption for safety).** Every
   lock acquisition carries a number higher than any number seen before
   (e.g. `(counter, node id)`, learnt from the lock quorum, as versions are
   in Part 2). A server that grants or sees number b **rejects** every later
   `get`/`put` carrying a number lower than b. A taker-over acquires with a
   higher number at a majority; from then on the old holder's puts are
   rejected by at least one server of every write quorum (majorities
   intersect), so it cannot complete a write: at most one holder *can act*.
   The new holder must first read the latest value from its quorum (the
   old holder may have written at some servers) and finish or redo it.
   This is exactly the **prepare/accept** structure of Paxos (ballot =
   fencing token).
2. **Leases (safety depends on timing).** A lock is granted for a bounded
   time T and expires by itself; the holder stops acting before T − ε by its
   own clock. Safe only if clocks drift less than ε, i.e. under a partially
   synchronous model. Simple, but a paused process (GC, VM stall, like our
   WSL clock jumps!) can outlive its lease.

Practical systems combine both: a lease to avoid waiting forever, a
fencing token so that a holder whose lease expired cannot do damage.
