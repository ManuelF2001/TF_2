# Part 2 – Agree on the newest

Program: `code/q2.py` (alternative for the checkpoint: `code/q2local.py`),
explained in `code.md` §4. Majority quorums from now on: Qr = Qw = 2, N = 3.

## 1. Q1 – what extra information, who produces it, how

**What.** A **version number** stored with each value: `store[key] =
[version, value]`, a missing key has version 0. A higher version means a
newer write. Servers keep the pair with the highest version they have
received; readers return the value with the highest version among their
Qr answers.

**Who produces it.** The **coordinator of the write** (the server that
received it from the client), *before* sending the value.

**How.** It must be higher than the version of every write that has
completed, otherwise the new value would be considered older and ignored.
The coordinator does not know the latest version by itself (it may not
have been in the last write quorum), so it **asks**: phase 1 sends `get` to
all servers and waits for Qr answers; since Qr + Qw > N, at least one of
them was in the write quorum of the last completed write, so
`highest seen + 1` is higher than every completed write's version. Phase 2
sends `put{version, value}` to all and waits for Qw acknowledgements, as
in Part 1. A server stores a put only if its version is *strictly* higher
than its own.

Alternatives (`decisions.md` D5): the coordinator's own version + 1
(`q2local.py`, one round trip less, but a coordinator outside the last
write quorum produces a version that is too low); physical time (needs
synchronised clocks).

**Space-time diagram: two writes followed by a read** (key x, initially
`[0, –]` everywhere; each arrow is a message; `get`/`put` sent to all, only
the answers that count are drawn):

```
 client A       n0                    n1                    n2          client B
    |            |                     |                     |              |
    |--w(x,5)--->|                     |                     |              |
    |            |--get x------------->|                     |              |   phase 1:
    |            |  own: [0,-]         |                     |              |   answers n0 [0,-],
    |            |<------------[0,-]---|                     |              |   n1 [0,-]: v = 0+1 = 1
    |            |--put x [1,5]------->| stores [1,5]        |              |   phase 2
    |            |  own: stores [1,5]  |                     |              |
    |            |<----------put_ok----|                     |              |   2 acks: done
    |<-write_ok--|--put x [1,5]--------------------------->(slow, arrives later)
    |            |                     |                     |<--w(x,7)-----|
    |            |                     |<--------get x-------|  own: [0,-]  |   phase 1:
    |            |                     |-------[1,5]-------->|              |   answers n2 [0,-],
    |            |                     |                     |              |   n1 [1,5]: v = 1+1 = 2
    |            |                     |<---put x [2,7]------|  stores [2,7]|
    |            |                     | stores [2,7]        |              |
    |            |                     |-------put_ok------->|---write_ok-->|   2 acks: done
    |            |                     |                     |  [1,5] arrives from n0: 1 < 2, ignored
    |--read x--->|                     |                     |              |
    |            |--get x------------->|                     |              |
    |            |  own: [1,5]         |                     |              |
    |            |<-----------[2,7]----|                     |              |   highest version: 2
    |<--read 7---|                     |                     |              |
```

Without versions (Part 1) the read would have returned n0's own 5; and
n2, receiving [1,5] late, would have overwritten 7 with 5. With versions,
the late put is recognised as older and ignored, and the reader picks 7.

## 2. Q2 – the implementation, with traces

`code/q2.py`. The information is **created** in `write` → `versions_known`
(trace `version`, with the versions seen in phase 1 and the version
chosen) and **compared** in two places: at each replica in `serve` (trace
`put` with `had` = what the replica had and `stored` = true/false) and at
the reader in `newest` (trace `read` with every `[version, value]` answer
and the one returned).

## 3. Q3 – runs

**Prediction** (before running): linearizable without faults and with one
crash (versions fix the Part 1 anomalies: late puts can no longer
overwrite newer values, readers pick the newest); under latency and load,
**still not linearizable**, because two concurrent writes can compute the
same version (both phase 1s finish before either put arrives), and nothing
breaks that tie consistently.

| scenario | runs | linearizable | ok / fail / info | version ties per run |
|---|---|---|---|---|
| no faults | 1 | yes | 117/71/0 | 0 |
| n1 crashes at 5 s | 1 | yes | 118/65/10 | 0 |
| partitions | 1 | yes | 24/133/28 (a 15 s majorities ring: almost nothing completes) | 0 |
| `--latency 50 --rate 50` | 5 | **0/5** | 532/315/0 · 535/304/0 · 526/332/0 · 541/306/0 · 527/295/0 | 79 · 106 · 94 · 120 · 123 |
| `--latency 100 --rate 100` | 5 | **2/5** | 329/202/0 · 334/201/0 · 333/216/0 · 336/207/0 · 336/188/0 | 81 · 65 · 74 · 90 · 79 |
| more partitions (added later) | 2 | yes ×2 | 116/79/1 · 34/117/31 | 0 |

*Version ties* = puts that a server refused because it already had the
**same version with a different value** (`put … stored=false` with
`version == had[0]`), counted in the node logs. They occur only under
load, and in every such run, including the three the checker found
linearizable: a tie is harmless until a read **observes** the divergence
(different servers answering different values) before the next write,
with a higher version, overwrites all copies. Whether that happens in a
given run is a matter of chance, which is why 2 of the 5 runs at
`--latency 100` passed. When the checker fails a run, the anomaly is a
tie: §4.1. All Part 2 runs are free of wall-clock jumps.

The latency runs complete fewer operations than Part 1's (≈ 530 vs
≈ 560 ok): a write now takes two round trips (phase 1 + phase 2), and
`msgs/op` rose from ≈ 2.4 to ≈ 3.3.

## 4. Explaining the non-linearizable runs

### 4.1 `q2.py`: three writes, one version

Run `runs/p2-latency` (`store/lin-kv/20261030T150432.624Z`, no clock jump),
key 0. Three clients write at almost the same time, one at each server:

```
 8.368  n0  version  value=4 client=c9   version=47 seen={n0: 46, n1: 46}
 8.384  n1  version  value=2 client=c10  version=47 seen={n1: 46, n0: 46}
 8.419  n2  version  value=3 client=c11  version=47 seen={n2: 46, n1: 46}
 8.369  n0  put  version=47 value=4 had=[46,0] stored=true   (own)
 8.384  n1  put  version=47 value=2 had=[46,0] stored=true   (own)
 8.421  n2  put  version=47 value=3 had=[46,0] stored=true   (own)
 8.420  n1  put  version=47 value=4 had=[47,2] stored=false  <- equal version: ignored
 8.421  n2  put  version=47 value=4 had=[47,3] stored=false
 8.435  n0  put  version=47 value=2 had=[47,4] stored=false
 8.435  n2  put  version=47 value=2 had=[47,3] stored=false
 8.471  n1  put  version=47 value=3 had=[47,2] stored=false
 8.472  n0  put  version=47 value=3 had=[47,4] stored=false
 8.471  p3  ok write [0 4]   8.487  p4  ok write [0 2]   8.523  p5  ok write [0 3]
        -> all three complete; n0 = [47,4], n1 = [47,2], n2 = [47,3]
 8.575  p0  ok read [0 4]  at n0: {n0: [47,4], n1: [47,2]} -> first of equals: 4
 8.587  p1  ok read [0 2]  at n1: {n1: [47,2], n0: [47,4]} -> 2
 8.639  p2  ok read [0 3]  at n2: {n2: [47,3], n0: [47,4]} -> 3       <- not linearizable
```

All three phase 1s ran before any of the three puts arrived anywhere, so all
three saw version 46 and chose 47. Each server stored the first version-47
put it received (its own), and ignored the other two (`stored=false`,
equal version). After 8.523 no write is in progress and the three servers
hold three different values with the same version: reads return 4, 2 or 3
depending on the server. Versions fixed "which is newer" for writes that
are *ordered*; for **concurrent** writes they can be equal, and then the
servers and readers each break the tie their own way. That is Part 3.

### 4.2 Checkpoint: `q2local.py` (version from the coordinator's own copy)

The guide's checkpoint compares groups that made different choices in Q1.
We ran the most common alternative ourselves: the coordinator takes
`own version + 1`, without phase 1.

| program | `--latency 50 --rate 50` | ok / fail / info | ties per run |
|---|---|---|---|
| q2.py (asks a read quorum) | **0/5** linearizable | ≈ 530 ok | 79–123 |
| q2local.py (own copy) | **1/3** linearizable | 582/364/0 · 548/384/0 · 561/382/0 | 112 · 79 · 99 |

- **Same failure under load.** The anomalies of q2local are ties too:
  `store/lin-kv/20261030T151027.829Z`, key 0: write 0 via n0 and write 4
  via n2 both take version 73 from their own copies (72); n0 keeps 0,
  n1 and n2 keep 4; reads at n0 return 0 while reads at n1, n2 return 4.
- **Faster writes**: one round trip instead of two (more ok, ≈ 2.4
  msgs/op instead of ≈ 3.3).
- **A failure that latency alone hides.** q2local's version is right only
  if the coordinator's own copy has the latest completed write. Under
  latency it almost always has (every put is sent to every server, and,
  as in Part 1 §3.3, arrives about as fast as the acknowledgements). But
  a server that was **cut off** while others wrote keeps an old version;
  its next write after the heal gets a version *lower* than writes that
  already completed, every other server ignores it (`stored=false`), it
  is still acknowledged (`put_ok`), and the client gets `write_ok` for a
  write that no later read will ever return: a **lost write**. q2.py
  cannot do this: its phase 1 asks a quorum, which intersects the write
  quorum of every completed write. Partition runs of both: §5.
- The 1 valid q2local run in 3 is not evidence that it is better: it had
  112 ties, as many as the failing runs; no read happened to observe one.

## 5. Partition runs of both versions (added after the first runs)

To look for q2local's lost write, we added 2 partition runs of q2.py and
3 of q2local.py (`bash run_all.sh part2b`): **all linearizable**
(q2local: 134/64/0 · 112/90/7 · 125/70/1). In the run where it could
happen (`store/lin-kv/20261030T154523.537Z`: n2 isolated 0–7.855 s),
n2 came back with version 1 while the others were at 12; but the first
thing that reached n2 after the heal was a put from n0 (8.089 s, version
13), which brought it up to date before any client of n2 wrote (they were
still waiting for operations that timed out). No put was ever refused for
being *older* than the stored version. Like the stale own copy of Part 1
(`01` §3.4), the window exists but was not hit: **predicted by the
argument, not observed**. A targeted test would isolate one server, write
elsewhere, heal, and make that server's client write first.

**Conclusion for the checkpoint:** "who produces the version" matters for
*completed* writes (asking a quorum is necessary when servers can miss
writes); neither choice handles *concurrent* writes, which need Part 3's
tie-break.
