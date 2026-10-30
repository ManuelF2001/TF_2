# Part 3 – Concurrent writers, and the limits

Program: `code/q3.py` (explained in `code.md` §5).

## 1. Q1 – two concurrent writes on the same key (from our Part 2 traces)

From `runs/p2-latency`, key 0 (full trace in `02-agree-on-newest.md`
§4.1): three writes, 4 via n0 (client c9), 2 via n1 (c10), 3 via n2 (c11),
ran concurrently. Each one's phase 1 saw version 46 and chose **47**.

**What each server ended up storing, and why:** n0 `[47, 4]`, n1 `[47, 2]`,
n2 `[47, 3]`: each server stored **its own write**, because the coordinator
applies its own put first (locally, before the remote puts arrive), and
then ignored the others, because a put is stored only if its version is
*strictly* higher, and they were equal. "First arrival wins" among equal
versions, and every server saw a different write arrive first.

**A rule that makes all servers agree without extra messages:** make the
version a pair `(number, writer id)` and compare pairs
lexicographically: first the number, then the id. Every put already
carries its version, so the id costs nothing extra. All servers and all
readers apply the same total order, so among `(47, c9)`, `(47, c10)`,
`(47, c11)` they all pick the same one (here `(47, c9)`, since
`"c9" > "c11" > "c10"` as strings), whatever the arrival order.

Which id? We use the **client id** (`decisions.md` D6): a node id is not
enough, because two clients of the same server can write concurrently and
get the same `(47, n0)`.

## 2. Q2 – implementation and runs under latency and load

`code/q3.py`: tags `[number, client]`, one comparison function `newer()`
used by replicas (store or not), readers (newest answer) and writers
(highest number + 1). Prediction: linearizable under latency and load,
since Part 2's only anomaly was the tie.

| program | scenario | linearizable | ok / fail / info | same-number puts resolved by the tie-break, per run |
|---|---|---|---|---|
| q2.py (Part 2) | latency 50, rate 50 | 0/5 | ≈ 530 ok | (79–123 ties, unresolved) |
| q2.py (Part 2) | latency 100, rate 100 | 2/5 | ≈ 335 ok | (65–90 ties, unresolved) |
| **q3.py** | latency 50, rate 50 | **5/5** | 554/267/0 · 530/326/0 · 547/307/0 · 535/329/0 · 526/320/0 | 131 · 110 · 161 · 113 · 129 |
| **q3.py** | latency 100, rate 100 | **5/5** | 343/184/0 · 336/176/0 · 339/205/0 · 331/241/0 · 336/178/0 | 115 (first run) |

"Same-number puts" are puts arriving at a server that holds the same
number with another writer: the comparison of client ids decided
(`stored=true`: the incoming writer id is higher, the server switches;
`stored=false`: it keeps its own). Each of these was a divergence in Part
2; now every server makes the same choice. 10/10 runs linearizable, none
with a clock jump (`tools/clockcheck.py`).

This does not prove q3.py linearizable: §4 shows an execution it allows.

## 3. Q3 – availability with N = 5

`q3.py`, `--node-count 5` (10 clients, two per server), one run per cell
(16 runs). "After 5 s" = operations completed after the crash time, by the
clients of the **live** servers (clients of a crashed server lose
everything, whatever the protocol), from `tools/after.py <run> 5`.

| config | scenario | lin | ok / fail / info | reads after 5 s (live servers) | writes after 5 s (live servers) | msgs/op |
|---|---|---|---|---|---|---|
| majority (3,3) | no faults | yes | 120/80/0 | – | – | 6.56 |
| | n1 crashes | yes | 145/54/6 | **ok** (60) | **ok** (43) | 7.01 |
| | n1, n2 crash | yes | 124/73/11 | **ok** (67) | **ok** (25) | 5.25 |
| | partitions | yes | 123/68/8 | n0 isolated 0–14.4 s: its clients wait, the 4 others work | | 5.97 |
| ROWA (1,5) | no faults | yes | 105/79/0 | – | – | 6.22 |
| | n1 crashes | yes | 98/72/29 | **ok** (62) | **none** (20 info) | 5.32 |
| | n1, n2 crash | yes | 87/67/42 | **ok** (55) | **none** (22 info) | 5.17 |
| | partitions | **NO** | 120/69/5 | 5-node ring 0–2.7 s: no write completes | | 6.55 |
| (2,4) | no faults | yes | 128/76/0 | – | – | 6.67 |
| | n1 crashes | yes | 118/69/7 | **ok** (64) | **ok** (25) | 5.89 |
| | n1, n2 crash | yes | 79/87/40 | **ok** (56) | **none** (19 info) | 4.34 |
| | partitions | yes | 126/71/1 | one node isolated at a time: the 4 others work | | 6.35 |
| (4,2) | no faults | yes | 132/76/0 | – | – | 6.62 |
| | n1 crashes | yes | 122/66/4 | **ok** (67) | **ok** (22) | 5.92 |
| | n1, n2 crash | yes | **36**/127/38 | **none** | **none** | 3.52 |
| | partitions | yes | 117/79/10 | 5-node ring 0–4.5 s | | 6.91 |

**Compared with Part 0, question 3.**

- Majority: predicted 2 crashes for reads and writes; observed: everything
  still works with n1 and n2 down. ✔
- ROWA: predicted reads 4, writes 0; observed: **no write completes after
  one crash** (every write `info`), reads continue with 2 crashes (we did
  not test 4). ✔
- (2,4) and (4,2) show something Part 0 did not consider: our **write has
  two phases**, phase 1 waits for **QR** answers, phase 2 for **QW**. So a
  write tolerates min(N − QR, N − QW) crashes. (2,4): writes tolerate 1
  (phase 2). (4,2): writes also tolerate only 1, because of phase 1; and
  reads tolerate 1. **(4,2) with two crashes completes nothing at all**
  (36 ok, all before the crash), worse than majority in every respect.

**Why msgs/op is almost the same for every configuration** (≈ 6.2–6.7
without faults): a coordinator always **sends to all N − 1 other servers
and they all answer**; Qr and Qw only decide how many answers it *waits
for* before continuing. So a read always costs ≈ 2(N − 1) = 8 messages and
a write (two rounds) ≈ 16, whatever the quorum sizes; cas costs 0 (error
10), and `msgs/op` averages over all operations. It drops with crashes
(crashed servers neither receive nor answer). Quorum sizes change latency
(how long until the Q-th answer) and fault tolerance, not traffic.

**Choice of configuration** (N = 5, our protocol):

- **Read-heavy service: (2,4).** A read waits for the 2 fastest of 5
  answers and survives 3 crashes; writes still survive 1. ROWA (1,5) has
  the cheapest reads (local, no wait), but a single crashed or unreachable
  server stops **every** write, and with reads of a single server,
  partially applied writes are visible at some servers and not others
  (§5: non-linearizable under partitions). We would take ROWA only for
  a service whose writes are rare and can wait.
- **Write-heavy service: majority (3,3).** Writes tolerate 2 crashes, the
  maximum possible for both operations. The intuitive choice (4,2)
  ("small write quorum") does not help with our protocol: the write's
  phase 1 reads from 4 servers, so writes survive only 1 crash, and
  reads become fragile too. (4,2) would pay off only with a write that
  does not need to read versions first, which Part 2 showed to be unsafe.

## 4. Q4 – predict: two reads, new then old

N = 3, majority quorums, our protocol (q3.py). A write w(x, 1) has reached
only the server that received it, n0. Reads do not overlap: B starts after
A has returned.

```
 client W      n0                   n1                   n2         client R1   client R2
    |--w(x,1)-->|                    |                    |              |           |
    |           | phase 1: highest 7 |                    |              |           |
    |           | stores [8,1]       |                    |              |           |
    |           |--put [8,1]--------------------- (slow) ------------------------------- ...
    |           |<---------------------------------------------- read x (A) ---|       |
    |           | own [8,1], n1 [7,0]                                            |       |
    |           |----------------------------------------------- 1 ------------>|       |
    |           |                    |<---------------------------------- read x (B) --|
    |           |                    | own [7,0], n2 [7,0]                              |
    |           |                    |--------------------------------- 0 ------------->|
    |           |                    | <- put [8,1] finally arrives                      |
    |<-write_ok-| (2 acks)           |                    |                              |
```

Read A asks n0 (which has `[8,1]`) and n1 (`[7,0]`) and returns 1, the
highest. Read B, started after A returned, is answered by n1 and n2, which
have not received the put yet, and returns 0. **Not linearizable**: A
returned the new value, so the write must be ordered before A; B comes
after A in real time, so after the write too, and must not return the old
value. The write is still in progress during both reads, so the intersection
argument (which is about *completed* writes) says nothing.

**Is it possible with our protocol? Yes.** Nothing in q3.py prevents it:
a read returns the highest value it *sees*, but does not make sure that
later reads will see it too: the value may be on fewer than Qw servers.
It needs puts that are slow compared to reads, so it is rare with majority
quorums and Maelstrom's latencies. It cannot happen to a *completed*
write. (Removing it is the "Going further" part.)

## 5. Q5 – finding the execution in a run

The kit's `inversion-run.tar.bz2` comes from eLearning and was not
available to us (`decisions.md` D8). We produced the same situation with
the `SLOW_PUT` test hook: `SLOW_PUT="n0=0.5"` delays by 0.5 s every put
that n0 sends to another server (traced as `slow_put`), so any write
coordinated by n0 "reaches only the server that received it" for half a
second. Scenario `slow-n0` (`--latency 10 --rate 50`), 3 runs: **0/3
linearizable** (645/314/0 · 656/313/0 · 616/355/0).

**The execution** (`runs/p3-inversion`, `store/lin-kv/20261030T152554.648Z`,
no clock jump), key 0, found with `tools/anomaly.py … --hide-cas` (equivalent
to `../kit/timeline.py <run> --history --key 0 | grep -v cas`). Before: x
= 0 with tag `[16, c9]` everywhere.

```
 1.535  p3  invoke  write [0 3] -> n0
 1.558  n0  version  tag=[17,"c7"]  seen={n0:[16,c9], n1:[16,c9]}
 1.558  n0  slow_put dest=n1 delay=0.5     1.559 slow_put dest=n2 delay=0.5
 1.559  n0  put [17,c7] value=3 stored=true            (only n0 has 3)
 1.585  p2  ok read [0 3]  at n2: {n2: [16]0, n0: [17]3} -> 3
 ...    p0 reads 3 at n0 (answers include n0 itself), several times
 1.714  p1  invoke read -> n1
 1.736  n1  read {n1: [16]0, n0: [17]3} -> 3
 1.737  p1  ok read [0 3]                              <- read A (client c6 at n1): new value
 1.786  p0  invoke read -> n0;  1.809 p0 ok read [0 3]
 1.828  p1  invoke read -> n1                          (after A, and after p0's read, ended)
 1.851  n1  read {n1: [16]0, n2: [16]0} -> 0           n0's answer arrives later: not waited for
 1.852  p1  ok read [0 0]                              <- read B: old value. NOT LINEARIZABLE
 1.886  p4  invoke write [0 1] -> n1;  phase 1 asks n1, n2: tag [17,"c9"]
 1.920  n0  put [17,c9] value=1 had=[17,c7] stored=true ("c9" > "c7": the tie-break)
 1.931  p4  ok write [0 1]
 2.070  n1, n2  put [17,c7] value=3 (the slow puts) stored=false
 2.081  n0  write_done [17,c7] acks n0, n2;   2.082 p3 ok write [0 3]
```

This is exactly the predicted execution, with even less excuse: read A and
read B are by the **same client** (p1, c6, talking to n1), one after the
other. A asked n1 and n0 and saw the new value at n0; B asked n1 and n2,
neither of which had received the slow put, and returned the old one.
The checker: *"can't read 0 from register 3"*. Note also what happened to
the slow write: it **completed** (`write_ok` at 2.082), but a concurrent
write took the same number 17 and won the tie-break, so the value 3 was
overwritten everywhere before write 3 even finished; that is legal
(write 3 is ordered before write 1, both overlapped), and shows that
"completed" does not mean "readable".

The other two slow-n0 runs fail the same way (`tools/anomaly.py`).

**Did any of our ROWA runs of question 3 show the same pattern? Yes**, the
ROWA partition run (`runs/p3-rowa-partition`,
`store/lin-kv/20261030T152111.376Z`), without any artificial delay. During
a 5-node ring partition (0–2.7 s) no write could reach all 5 servers, so
every write was applied at some servers, never acknowledged (`info`), and
**never repaired** (nothing retries). After the heal the copies stayed
different: n0 and n4 hold `[4, c13]` = 4, n2 holds `[3, c12]` = 0, n3
holds `[2, c16]` = 0. ROWA reads ask one server:

```
 3.321  p0  invoke read -> n0;  3.325 p0 ok read [0 4]   (n0: [4,c13] 4)
 3.456  p2  invoke read -> n2;  3.459 p2 ok read [0 0]   (n2: [3,c12] 0)   <- new, then old
 3.459  p3  invoke read -> n3;  3.463 p3 ok read [0 0]   (n3: [2,c16] 0)
 3.556  p4  invoke read -> n4;  3.559 p4 ok read [0 4]   <- and new again: not linearizable
```

Same pattern: a write that reached only some servers is returned by one
read and missed by a later one. With ROWA it does not even need a slow
link: any write that fails to reach all N servers is a write "in progress
forever". (Part 1 had the same with `q1.py`: `runs/p1-rowa-partition`.)
Majority runs did not show it without the slow link: it needs a put to
be slower than two complete reads.
