# Part 4 – Compare-and-set

Programs: `code/q4a.py` (cas without lock) and `code/q4b.py` (cas and
write under a quorum lock), explained in `code.md` §6–7.

## 1. Q1 – cas on the quorum store

`cas(k, from, to)` at the coordinator, exactly as the guide says:

1. **read from a quorum**: `get` to all, wait for Qr answers, take the
   value with the highest tag (traced as `cas_read`, with every answer,
   `expected` = from, `to`);
2. **compare**: key missing → error 20; value ≠ from → error 22;
3. otherwise **write as a write would**: tag `[highest number + 1, client]`,
   `put` to all, `cas_ok` after Qw acknowledgements.

## 2. Q2 – predict, run, and find two cas that both succeeded

**Prediction.** Not linearizable under `--latency 50 --rate 50`: two cas on
the same key from the same value, at different servers, both read `from`
in step 1 (each before the other's put arrives), both decide to write, and
both reply `cas_ok`. Only one of them should have succeeded: after the
first, the value is `to₁`, not `from`. Clients complete operations as
before (all live servers available).

**Runs** (`q4a.py`, `--latency 50 --rate 50`): **0/3 linearizable**
(553/165/0 · 556/158/0 · 542/173/0; cas_ok 35 · 42 · 48). Now that cas can
succeed, Maelstrom's overall verdict is meaningful again, and `summary.py`'s
`lin=` is the same verdict.

**Two cas on the same key that both succeeded** (`runs/p4-lost-update`,
`store/lin-kv/20261030T152732.164Z`, key 0; no clock jump). Here the
checker's minimal history does contain them (*"can't CAS 1 from 2 to 1"*);
the traces show why:

```
10.173  n2  version [57, c11] value=2      (p5's write; stored at n2, at n0 and n1 at 10.224)
10.189  p3  invoke cas [0 [2 1]] -> n0
10.227  p4  invoke cas [0 [2 1]] -> n1
10.275  p5  ok write [0 2]                  x = [57, c11] = 2 everywhere
10.327  n0  cas_read client=c7  read=[[57,c11], 2] from=2 to=1  answers={n0: [57]2, n1: [57]2}
10.328  n0  put [58, c7] value=1 stored=true                     (n0's own copy)
10.379  n1  cas_read client=c10 read=[[57,c11], 2] from=2 to=1  answers={n1: [57]2, n2: [57]2}
10.380  n1  put [58, c10] value=1 stored=true                    (n1's own copy)
10.380  n1  put [58, c7]  value=1 had=[58,c10] stored=true       <- c7's put arrives 1 ms too late
10.429  n0  cas_done tag=[58,c7]  acks n0, n2;   10.430 p3 ok cas [0 [2 1]]
10.481  n1  cas_done tag=[58,c10] acks n1, n2;   10.482 p4 ok cas [0 [2 1]]   <- second success
```

Both coordinators read 2 from a quorum (n1's read at 10.379 used n1 and n2,
which had not yet received c7's put), both compared successfully, both
wrote 1 with tag number 58, and both clients got `cas_ok`. The final value
(1) happens to be the same, but **the history is impossible for a
register**: after the first `cas(2 → 1)` the value is 1, so the second must
fail with "expected 2, found 1". (Over the three runs, our traces show 5
such pairs: two successful cas that read the same tag, e.g. in the same run
c10 `cas(2 → 1)` and c7 `cas(2 → 2)` from `[39, c11]`, a lost update with
different values.)

**Why this is impossible with a single server.** A single server executes
one request at a time: the read, the comparison and the write of a cas
happen in one handler, with no other operation in between (Lab 1's
`kv.py`, or n0 in strategy D). The second cas then reads `to₁` and fails
with error 22. With quorums, the read and the write of a cas are two
separate rounds of messages, and other operations, in particular another
cas, can run between them at other servers. Quorum intersection guarantees
that the second cas's read *would* see the first cas's write if that write
had *completed* before the read started; it says nothing about two
operations whose reads both happen before either write.

## 3. Q3 – designing a lock (as a group, without a computer)

Before a cas, the coordinator locks the key at a **lock quorum** of
servers and unlocks it when done.

**How large must the lock quorum be?** Two operations must never hold
the lock at the same time, so any two lock quorums must share a server
(which grants the lock to only one of them): **Ql + Ql > N**, i.e.
**Ql > N/2, a majority** (2 of 3, 3 of 5). *Relation to Part 0:* it is the
intersection condition of Part 0 Q1 (Qr + Qw > N) applied to two *writers*
(Qw + Qw > N) instead of a reader and a writer, and it is the majority
quorum of Part 0 Q3: it tolerates ⌊(N − 1)/2⌋ crashed servers (1 of 3,
2 of 5); a smaller lock quorum would tolerate more crashes but could be
held by two coordinators at once.

**What does a server do when asked to lock a key that is already
locked?** It **refuses** (`lock_busy`, with the holder), immediately. It
does not queue the request: a queued requester would keep the locks it
already got at other servers while waiting, and two requesters that each
got part of a quorum would wait for each other forever (deadlock).

**What does the requester do then?** As soon as a lock quorum has become
impossible (more than N − Ql refusals), or 0.25 s pass without one (some
servers do not answer), it **releases every lock it got** and **retries
after a random delay** (0–0.25 s), so that two competing requesters are
unlikely to collide again. After 0.8 s it gives up and answers the client
**error 11** ("temporarily unavailable", the operation surely did not
happen): true, since nothing is written before the lock is held, and
sooner than the client's 1 s timeout.

**Do writes also need the lock? Yes.** Otherwise a write can fall between
the read and the put of a cas:

```
cas(x, 1, 2) at n0:  locks x; reads x = 1 (tag [5, c1]) ......... puts [6, c3] value 2
write(x, 3) at n1:                 (no lock) phase 1 sees [5, c1], puts [6, c4] value 3, write_ok
```

Both puts carry number 6; whichever wins the tie-break, something is
wrong: if the cas's value wins, the completed write(x, 3) is lost, and a
read after both returns 2, which requires the cas to come after the write,
when x was 3, not 1 (the cas should have failed); if the write's value
wins, the cas succeeded but its effect never appears. With the write also
taking the lock, it waits until the cas has released, then reads the
cas's tag in its phase 1 and goes after it. **Reads** need no lock: they
change nothing (they are still subject to Part 3's in-progress
inversion, which the lock does not address).

## 4. Q4 – runs with the lock

`code/q4b.py`. As the guide says: `--latency 50 --rate 50`, then the same
plus `MS_CRASH="n1@5"`, then plus `--nemesis partition`. (We first ran
the crash and the partitions *without* latency, scenario names
`crash-n1` / `partition`; with ~0 ms latency a lock is held for about a
millisecond and no fault ever hit one, so we re-ran them on top of the
latency, as the guide intends: `latency-crash-n1`, `latency-partition`.)

| scenario | lin | ok / fail / info | cas_ok | locks taken | lock attempts failed (busy / timeout) | gave up: error 11 |
|---|---|---|---|---|---|---|
| q4a, no lock, latency | **0/3** | 553/165/0 · 556/158/0 · 542/173/0 | 35 · 42 · 48 | – | – | – |
| q4b latency 50, rate 50 | **3/3** | 428/149/2 · 475/102/1 · 481/93/0 | 8 · 11 · 8 | 69 · 71 · 68 | ≈ 200 / 0 | 41 · 43 · 43 |
| q4b + n1 crashes at 5 s | **7/7** | 337/108/25 · 362/88/21 · 367/85/18 · 365/96/19 · 347/100/19 · 345/94/16 · 362/79/17 | 2 · 6 · 6 · 7 · 0 · 3 · 2 | 44 · 49 · 43 · 48 · **24 · 19 · 19** | ≈ 100 / ≈ 47 | 27–46 |
| q4b + partitions | **3/3** | 353/129/8 · 342/113/10 · 392/125/3 | 4 · 7 · 4 | 46 · 43 · 44 | 90/93 · 79/99 · 192/31 | 50 · 49 · 53 |
| q4b, crash, no latency | 3/3 | 123/62/8 · 149/60/4 · 125/53/7 | 15 · 15 · 9 | ≈ 95 | ≈ 0 | 0 |
| q4b, partitions, no latency | 3/3 | 121/62/2 · 148/62/0 · 116/72/2 | 13 · 16 · 8 | 92 · 104 · 62 | 4/21 · 2/8 · 0/41 | 8 · 3 · 14 |

**Safety restored**: every run with the lock is linearizable, and in no
q4b run did two successful cas read the same tag (the search that found 5
pairs in q4a finds 0).

**The price**: the lock serialises all writes and cas on a key, and each
one holds it for three round trips (lock, phase 1, put) ≈ 300 ms at 50 ms
latency: ≈ 70 locked operations in 20 s, i.e. ≈ 3.5 per second for the
hot key. The other attempts are refused (`busy`, ≈ 200 per run), retried,
and ≈ 40 per run give up with error 11 (a definite failure, so they count
as `fail`, not `info`). cas_ok fell from 35–48 to 8–11. Reads are not
affected (they take no lock). We also saw **starvation**: refusal without
a queue is not fair: in `store/lin-kv/20261030T154031.997Z` (latency +
crash), from 4.9 s to 5.5 s the coordinator n2 took the lock three times
in a row (`n2:21`, `n2:22`, `n2:23`, each next attempt starting right after its own
release) while every attempt of n0 (`n0:25`, `n0:26`, `n0:27`) was
refused.

**What happens to the other clients when the server that holds a lock
crashes?** In the first three crash runs, n1 happened not to hold a lock
quorum at the crash instant (it only held its *own* server's lock, which
disappears with it; e.g. `n1:23` was refused by n0 and n2 just before the
crash). We ran four more (7 in all); in **three** of them key 0 was then
blocked (`locks taken` 24 · 19 · 19 instead of ≈ 45):

```
runs/p4-crash-holder (store/lin-kv/20261030T154828.000Z), key 0:
4.757  n1  lock owner=n1:23          (n1's own server)
4.807  n0  lock owner=n1:23
4.859  n1  locked owner=n1:23 client=c9 op=write granted=[n1, n0]   <- n1 holds a majority
4.956  n1  crash                                                     <- while holding it
       from here on, no lock on key 0 is ever granted again: n0 is held by a dead owner,
       n1 is dead, so no two servers can grant; every write and cas on key 0 by the
       clients of n0 and n2 fails with error 11 (lock_failed: busy / timeout), for
       ≈ 14 s, until the workload moves to key 1 at 18.8 s (2 locks there)
```

In the two other runs (`20261030T154722.633Z`, `20261030T154755.447Z`) the
holder was a **lock request still in flight**: n1 sent `lock{n1:21}` (resp.
`n1:26`) and crashed; the request reached n0 (resp. n2) after the crash
(4.995 > 4.954; 4.988 > 4.945) and was granted to an owner that no longer
existed. Same result: a live server holds the key for a dead
coordinator, and with n1 down the other live server alone is not a
majority. So the answer: **the other clients can still read, but every
write and cas on that key fails (error 11, or timeouts) forever**; and,
because a dead holder looks exactly like a slow one, no server may simply
take the lock away (Part 6 Q2). All 7 runs stay linearizable: the lock
fails safe, by refusing, never by allowing two holders.

The same situation, a holder that can no longer release, occurs with a
partition, which for the others is indistinguishable from a crash:

**A blocked key** (`runs/p4-blocked-key`,
`store/lin-kv/20261030T154242.759Z`, latency + partitions, no clock jump):

```
14.196  n2  lock_busy owner=n2:63 holder=n1:58         (n2's own server is still held)
14.247  n0  lock owner=n2:63      14.247 n1 lock owner=n2:63   <- n2:63 now holds a majority
14.253  nemesis start-partition {n2 isolated from n0, n1}   (until the end of the run)
                                   the lock_ok replies to n2 are dropped
14.269… n0, n1: lock_busy for n1:59, n0:65, n1:60, … holder=n2:63    (forever)
14.447  n2  lock_failed owner=n2:63 reason=timeout granted=[] refused=[n2]
        n2  released: unlock sent to all                   <- dropped by the partition
after 14.3 s: n0, n1 clients: reads ok 51 + 49; writes/cas ok 0 (17 error 11)
              n2 clients: nothing (cut off)
```

n2 never learned that it had the lock (the grants were lost), gave up,
and its `unlock` messages were lost too. n0 and n1, the **majority** side,
still hold the lock on key 0 for an operation that no longer exists: for
the rest of the run, every write and cas on key 0 by their clients fails
with error 11, while reads continue. Nothing in our design ever releases
it, not even after the partition heals (lost messages are not resent):
the key is blocked forever. A crashed holder does exactly the same. The
service stays linearizable; it loses availability for that key, and
this happens with only **one** faulty server, which the quorums alone
would have tolerated.

**When two servers each lock part of the quorum.** After n1 crashed, a
lock quorum needs *both* live servers. `store/lin-kv/20261030T153958.994Z`:

```
4.902  n2  lock owner=n0:22            (n0's attempt holds n2's lock)
4.937  n2  lock_busy owner=n2:22 holder=n0:22
4.963  n1  crash
4.987  n0  lock owner=n2:22            (n2's attempt holds n0's lock)
5.187  n2  lock_failed owner=n2:22 reason=timeout granted=[n0] refused=[n2]
5.451  n0  lock_failed owner=n0:23 reason=timeout granted=[n2] refused=[n0]
5.636  n2  lock_failed owner=n2:23 … granted=[n0] refused=[n2]   (and again)
```

Each attempt holds one of the two live servers and is refused by the
other; n1 never answers, so neither attempt can reach 2 grants nor 2
refusals, and both wait for the 0.25 s timer, release everything and back
off randomly. Without the release this would be a **deadlock**; with
release but without randomness, a **livelock**; with both, it is lost
time (≈ 45 timeouts per crash run) until one attempt gets both servers
(still 43–49 locks per run). A server that crashed while *granting*
(n1 holding someone's lock) just disappears from the quorum: harmless,
because the other two still decide.
