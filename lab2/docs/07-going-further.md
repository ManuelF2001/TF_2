# Going further – a read that cannot go back in time

Program: `code/qx.py` = `q3.py` + write-back on reads (`code.md` §8,
`decisions.md` D10). Runs: lines `qx.py` of `results/results.tsv`.

## 1. The change, and why it removes the inversion

The execution of Part 3 Q4 (`03-concurrent-writers.md` §4–5): read A sees
a write that is still on fewer than QW servers and returns it; read B,
later, is answered by servers that have not received it and returns the
old value. Read A returned a value **without making sure later reads
would see it**.

New read:

1. phase 1 as before: ask all, take the highest `[tag, value]` among QR
   answers;
2. **write-back**: unless at least QW of those answers already carry that
   tag, send it as a normal `put` to all servers and wait for QW
   acknowledgements **before** answering the client.

**Why the inversion becomes impossible.** When read A returns value v
with tag t, t is stored at a write quorum (either it already was, or A
put it there). Any read B that starts after A returned asks a read
quorum, which intersects that write quorum (QR + QW > N), so B sees a tag
≥ t and returns v or something newer. Reads now behave like completed
writes: once a value has been returned, it can never be "un-returned".
Together with Part 3's tags this is the ABD algorithm, and its reads and
writes are linearizable (an **atomic** register, `theory.md` §5).

The skip rule (≥ QW answers already have the tag) is an optimisation: in
that case the value is already at a write quorum, which is all phase 2
would achieve.

## 2. Evidence

| scenario | q3.py (Part 3) | **qx.py** (write-back) |
|---|---|---|
| slow-n0 (`SLOW_PUT=n0=0.5`, latency 10, rate 50) | **0/3** linearizable | **3/3** linearizable (640/314/0 · 666/315/0 · 630/328/0) |
| majority (2,2), latency 50, rate 50 | 5/5 (≈ 540 ok, 3.29 msgs/op) | 3/3 (471/326/0 · 468/295/0 · 490/307/0, **3.83** msgs/op) |
| N = 5, majority (3,3), no faults | yes, 6.56 msgs/op | yes, 6.67 msgs/op |
| N = 5, ROWA (1,5), no faults | yes, 6.22 msgs/op | yes, **10.77** msgs/op |
| N = 5, ROWA (1,5), n1 crashes at 5 s | yes; **reads continue** (62 ok after 5 s) | yes; **no read completes** after 5 s (0 ok, 60 fail) |
| N = 5, ROWA (1,5), partitions | **NO** (inversion, §5 of Part 3) | yes, but 18 ok / 154 fail / 40 info |

How often reads had to write back (trace `read … write_back=`):

| run | reads with write-back | reads without |
|---|---|---|
| slow-n0 (3 runs) | 43 · 40 · 46 | 436 · 449 · 418 |
| (2,2) latency 50 (3 runs) | 101 · 114 · 108 | 218 · 192 · 211 |
| (3,3) N = 5, no faults | 0 | 102 |
| ROWA (1,5) (3 runs) | **all** (113 · 71 · 85) | 0 |

The slow-n0 runs are the direct test: the same fault that broke q3.py in
3 runs out of 3 leaves qx.py linearizable in 3 out of 3. The reads that
found n0's not-yet-propagated value now pushed it to a write quorum before
answering (≈ 45 per run).

## 3. What it costs

- **Latency of reads**: a write-back read takes two round trips instead of
  one. Under latency 50, a third of the reads wrote back (the others saw
  the newest tag at both servers they asked); clients completed ≈ 13 %
  fewer operations (≈ 476 vs ≈ 540 ok) and msgs/op rose from 3.29 to
  3.83.
- **Messages**: a write-back is a write: 2(N − 1) more messages.
- **Availability of reads**: a read that must write back needs **QW**
  servers, not QR. With majority quorums, QW = QR and nothing changes.
  With ROWA it is drastic: QR = 1 < QW = 5, so the skip rule never
  applies (one answer is never 5), **every read writes to all five
  servers**, msgs/op goes from 6.2 to 10.8, and a single crashed or
  unreachable server stops **all reads** as well as all writes (0 reads
  after the crash; the partition run completed 18 operations). ROWA's
  whole point, cheap and highly available reads, is gone: linearizable
  ROWA reads are as expensive as writes.
- **Reads become writes**: a read now changes server state (harmless here,
  since it only re-stores an existing tag, but it means a read can be
  "in progress" at a server, like a write).

**Conclusion.** Write-back buys linearizability for reads that overlap
writes, for one extra round trip on the reads that see disagreement. With
majority quorums the cost is moderate and only paid under concurrency;
for read-optimised configurations (small QR) it removes exactly the
advantage they were chosen for. This is a step of the design evolution
(record §2), with `runs/px-slow-n0` and `runs/px-rowa-crash` as evidence.
