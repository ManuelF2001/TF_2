# Decisions and doubts

Every point where the guide, the kit or the situation left a choice open,
what we chose, and why. Each one can be revisited by the group: the
document that depends on it is named.

## Organisation

**D0. Where Lab 2 lives.** The Lab 2 material (`kit.tar.bz2`, `lab2.pdf`)
was placed in `~/TF_2`, while Lab 1 lives in `~/TF`. We kept Lab 2 in
`~/TF_2` and gave it the same layout as Lab 1 (`kit/`, `archives/`,
`env.sh`, `labN/{code,docs,runs,results,record}`), so that both labs read
the same way. To avoid a second 75 MB copy of Maelstrom, `TF_2/maelstrom`
is a **symlink** to `~/TF/maelstrom` (same version, 0.2.4), and `env.sh`
reuses Lab 1's user-space Java 17 and gnuplot. *If TF_2 is moved to
another machine:* extract `maelstrom.tar.bz2` (from `~/TF/archives`) in
place of the symlink.

**D1. The kit.** The guide says "extract it over your Lab 1 kit (your own
files are kept)". `TF_2/kit` is exactly that: a copy of `~/TF/kit` (without
its `store/`) with the new `kit.tar.bz2` extracted over it. What changed
(checked with `cmp`): `summary.py` is new; `AGENTS.md`, `README.md` and
`record.tex` were updated (AGENTS.md now also forbids, unless asked,
"versions or timestamps, tie-breaking, read repair or write-back";
record.tex allows three pages instead of two); `ms.py`, `run.sh`,
`timeline.py`, `echo*.py` are identical. The kit is otherwise unmodified.

**D7. One program per design step instead of a single evolving `q.py`.**
The guide calls the program `q.py` and changes it part after part. We kept
**each step as its own file** (`q1.py` → `q2.py` → `q3.py` → `q4a.py` →
`q4b.py`, plus `qx.py`), because the record asks for "the evolution of your
design, one line per part, citing the run that showed it": every cited run
must be reproducible with the exact code that produced it. **The final
store is `q4b.py`.** Each file's header says what changed from the
previous one; `diff code/q3.py code/q4a.py` shows a step.

## Part 1

**D2. What the reader returns when the QR answers disagree (Part 1, Q1).**
Options considered: the first answer; the coordinator's own copy; a
majority vote; any non-missing value. We chose: *a value beats "key does
not exist"* (keys are never deleted, so "missing" is certainly older than
any value), *then the first answer received*. Since the coordinator's own
answer is always first (D4), this means "my own copy if I have the key".
Why: it is the only rule that is right in at least one case, and it adds
no mechanism the design does not have (a vote among 2 answers is
meaningless, and with only values no rule can find the newest).
Consequence: `01-wait-for-some.md`.

**D3. No timeouts, no retries in Parts 1–3.** The design says "replies
after Qw/Qr answers". When fewer servers answer, our coordinator simply
never replies; the client times out after 1 s and Maelstrom records `info`
(write) or `fail` (read). We did *not* add an error reply after a timeout:
for a write, error 11 would even be wrong (some servers may have stored
it); error 13 would only say what a timeout already says.

**D4. "All servers (itself included)".** The coordinator does not send a
message to itself: it applies the request to its own copy directly
(`serve(...)` in `quorum()`), counting it as one answer. Equivalent to a
message with zero delay that partitions cannot drop, which is what a local
copy is. Side effect, relevant to D2: the own answer is always the first.

**D12. Repetitions.** The guide asks for each of the 12 Part 1
combinations once; anomalies are probabilistic, so we ran each **three
times** (36 runs) and report all of them.

**D13. Which configuration to explain (Part 1, Q5).** It depends on the
group number, which we do not know (the Lab 1 record also says "Group G").
We explain **one non-linearizable run for each of the three
configurations** (majority, ROWA, non-intersecting), so the group can keep
the one assigned to it.
*Update, 11 November:* we are **group 7 → majority**; our Q5 answer is
`01-wait-for-some.md` §3.2 (`runs/p1-majority-latency`). §3.1 (ROWA) and
§3.3 (non-intersecting) stay as extra material for Part 6.

## Part 2

**D5. Who produces the version, and how (Part 2, Q1).** We chose: the
**coordinator of the write**, in a first phase, **asks all servers for their
version and waits for QR answers**, then uses highest + 1 (ABD's write).
Because QR + QW > N, the highest version seen is at least that of every
completed write, so versions increase along real time for completed writes.
The cost is a second round trip per write. The alternative (the
coordinator uses its own copy's version + 1, one round trip) is also
implemented as `q2local.py` and run, because the guide's checkpoint
compares groups that made different choices: it fails differently and
more often (`02-agree-on-newest.md` §4). Physical timestamps were
rejected (they need synchronised clocks).

**D5b. Equal versions in Part 2.** A replica stores a put only if its
version is *strictly* higher; a reader returns the first of equal
versions. Nothing else, on purpose: breaking ties is Part 3.

## Part 3

**D6. Tie-breaking id: the client, not the coordinator.** The guide's
question ("what rule would make all servers agree, without any extra
messages?") is usually answered with "compare (version, node id)". But in
Maelstrom two clients of the **same** server can write concurrently (2 per
server with `--concurrency 2n`): both writes would get the same
`(v + 1, n0)` and the tie would remain. We use the **client id** of the
write (`msg.src`, unique per client; a client has one operation at a time,
and a client that times out is replaced by a new one with a new id). Same
rule, no extra message.

**D11. The configuration "of our choice" for availability (Part 3, Q3).**
The record asks which configuration we would choose for a read-heavy and
for a write-heavy service, so we ran **two** extra configurations, (2,4)
and (4,2), besides majority (3,3) and ROWA (1,5): 16 runs with N = 5.

**D8. `inversion-run.tar.bz2` was not available (until 11 November).** It is downloaded from
eLearning, which we do not have access to. To still find the execution of
Part 3, Q4 in a real run, we added a **test hook** to `q3.py` (and `qx.py`),
off by default: `SLOW_PUT="n0=0.5"` delays every put that n0 sends to
another server by 0.5 s and traces it as `slow_put`, like the
`slow_put` events the guide mentions. This is fault injection, like
`MS_CRASH` in `ms.py`, not a protocol mechanism. We also looked for the
same pattern in our ROWA runs, as the guide asks.
*Update, 11 November:* the group downloaded the real run; it is extracted
in `kit/inversion-run` and compared in `03-concurrent-writers.md` §5.1. The
hook turned out to be faithful: the teachers' `p3_slow.py` holds n0's puts
to n1 and n2 for 0.5 s, exactly what `SLOW_PUT="n0=0.5"` does, and the run
shows the same anomaly. We keep our run as the Part 5 execution (the guide
prefers the group's own run) and use the kit's for the SC contrast
(`05-explain-execution.md` §5).


## Part 4

**D9. The lock design (Part 4, Q3).**

- *Lock quorum*: a **majority** (QL = N // 2 + 1, configurable with `QL=`),
  because two lock quorums must intersect: 2·QL > N, the write–write
  intersection condition. It is the size of Part 0's majority quorum.
- *Locked key*: the server **refuses** (`lock_busy`) instead of queueing
  the request. A queue would make the requester wait while holding other
  servers' locks: deadlock when two requesters each hold part of a quorum.
- *The requester*, when a lock quorum becomes impossible (too many
  refusals) or does not arrive within 0.25 s (crashed or unreachable
  servers), **releases everything and retries after a random delay**
  (0–0.25 s); after 0.8 s it answers **error 11** to the client. Error 11
  ("surely not done") is truthful because nothing is written before the
  lock is held; 0.8 s is below the client's 1 s timeout.
- *Writes take the lock too*: otherwise a write can complete between a
  cas's read and its put and be overwritten by the cas, an anomaly as bad
  as the lost update (`04-compare-and-set.md` §3).
- *Reads take no lock*: they modify nothing.
- *Unlock* is sent to **all** servers, fire and forget; a grant that
  arrives after the attempt ended is unlocked at once (covers an `unlock`
  overtaking its `lock`).
- *Not added*: leases, lock timeouts at the servers, takeover. A lock
  whose holder crashed is never released: we want to *observe* that
  (Part 4, Q4) and discuss the fix (Part 6, Q2).

**D9b. Cas reads use QR, writes keep two phases under the lock.** Under
the lock, writes to a key are serialised, so the tag's tie-break is no
longer needed; we kept it anyway (it costs nothing and reads still need
tags).

**D17. Crash and partition runs of the lock on top of latency.** We
first ran `q4b.py` with a crash and with partitions *without* latency
(scenarios `crash-n1`, `partition`), reading the guide's "run with
`--latency 50 --rate 50`, then add `MS_CRASH`, then try partitions" too
literally. With ~0 ms latency a lock is held for ~1 ms and no fault ever
hit one. Re-reading, "add" means *on top of* the latency, so we added the
scenarios `latency-crash-n1` and `latency-partition` (`run_all.sh
part4b`) and kept the first runs as well. Since the crash hits a lock
holder only by chance, we ran 7 crash runs; 3 of them blocked a key.

**D18. Extra runs added after reading the first results** (all in
`run_all.sh`, so they are reproducible): `part2b` (partition runs of
`q2.py`/`q2local.py`, to look for q2local's stale version) and `part4b`
(D17). Both were run after the main batch; `results.tsv` is in execution
order.

**D19. How we read timelines.** The WSL wall clock jumps (`worklog.md`
§5): every execution explained in the documents was checked with
`tools/clockcheck.py` (none of the cited windows has a jump) and, where
the order mattered, against the node logs. The failing operations are
located with `tools/anomaly.py` by their history index, not by time.

## Going further

**D10. Write-back built on `q3.py`, not on `q4b.py`.** The optional part
asks to "change the read" to prevent the inversion of Part 3, Q4. We
applied the change to the Part 3 protocol (`qx.py` = `q3.py` + write-back)
so that the *only* difference with the runs it is compared to is the read.
We added a standard optimisation and say so: no write-back when at least
QW of the QR answers already have the newest tag (then the value is
already at a write quorum).

## Deliverable

**D14. The record.** `record/record.tex` follows the kit template (three
pages max) and the guide's list (claim, design evolution, Part 1 table,
Part 3 table with read-/write-heavy choice, Part 5 diagram, limitations,
AI log, contributions). Group number, names and contributions are left
as placeholders: we do not know them. *(11 November: group number set
to 7; names and contributions still to be filled in by the group.)* It is compiled with Tectonic
(`cd record && tectonic record.tex`).

**D15. AI use.** The lab was implemented with an AI assistant (Claude
Code); what it was asked, what it produced and what had to be corrected is
in `ai-log.md` and in §5 of the record.

**D16. Part 6 (class table).** Other groups' results are not available
here: `06-compare.md` gives our rows for the class table, what we expect
other groups to see differently and why, and the answer to the lock
takeover question.

## Re-review, 11 November

A second pass over every decision, against the final code (`q4b.py`), the
runs and the kit's `inversion-run`, done by the assistant (session 3,
`ai-log.md`). The group's own verdicts go in `ai-log.md` §5.

| decision | verdict | reason |
|---|---|---|
| D2 reader rule (Part 1) | keep | with values only no rule is correct; this one adds no mechanism and its failure (`01` §3.2) is what motivates versions |
| D3 no timeouts in Parts 1–3 | keep | error 11 after a timeout would be false for a write that reached some servers |
| D4 own copy without a message | keep | equivalent to a zero-delay message; the only side effect (own answer first) is documented |
| D5 version from a read quorum | keep | QR + QW > N makes versions grow with real time for completed writes; `q2local` (local version) failed more (`02` §4); the teachers' `p3_slow.py` does the same |
| D6 tie-break by client id | keep | the kit's run breaks ties by server id, which is safe there only because each server has one writing client; with `--concurrency 2n` two clients of one server can write concurrently |
| D7 one file per step | keep | every cited run is reproducible with the exact code |
| D8 `SLOW_PUT` hook | keep, confirmed | same held puts and same anomaly as the kit's run |
| D9 lock: refuse + random backoff, error 11 after 0.8 s | keep | queueing deadlocks; error 11 is truthful (nothing written before the lock); 0.8 s < client timeout. Known costs: starvation, a crashed holder blocks the key (record §4) |
| D9b cas read with QR, two-phase write under the lock | keep | the lock serialises writers, the read quorum still gives the latest tag |
| D10 write-back on `q3.py` | keep | the comparison isolates the read change |
| D11 (2,4) and (4,2) as extra configurations | keep | needed for the read-/write-heavy choice |
| D17–D19 | keep | |

**Changed in the documents (not in the code):**

- The claim said "no two cas succeed from the same value". Too strong: two
  cas from the same value may both succeed legitimately if a write puts the
  value back in between. What the lock guarantees, and what the runs
  checked ("no two successful cas read the same tag", `04` §4), is **no
  two cas succeed after reading the same version**. Fixed in the record §1
  and `05` §4.
- Claim (ii) was ambiguous about whose writes are answered; it now says
  clients of the live majority for reads, writes and cas alike.
- `05` §4 said the store is "not even sequentially consistent"; now: it
  does *not guarantee* SC (two clients can see two writes in opposite
  orders, §3), since whether a whole history is SC also depends on
  repeated values (`05` §5).

No decision needed a code change, so no run was repeated.
