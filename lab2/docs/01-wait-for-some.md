# Part 1 – Wait for some

Program: `code/q1.py` (explained in `code.md` §3). Runs: `results/results.tsv`
(lines `q1.py`), cited runs copied to `runs/p1-*`.

## 1. The design, and our answers to questions 1–2

**Design (from the guide).** Each server stores, for each key, only its
value. `write`: the receiving server sends the value to all servers
(itself included) and replies after **Qw** acknowledgements. `read`: it
asks all servers and replies after **Qr** answers. `cas`: error 10.

**Q1 – what the reader returns when the Qr answers disagree.** A value
beats "key does not exist" (keys are never deleted); among values, the
**first answer received**, which is always the coordinator's **own copy**
(it is computed locally, before any remote answer can be processed).
Alternatives and why we chose this: `decisions.md` D2. With values only,
no rule can find the newest value, so we expect every rule to fail
somewhere.

**Q2 – predictions** (written before running; *why* in one sentence each):

| configuration | scenario | linearizable? | clients complete operations? |
|---|---|---|---|
| ROWA (1,3) | no faults | **probably yes**: a completed write is on every server; the only risk is two concurrent writes applied in opposite orders, and at ~0 ms latency and 10 req/s their window is ~1 ms | yes, all |
| ROWA (1,3) | latency 50, rate 50 | **no**: concurrent writes on the same key now overlap for ~100 ms, get applied in different orders at different servers, and the copies diverge for good | yes (writes take ≈ 100 ms) |
| ROWA (1,3) | n1 crashes | **probably yes**: the two live servers still receive every put at ~0 ms | reads yes; **no write completes** after 5 s (needs all 3); n1's clients nothing |
| ROWA (1,3) | partitions | **no**: writes applied on one side only (never acknowledged) are read there and not on the other side: different servers return different values | reads yes; writes **none** while any server is cut off |
| majority (2,2) | no faults | **probably yes**, same reason as ROWA (tiny windows) | yes |
| majority (2,2) | latency 50, rate 50 | **no**: the reader returns its own copy even when the other answer is newer, and concurrent writes leave the copies divergent | yes |
| majority (2,2) | n1 crashes | **probably yes** (tiny windows) | yes, except n1's clients |
| majority (2,2) | partitions | **no**: a server cut off during writes keeps an old value, and after the partition heals it returns its own (old) copy first | only on the majority side |
| non-intersecting (1,2) | no faults | **probably yes** (tiny windows) | yes |
| non-intersecting (1,2) | latency 50, rate 50 | **no**: a read at the server not in the write quorum returns the old value after the write completed, and concurrent writes diverge | yes |
| non-intersecting (1,2) | n1 crashes | **probably yes** (the 2 live servers both get every completed write) | yes, except n1's clients |
| non-intersecting (1,2) | partitions | **no**: the isolated server keeps answering reads from its stale copy | reads everywhere; writes on the side with 2 servers |

## 2. Results (Q4): 36 runs, 3 per combination

`lin` = runs the checker found linearizable (`./summary.py`'s `lin=`, i.e.
ignoring the "cas never succeeds" failure, `decisions.md` D1). Counts are
ok/fail/info per run; **every `fail` in the no-fault and latency runs is a
`cas` answered with error 10** or a read of a key not yet written: no read
timed out.

| configuration | scenario | predicted | observed: lin | ok / fail / info | why it differs |
|---|---|---|---|---|---|
| ROWA (1,3) | no faults | yes; all | **3/3** | 125/81/0 · 112/78/0 · 114/76/0 | – |
| majority (2,2) | no faults | yes; all | **3/3** | 118/73/0 · 126/77/0 · 120/64/0 | – |
| non-int. (1,2) | no faults | yes; all | **3/3** | 126/85/0 · 141/68/0 · 116/78/0 | – |
| ROWA (1,3) | latency+load | **no**; all | **0/3** | 703/282/0 · 661/302/0 · 706/286/0 | – |
| majority (2,2) | latency+load | **no**; all | **0/3** | 578/377/0 · 548/368/0 · 539/391/0 | – |
| non-int. (1,2) | latency+load | **no**; all | **0/3** | 662/320/0 · 639/316/0 · 683/281/0 | not by stale reads alone (§3.3) |
| ROWA (1,3) | n1 crashes | yes; no write after 5 s | **3/3** | 111/61/32 · 108/61/26 · 96/77/23 | – |
| majority (2,2) | n1 crashes | yes; all but n1's | **3/3** | 118/72/7 · 116/77/5 · 119/68/8 | – |
| non-int. (1,2) | n1 crashes | yes; all but n1's | **3/3** | 124/69/7 · 111/68/9 · 124/66/7 | – |
| ROWA (1,3) | partitions | **no**; writes blocked | **1/3** | 138/77/3 · 114/57/4 · 109/59/14 | the valid run: one short partition (2.3 s) |
| majority (2,2) | partitions | **no**; minority blocked | **3/3** | 13/139/34 · 99/95/7 · 112/76/2 | **wrong prediction**, §3.4 |
| non-int. (1,2) | partitions | **no** | **0/3** | 126/80/8 · 126/76/3 · 121/71/8 | – |

Availability, measured with `tools/after.py <run> 5` (operations completed
after the crash at 5 s), first crash run of each configuration:

| configuration, n1 crashed at 5 s | reads ok after 5 s | writes ok after 5 s |
|---|---|---|
| ROWA (1,3) | n0: 60, n2: 16, n1: 0 | **0** (21 `info`: n0 11, n1 1, n2 9) |
| majority (2,2) | n0: 50, n2: 10, n1: 0 (8 timed out) | n0: 17, n2: 3, n1: 0 (2 `info`) |
| non-intersecting (1,2) | n0: 50, n2: 15, n1: 0 (9 timed out) | n0: 16, n2: 3, n1: 0 |

(Runs `runs/p1-rowa-crash`, `store/lin-kv/20261030T145508.615Z`,
`store/lin-kv/20261030T145642.189Z`. Clients of n1 lose everything whatever
the protocol: each client always talks to the same server.)

Things we learnt from the runs:

- **Latency makes everything visible.** With ~0 ms latency at 10 req/s,
  the windows in which two operations can interleave badly are around a
  millisecond, and 9 + 9 runs without latency stayed linearizable. With 50 ms
  latency at 50 req/s all 9 runs failed. A valid run says nothing about
  correctness, only that the window was not hit.
- **ROWA reads are local and instant**, majority reads wait one round trip
  (≈ 100 ms): with the same request rate, ROWA clients complete more
  operations (703 vs 578 ok).
- **Partitions in Maelstrom come in three shapes** (`--nemesis partition`):
  one node isolated from the other two (`{"n0" #{"n1" "n2"}, …}`), an
  "empty" partition that isolates nobody (`{"n0" #{}, …}`), and a
  **majorities ring** (`{"n2" #{"n0"}, "n0" #{"n1"}, "n1" #{"n2"}}`): every
  node drops messages *from* one other node. With 3 nodes, every pair then
  has one direction cut, so **no request/reply round trip completes
  anywhere**: no quorum of 2 can form. Run `runs/p1-majority-ring`: a
  ring for 17.8 s, only 13 operations ok in the whole run.

## 3. Explaining one non-linearizable run (Q5)

The configuration to explain depends on the group number (majority for
groups 1, 4, 7, 10; ROWA for 2, 5, 8; non-intersecting for 3, 6, 9). We do
not know ours at first (`decisions.md` D13), so here is one for each.
**We are group 7: majority, §3.2.**

How we found them: `tools/anomaly.py <run> --hide-cas` prints the last
operation the checker could linearize and the ones it then could not, plus
the merged timeline of the key just before (the same as
`../kit/timeline.py <run> --history --key 0 | grep -v cas`, cut to the
window). The orders below were also checked against the node logs
(`worklog.md` §5: the wall clock can jump; these runs have no jump in the
window).

### 3.1 ROWA (1,3): concurrent writes applied in opposite orders

Run `runs/p1-rowa-latency` (`store/lin-kv/20261030T144816.502Z`), key 0:

```
 1.405  p3  invoke  write [0 1] -> n0
 1.434  n0  put     value=1 coordinator=n0         n0 = 1
 1.438  p4  invoke  write [0 2] -> n1
 1.484  n1  put     value=2 coordinator=n1         n1 = 2   (its own write first)
 1.484  n1  put     value=1 coordinator=n0         n1 = 1   (n0's arrives after)
 1.486  n2  put     value=1 coordinator=n0         n2 = 1
 1.534  n2  put     value=2 coordinator=n1         n2 = 2
 1.536  n0  put     value=2 coordinator=n1         n0 = 2
 1.537  p3  ok      write [0 1]                    (acks n0, n1, n2)
 1.558  p0  ok      read [0 2]   at n0
 1.586  p1  ok      read [0 1]   at n1             <- not linearizable
 1.588  p4  ok      write [0 2]                    (acks n1, n2, n0)
 1.682  p0  ok      read [0 2]   at n0
 1.733  p1  ok      read [0 1]   at n1             ... and so on, until the next write
```

Both writes reached all three servers, but n1 applied them in the order
2, 1 and n0, n2 in the order 1, 2. From 1.588 on, both writes are complete
and **the copies disagree permanently**: n0 = n2 = 2, n1 = 1. p0's read of 2
(ended 1.558) requires write 2 to come after write 1; p1's read of 1, which
started after p0's read ended, requires the opposite. The checker:
*"can't read 1 from register 2"*.

**To blame: what the servers store.** A server keeps the *last value to
arrive*, and arrival order differs between servers. The reader is not the
problem: with Qr = 1 it reads the only copy it asks; even a reader that
asked everyone would find {2, 1, 2} and have no basis to pick.

**Compared with strategy B of Lab 1** (receiver executes, replies after all
acks, reads served by the receiver): ROWA *is* strategy B. Same strength
(a completed write is on every copy, reads are local) and same weaknesses:
concurrent writes at different receivers are applied in different orders,
and one crashed server blocks every write (here: 0 writes after the crash,
`runs/p1-rowa-crash`). In ROWA, as in B, waiting for *all* does not order
the writes.

### 3.2 Majority (2,2): divergent copies, and the reader prefers its own

> **This is group 7's answer to Q5** (majority is assigned to groups 1, 4,
> 7, 10; `decisions.md` D13). §3.1 and §3.3 are kept for the class
> comparison.

Run `runs/p1-majority-latency` (`store/lin-kv/20261030T144955.465Z`), key 0:

```
 6.003  p3  invoke  write [0 2] -> n0
 6.005  n0  put     value=2 (own)                  n0 = 2
 6.022  p5  invoke  write [0 0] -> n2
 6.055  n1  put     value=2 from n0                n1 = 2
 6.055  n2  put     value=0 (own)                  n2 = 0
 6.055  n2  put     value=2 from n0                n2 = 2
 6.107  n0  put     value=0 from n2                n0 = 0
 6.107  n1  put     value=0 from n2                n1 = 0
 6.107  p3  ok      write [0 2]   (acks n0, n1)
 6.158  p5  ok      write [0 0]   (acks n2, n0)    both writes complete; n0 = n1 = 0, n2 = 2
 6.199  p1  invoke  read -> n1;  6.310 n1 answers {n1: 0, n2: 2} -> returns 0 (own)
 6.228  p2  invoke  read -> n2;  6.361 n2 answers {n2: 2, n0: 0} -> returns 2 (own)   <- not linearizable
 6.422  p0  read at n0: {n0: 0, n2: 2} -> 0 ...
```

After 6.158 no write is in progress, yet reads return 0 at n0 and n1 and 2
at n2, until the next write (6.393). The checker: *"can't read 2 from
register 0"*.

**To blame: both choices, the storage first.** (1) What the servers
store: the two concurrent writes were applied in opposite orders, so the
copies diverged (n0 = n1 = 0, n2 = 2) although both writes completed at a
majority; there is no "newest" value to find. (2) What the reader
returns: both n1 and n2 *saw both values* ({0, 2}) and each returned its
own. Intersection did its job (each read did receive the other value);
the reader had no information to choose. Fixing the reader alone is
impossible (values carry no order); fixing it needs information produced
by the writes and stored with the values: **versions**, Part 2.

### 3.3 Non-intersecting (1,2): no change to the storage can fix it

Under latency, the (1,2) anomalies were again concurrent writes applied
in opposite orders (e.g. `store/lin-kv/20261030T145229.686Z`: writes of 3
via n0 and 1 via n1 leave n0 = 1, n1 = 3; p1 reads 3 at n1, then p0 reads
1 at n0). Surprisingly, **in none of the 36 Part 1 runs did a read miss a
completed write while no other write was in progress** (a "pure" stale
read; checked over the checker's history order). Why: every put is sent to
both other servers at the same moment; the write completes when the
*first* acknowledgement returns, a full round trip later, by which time
the put to the third server has usually arrived too. Non-intersection is a
risk that latency alone rarely exposes. A partition exposes it.

Run `runs/p1-nonint-partition` (`store/lin-kv/20261030T150125.015Z`),
majorities-ring partition from 0.006 s to 6.927 s (n0 drops messages from
n1, n1 from n2, n2 from n0):

```
 1.659  p3  invoke write [0 1] -> n0:  n0 = 1, put reaches n1 (n1 = 1); n1's ack is dropped
 1.682  p4  invoke write [0 3] -> n1:  n1 = 3, put reaches n2 (n2 = 3); n2's ack is dropped
 1.849  p5  invoke write [0 4] -> n2:  n2 = 4, put reaches n0 (n0 = 4); n0's ack is dropped
 1.970  p0  ok read [0 4] at n0
 2.030  p1  ok read [0 3] at n1        (started after p0's read ended)
 2.061  p2  ok read [0 4] at n2        <- not linearizable: 4, then 3, then 4 again
```

None of the three writes ever completes (`info`, each has only its own
ack), so each may be placed anywhere after its invocation; but reads of
4, then 3, then 4 again, one after the other, need write 4 both before and
after write 3. **Would a change to what the servers store fix it? No.**
Suppose servers kept versions and agreed on an order: write 4 is newer
than write 3, and n2 and n0 have it. n1 never received write 4, and a read
at n1 with Qr = 1 asks **only n1**: it returns 3 whatever n1 stores,
because the servers that know about 4 are not asked. A read that does not
intersect the servers holding the newest value cannot return it; only
**Qr + Qw > N** fixes this. (Strictly, these writes never completed, so a
pure intersection argument covers only completed writes; with QW = 2 a
completed write would be at 2 servers and a Qr = 1 read at the third
would miss it in exactly the same way.)

### 3.4 Why majority survived partitions (our wrong prediction)

We predicted that a server isolated while writes happened would, after the
heal, return its own old copy (own answer first). The mechanism is real:
in `runs/p1-majority-partition` (`store/lin-kv/20261030T150022.454Z`),
n0 is isolated 0–6.435 s, and at the heal n0 still holds 0 while n1, n2
hold 4 (n1's read at 6.530 shows `{"n1": 4, "n0": 0}`). But no read was
served by n0 before the next write overwrote its copy (6.902 s): n0's
clients were still waiting for operations that would time out, and the
next request n0 received was a write. The window existed and was not hit
(in 3 runs). The prediction stands as a possibility, not an observation.

## 4. What Part 1 shows

- **Intersection is necessary but not sufficient.** (2,2) and (1,3)
  intersect and still fail: a read *receives* the newer value but cannot
  *recognise* it (§3.2), and servers apply writes in arrival order, so
  completed writes leave copies in different states (§3.1).
- **Non-intersecting quorums fail even with perfect storage** (§3.3).
- **Availability** is exactly counting: ROWA writes stop with one crashed
  server; majority keeps everything but the crashed server's clients;
  a ring partition can leave no quorum anywhere.

From now on: majority quorums, Qr = Qw = 2, N = 3.
