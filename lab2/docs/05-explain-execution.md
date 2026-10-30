# Part 5 – Explain one execution

**Chosen run:** the new–old inversion of Part 3, `runs/p3-inversion`
(`store/lin-kv/20261030T152554.648Z`, `q3.py`, QR = QW = 2, N = 3,
`SLOW_PUT="n0=0.5" --latency 10 --rate 50`; 645 ok / 314 fail / 0 info,
**not linearizable**, key 0; no wall-clock jump in the run).

Why this one: it is the execution the lab builds up to (Part 3 Q4), it is
the anomaly our *final* store still has (q4b.py reads exactly like
q3.py; the lock protects writes and cas, not reads), and it makes the
linearizable / sequentially consistent distinction concrete. The other
candidates are covered elsewhere: lost update `04-compare-and-set.md` §2,
locks under crashes and partitions `04` §4.

## 1. Reconstruction

Sources: `../kit/timeline.py runs/p3-inversion --history --key 0 | grep -v cas`
(merged traces + client operations), `independent/0/linear.svg`,
`messages.svg`, `timeline.html`.

**Who is who.** Clients (Maelstrom process → client id → server): p0 →
c11 → n0, p1 → c6 → n1, p2 → c8 → n2, p3 → c7 → n0, p4 → c9 → n1.
(`timeline.py` shows `pN`, `messages.svg` shows `cN`; the trace field
`client=` links them.)

**`linear.svg`** shows the checker's minimal non-linearizable history: three
reads by processes 0, 1, 2, returning 3, 0, 3, with *"can't read 0 from
register 3"*. The writes are not drawn (the checker only shows the
operations it needs).

**State before:** key 0 = `[16, c9]` value 0 at all three servers (write
by p4, completed at 1.492).

**In order** (times from `timeline.py`, 0 = first client request):

| t (s) | who | event |
|---|---|---|
| 1.535 | p3 → n0 | `write(0, 3)` invoked |
| 1.558 | n0 | phase 1 answers `{n0: [16,c9], n1: [16,c9]}` → tag **[17, c7]** |
| 1.558–1.559 | n0 | `slow_put` to n1 and to n2: both puts held for 0.5 s |
| 1.559 | n0 | stores `[17,c7]` = 3 — **only n0 has 3** |
| 1.562–1.585 | p2 at n2 | read: answers `{n2: [16]0, n0: [17]3}` → **3** |
| 1.624–1.809 | p0 at n0 | five reads, each `{n0: [17]3, n1 or n2: [16]0}` → **3** |
| 1.645–1.670 | p1 at n1 | read: `{n1: [16]0, n0: [17]3}` → **3** |
| 1.714–1.737 | p1 at n1 | read: `{n1: [16]0, n0: [17]3}` → **3** (read A) |
| 1.828–1.852 | p1 at n1 | read: `{n1: [16]0, n2: [16]0}` → **0** (read B) ✗ |
| 1.846–1.869 | p2 at n2 | read: `{n2: [16]0, n0: [17]3}` → 3 |
| 1.886 | p4 → n1 | `write(0, 1)`: phase 1 asks n1, n2 → also number 17: tag **[17, c9]** |
| 1.910–1.920 | n1, n2, n0 | store `[17,c9]` = 1; at n0 it replaces `[17,c7]` ("c9" > "c7") |
| 1.931 | p4 | `write_ok` |
| 1.942 | p0, p1 | read 1 |
| 2.070 | n1, n2 | the slow puts `[17,c7]` = 3 arrive: `stored=false` (older than `[17,c9]`) |
| 2.081 | n0 | 2 acks (n0, n2) → p3 `write_ok` (2.082) |

**Messages involved** (as in `messages.svg`, which uses client ids):
c7 → n0 `write`; n0 → n1, n2 `get` and their `get_ok` (phase 1); n0 → n1,
n2 `put` (sent at 2.06, after the 0.5 s hold) and their `put_ok`; for
each read, the coordinator's `get` to the two other servers and the first
`get_ok` back; for read B, n1 → n0 and n1 → n2 `get`, where **n2's
`get_ok` arrived first** and n0's (which would have said `[17]3`) was
not waited for.

## 2. Space-time diagram

```
          p3 (c7)      n0                  n1                  n2           p1 (c6)
 1.535   w(0,3) ──────►|                   |                   |              |
                       |──get──►           |                   |              |
 1.558                 |◄─[16]0─           |                   |              |
 1.559                 | x=[17,c7]=3       |                   |              |
                       |~~~~put [17,c7] held 0.5 s~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~┐
 1.714                 |                   |◄───────────────────────── read ──|  A
                       |◄────── get ───────|                   |              |
                       |─── [17]3 ────────►| own [16]0         |              |
 1.737                 |                   |──────────────────────────── 3 ──►|  A returns NEW
 1.828                 |                   |◄───────────────────────── read ──|  B
                       |                   |────── get ───────►|              |
                       |                   |◄───── [16]0 ──────|              |
 1.852    ✗ ───────────────────────────────| own [16]0 ─────────────────── 0 ►|  B returns OLD
                       |  (n0's [17]3 answer to B arrives later, ignored)    |
 1.886-1.931           |   w(0,1) by p4 via n1: [17,c9], stored everywhere   |
 2.070                 |~~~~~~~~~~~~~~~~~► stored=false   ► stored=false ◄~~~┘
 2.082   ◄─ write_ok ──| (acks n0, n2)     |                   |              |
```

**Where things went wrong (✗):** at 1.852, n1 answered read B with 0
after only two answers, n1's and n2's, neither of which had received the
held put. The real cause is earlier, at 1.737: read A returned 3, a value
stored at only **one** server (fewer than QW = 2), so nothing guaranteed
that a later read quorum would include a server that had it. {n1, n2}
is a legal read quorum that does not intersect {n0}.

## 3. Classification (restricted to key 0)

We classify the history **of this execution**: the operations below
(initial value 2 before p4's `write(0, 0)`). Over the whole 20 s history
of the run, sequential consistency could in principle "borrow" a write of
0 issued much later (it ignores real time), so the SC verdict is about
this sub-history; the checker (Knossos) only tests linearizability, for
which the argument holds for the whole history too.

| client | operations, in program order (interval) |
|---|---|
| p4 | W0 = `write(0,0)` [1.448, 1.492] · W1 = `write(0,1)` [1.886, 1.931] |
| p3 | W3 = `write(0,3)` [1.535, 2.082] |
| p0 | `read→0` [1.490, 1.513] · `read→3` ×5 [1.624 … 1.809] · `read→1` [1.912, 1.942] |
| p1 | `read→3` [1.645, 1.670] · **A** `read→3` [1.714, 1.737] · **B** `read→0` [1.828, 1.852] · `read→1` [1.918, 1.942] |
| p2 | `read→3` [1.562, 1.585] · `read→3` [1.846, 1.869] |

**Linearizable? No.** Linearizability needs one total order that respects
real time (an operation that ended before another began comes first) and
register semantics. A returned 3, so W3 is before A. B began (1.828) after
A ended (1.737), so B is after A, hence after W3. B returned 0, so a write
of 0 must lie between W3 and B. The only write of 0 that can be placed
before B ends is W0, but W0 ended (1.492) before W3 began (1.535), so W0
must come before W3. Contradiction. (The checker finds it with even fewer
operations: p0's read of 3 ending at 1.809 also precedes B.)

**Sequentially consistent? No.** Sequential consistency keeps register
semantics and each client's **program order**, but drops real time
between different clients. Look at p0 and p1 only:

- p0 read 0, then (program order) 3: the write of 0 it saw (only W0) comes
  before W3;
- p1 read 3 (A), then (program order) 0 (B): W3 comes before a write of 0,
  which can only be W0;

so W0 must be both before and after W3: no order exists. Two clients
observed the same two writes **in opposite orders**, which no sequential
execution allows.

**Would the answers change if the operations were by the same client?**
They already partly are: A and B are both p1's. That is exactly what makes
it non-SC: with A and B in one client's program order, SC also forbids
"new then old". If A and B had been by **different** clients, and nobody
had read in the opposite order, the history (e.g. only p0's `read→3`
ending at 1.809, p1's B `read→0`, W0, W3) would be:

- **not linearizable** (B starts after p0's read ended in real time);
- but **sequentially consistent**: order W0, B, W3, p0's read. Each
  client's own order is respected; only real time between clients is
  violated.

So the inversion by itself, across clients, is a linearizability
violation that SC tolerates; seen by a single client (or by two clients
in opposite orders), it violates SC too.

## 4. Revised claim (from Lab 1) for the store we now have, `q4b.py`

**Assumptions.** N = 3 servers, Qr = Qw = 2, lock quorum Ql = 2;
crash-stop failures (`MS_CRASH`, state is lost with the server: there is no
recovery); asynchronous network that may delay, reorder and drop messages
(partitions), but does not duplicate or corrupt them; each client talks to
one server; servers do not lie.

**If at most f = 1 server fails** by crashing or being cut off from the
other two:

**the service guarantees**

1. *Safety for completed operations:* a read that starts after a
   write/cas has completed returns that value or a newer one; all servers
   converge on the same value for a key once they have received the same
   puts (tags with tie-break); two cas can never both succeed from the same
   value, and a write cannot slip between a cas's read and its put (the
   majority lock).
2. *No guarantee for reads overlapping a write in progress:* such a read
   may return the new value and a later read the old one (this execution).
   So the store is **not linearizable** (it is a regular register for
   reads + atomic cas/write), and not even sequentially consistent.
3. *Availability:* clients of the two live, connected servers get answers
   to reads; writes and cas are answered (ok, or error 11 when the lock
   cannot be taken within 0.8 s), unless the key's lock is held by a server
   that crashed or was cut off, in which case that key's writes and cas are
   blocked forever.

**Evidence.** `q4b.py`: 3 runs under latency 50/rate 50, 3 + 7 with n1
crashing (without and with latency), 3 + 3 with partitions: all 19
linearizable, and no two successful cas read the same tag
(`04-compare-and-set.md` §4). Its read is q3.py's, whose
weakness this execution shows (3/3 slow-n0 runs non-linearizable); the
components' necessity is shown by the failures of the previous steps
(Part 1: divergence; Part 2: version ties; q4a: lost updates).

**Not covered.** Two or more failures (no quorum: everything blocks);
majorities-ring partitions, where no node pair has a working round trip
(no quorum anywhere, `01-wait-for-some.md` §2); servers recovering
without memory; lock holders that crash or are cut off (key blocked for
good, observed in 3 of 7 crash runs and in 1 partition run, `04` §4);
fairness (a coordinator can be starved of the lock); valid runs are
not proofs (20 s, one hot key, few clients).
