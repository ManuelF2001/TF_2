# Theory for Lab 2 – Quorums

Everything in this lab follows from a few ideas. Read this first; the other
documents refer to its sections (§1 … §9).

## 1. Where Lab 1 left us

Lab 1 (strategy D, "primary for everything") was always linearizable but
only as available as one server, n0. The question it ended with: *is there
a middle ground between waiting for one server and waiting for all of them?*

- **Wait for one** (each server answers alone, Lab 1's independent servers):
  available, but a read may miss a write done elsewhere: stale reads.
- **Wait for all** (write to every copy before answering): every copy has
  every completed write, but a single crashed server blocks every write.

Quorums sit in between: every operation waits for **some** of the N servers.

## 2. Quorums and the intersection condition

N servers. A **write** is acknowledged after **Qw** servers have stored it;
a **read** returns after **Qr** servers have answered. Which Qw and which
Qr servers answer is not chosen: it is whoever answers first.

**Read–write intersection.** If `Qr + Qw > N`, then *any* Qr servers and
*any* Qw servers share at least one server (pigeonhole: Qr + Qw servers
cannot fit into N distinct boxes without one box twice). So a read that
starts after a write has *completed* asks at least one server that has that
write.

**Write–write intersection.** If `2·Qw > N` (equivalently `Qw > N/2`), any
two write quorums share a server. Not needed for reads to see writes, but
needed whenever two *competing* operations must notice each other: two
lock holders (Part 4), two leaders.

| N = 3 | Qw = 1 | Qw = 2 | Qw = 3 |
|---|---|---|---|
| **Qr = 1** | no | no (Part 1 "non-intersecting") | **yes** (ROWA) |
| **Qr = 2** | no | **yes** (majority) | yes |
| **Qr = 3** | **yes** (RAWO: read-all, write-one) | yes | yes |

**Intersection is necessary, not sufficient.** The read *receives* the new
value from at least one server, but it must also *recognise* it as the
newest among the answers (§3), and servers must not have overwritten it
with an older value (§4).

## 3. Versions: knowing which value is newest

A value alone says nothing about its age. A reader that gets `{n0: 3, n1: 7}`
cannot know whether 3 or 7 was written last. The fix: store with each value
a **version** (also called timestamp or tag), produced when the value is
written, and order values by version.

Who produces the version and how matters:

- **The coordinator asks a read quorum first** (two-phase write; this is the
  write of the ABD algorithm, Attiya–Bar-Noy–Dolev 1995): get the versions
  from Qr servers, take the highest, add 1. Because of §2, the highest seen
  is at least the version of every *completed* write, so the new version is
  higher. Cost: one extra round trip per write. *(Our `q2.py`.)*
- **The coordinator uses its own copy** (a Lamport-clock-like counter): no
  extra round trip, but the coordinator may not be in the write quorum of
  the latest write, so its version can be *older* than a completed write;
  the new write is then ignored by the servers: a lost write.
  *(`q2local.py`, used for comparison.)*
- **Physical clocks**: needs synchronised clocks; any drift reorders writes.
  Not used.

Servers keep only the value with the highest version they have seen
("last writer wins", where "last" means highest version, not latest
arrival).

## 4. Concurrent writers and tie-breaking

Two writes that run at the same time can both read the same highest version
v and both choose v + 1. Then servers that received them in different
orders keep different values with the same version, and readers cannot
agree: replicas **diverge**. The fix needs no extra message: make versions
unique and totally ordered by appending a writer id and comparing
lexicographically, `(number, writer)`. Every server and every reader
applies the same rule and picks the same winner.

The writer id must be unique among *concurrent* writes: we use the
**client id** (`c6`, …), because two clients of the same server can write
concurrently and a node id would tie again; a client has one operation at
a time (`q3.py`).

## 5. Completed writes vs writes in progress: regular vs atomic

With §2–§4 (intersection + versions + tie-break), a read that starts after a
write **completed** returns that write or a newer one. That is the
guarantee of a **regular register** (Lamport 1986). It says nothing about a
write that is **still in progress**: a read that overlaps it may return the
old or the new value. And two reads that overlap the same write, one after
the other, may return **new, then old** (a *new–old inversion*):

```
write(x,1) at n0:  n0 stores 1 ...................... (puts to n1, n2 slow)
read A via n0:     asks n0 (1), n1 (0)  -> returns 1  (done)
read B via n1:     asks n1 (0), n2 (0)  -> returns 0  (starts after A ended)
```

Read A must be ordered after the write (it saw 1), read B after read A,
so B should also see 1: **not linearizable**. Linearizability (an *atomic*
register) needs the read to make sure the value it returns is at a write
quorum before returning it: **write-back** (also called read repair, ABD's
second read phase). Then any later read intersects that quorum. Cost: a
read takes two round trips instead of one, unless the read already sees the
value at a write quorum. *(Going further, `qx.py`.)*

## 6. Why cas needs more than quorums

`cas(k, from, to)` is a read-modify-write: "if the value is `from`, make it
`to`". Done as quorum read + compare + quorum write, two cas from the same
value can both read `from`, both decide to write, and both succeed: one of
the two updates is **lost**, and no sequential order explains two
successes (after the first, the value is no longer `from`). With a single
server this is impossible, because it executes one request at a time
between the read and the write. Quorums make reads see completed writes;
they do not make the read-and-write *atomic* with respect to other
operations.

Formally: a read/write register has **consensus number 1** (Herlihy 1991),
cas has consensus number ∞; no protocol built only from reads and writes
can implement cas in an asynchronous system with failures. Something
stronger is needed: mutual exclusion (a lock), a single leader that orders
operations, or consensus (Paxos/Raft).

## 7. Locks over quorums

To make cas atomic, take a **lock** on the key at a **lock quorum** of Ql
servers before the cas, release it after. Two lock quorums must intersect
so that two operations never both hold the lock: `2·Ql > N`, i.e. a
majority, the write–write condition of §2. A server grants a key's lock to
one owner at a time.

Two things go wrong with locks in an asynchronous system with crashes:

- **The holder crashes** (or is partitioned away) while holding the lock:
  nobody releases it; the key is **blocked forever** for every cas and write.
  Waiting for it is not an option and taking it over is dangerous: the
  holder may just be slow (an asynchronous system cannot tell the two
  apart), and two holders would break mutual exclusion.
- **Competing requesters** each lock part of the quorum (n0 at n0, n1 at n1,
  N = 3): neither has a majority. If both wait, it is a **deadlock**; if
  both release and retry at the same moment, a **livelock**. Random backoff
  makes repeated collisions unlikely, never impossible.

Safe takeover needs **leases** (locks that expire, with bounded clock
drift: a timing assumption) or **ballots/fencing tokens**: every new lock
holder gets a higher number, servers reject operations carrying a lower
number than one they have seen. That is the core idea of Paxos (Part 6,
question 2, `06-compare.md`).

## 8. Availability of quorum systems

With crash failures, an operation needing Q answers out of N can complete
while at most `N − Q` servers are down. So:

| N = 5 | reads tolerate (N − Qr) | one-phase writes tolerate (N − Qw) | **our** two-phase writes tolerate min(N − Qr, N − Qw) |
|---|---|---|---|
| majority (3,3) | 2 | 2 | 2 |
| ROWA (1,5) | 4 | **0** | 0 |
| (2,4) | 3 | 1 | 1 |
| (4,2) | 1 | 3 | **1** |

Under the condition Qr + Qw > N, `(N − Qr) + (N − Qw) < N`: tolerance of
reads and of writes trade against each other; majority is the only
configuration that tolerates ⌊(N−1)/2⌋ crashes for **both**.

In a **partition**, a client is served only if its server can reach Q
servers on its side. Majority quorums: only the majority side (if one
exists) can work. ROWA: reads work everywhere; writes nowhere.

Our writes take two phases (§3): phase 1 needs Qr answers, phase 2 Qw. So
a write needs **both** quorums: with ROWA (1,5), phase 1 is local and free,
and phase 2 needs all five. With (4,2), a write needs four servers for its
phase 1! (`03-concurrent-writers.md` §3 measures this.)

**Messages per operation** do not depend on Qr and Qw in our protocol: the
coordinator *sends to all* N servers and waits for the first Q answers;
the others still answer. Quorum sizes change *how long we wait* (latency)
and *how many failures we survive*, not how many messages are sent.

## 9. Linearizability vs sequential consistency

For a history of operations (invocation, response) on a key:

- **Linearizable**: there is a total order of the operations that
  (a) respects the sequential specification (each read returns the last
  write before it), and (b) respects **real time**: if A responds before B
  is invoked, A comes before B. Operations without response (`info`) may be
  placed anywhere after their invocation, or left out.
- **Sequentially consistent**: same, but (b) is weakened to respect only
  the **order of each client's own operations** (program order), not real
  time across clients.

So every linearizable history is sequentially consistent, not conversely.
The new–old inversion of §5 by *two different clients* is sequentially
consistent (put read B before the write, then the write, then read A) but
not linearizable. If the *same client* did both reads, program order would
force A before B: then it is not sequentially consistent either
(`05-explain-execution.md`).

A lost update (§6, two cas from the same value both succeed) is neither:
no total order at all can make both cas succeed.

## 10. Glossary

| term | meaning |
|---|---|
| coordinator | the server that received the client request and runs the quorum protocol |
| replica | any server, as receiver of `get` / `put` / `lock` from a coordinator |
| Qr, Qw, Ql | read, write, lock quorum sizes |
| ROWA | read-one/write-all, (1, N) |
| tag | our version: `[number, writer client id]` |
| write-back | read phase 2: store the value read at a write quorum before answering |
| regular register | read returns the last completed write or one that overlaps it |
| atomic register | linearizable register |
| ok / fail / info | Maelstrom: done / surely not done / unknown (see Lab 1 `theory.md` §3) |
