# Part 0 – Predict

> The guide asks for these answers **individually, without discussion and
> without AI**. What follows are reference answers written afterwards (by
> the AI assistant, see `ai-log.md`). Each member should keep their own
> original answers and compare: the differences are good material for the
> final discussion. The answers are checked against the runs in
> `03-concurrent-writers.md` §3.

## 1. N = 3: every pair (Qr, Qw); which ones must see a completed write?

There are nine pairs (1 ≤ Qr, Qw ≤ 3):

| Qr \ Qw | 1 | 2 | 3 |
|---|---|---|---|
| 1 | (1,1) no | (1,2) no | (1,3) **yes** |
| 2 | (2,1) no | (2,2) **yes** | (2,3) **yes** |
| 3 | (3,1) **yes** | (3,2) **yes** | (3,3) **yes** |

**A read that starts after a write has completed must see it exactly when
Qr + Qw > N = 3**, i.e. (1,3), (2,2), (2,3), (3,1), (3,2), (3,3).

**Why:** the write completed after Qw servers stored it; the read waits for
Qr answers. If Qr + Qw > N, the two sets cannot be disjoint (pigeonhole):
at least one of the Qr answers comes from a server that stored the write.
If Qr + Qw ≤ N, the read may be answered entirely by servers the write has
not reached yet, e.g. (1,2): the write is stored at n0, n1; a read at n2
asks only itself.

Two caveats that the lab then explores:

- "**sees**" is not "**returns**": among the Qr answers the reader must be
  able to tell the newest one (question 2, Part 2).
- Pairs with Qr + Qw > N but small Qw, like (3,1), make every read wait for
  all servers; and if Qw ≤ N/2, two writes may not see each other, which
  matters for ordering them (versions, Part 2) and for cas (Part 4).

## 2. Answers disagree: which one to return?

With only values, **there is no correct rule**: `{3, 7}` does not say which
was written last. Majority voting does not help either (with Qr = 2 there
is no majority, and the newest value may be in the minority right after a
write). The reader needs **extra information with each value: a version
number** (or timestamp), increasing with every write, and returns the value
with the **highest version**. For this to work:

- versions must grow along real time for completed writes (a new write must
  get a version higher than every completed one: the writer has to *learn*
  the current highest version first, from a quorum);
- two concurrent writes must not get the same version, or ties must be
  broken by the same rule everywhere (e.g. by writer id).

This is exactly the path of Parts 2 and 3.

## 3. N = 5: how many crashed servers can be tolerated?

An operation that waits for Q answers out of N completes as long as at
least Q servers are up, i.e. it tolerates **N − Q** crashes.

| configuration | reads (Qr) | writes (Qw) |
|---|---|---|
| majority, Qr = Qw = 3 | **2** crashes | **2** crashes |
| ROWA, Qr = 1, Qw = 5 | **4** crashes | **0** crashes (one crash blocks every write) |

Majority is the best compromise for both at once (⌊(N − 1)/2⌋ = 2); ROWA is
best for reads and worst for writes.

Note added after Part 2: our writes ask a read quorum *before* writing
(two phases), so a write needs both Qr and Qw servers; for these two
configurations it changes nothing (ROWA's phase 1 is local), but for e.g.
(4, 2) it does (`theory.md` §8).
