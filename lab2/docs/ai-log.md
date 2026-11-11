# AI log

What the guide asks for (deliverable item 5): the prompts that mattered,
what we had to correct or reject, and any mechanism the assistant proposed
before we needed it. Assistant used: **Claude Code (Claude Opus 5.5)**, in
two sessions.

## 1. How the assistant was used

| session | what we asked | what it produced |
|---|---|---|
| 30 Oct | implement and run the lab part by part, organise the folders, document every step and every doubt | `code/q1.py` … `q4b.py`, `qx.py`; 118 Maelstrom runs; `docs/`; `tools/`; first version of the record |
| 11 Nov | adapt everything to group 7, analyse the kit's `inversion-run`, improve this log | `03` §5.1, `05` §5, `tools/sccheck.py`; record updated |
| 11 Nov | re-review every design decision against the final code and the runs | all decisions kept; two claim statements made precise (`decisions.md`, last section) |

Prompts, verbatim:

- 30 Oct: *"Complete Lab2, while doing that organize every folder and
  content, explain everything you did in mds and explain everything that
  the software also does in mds and doubts you have you follow what you
  think its best and also explain what you did in md"*
- 11 Nov: *"acabei de meter o inversion_run kit e nós somos o grupo 7,
  altera o que for preciso ser alterado e faz a parte 0 zero também e uma
  boa ai log, sendo ao teu critério o que consideres bom"*. The Part 0
  answers in `00-predict.md` are Manuel's own; the assistant only added
  the comparison with the runs.

Every design choice the assistant made is listed in `decisions.md`
(D0–D19), so that we could review and overrule it (§5).

## 2. Prompts and requests that mattered

| request | why it mattered | what came out |
|---|---|---|
| "implement exactly the design of the current part" (guide) | stopped mechanisms from leaking into earlier parts | §3 |
| "explain everything the software does" | every program and script is documented, so each of us can explain each line | `code.md` |
| "doubts: follow what you think is best" | choices had to be written down, not made silently | `decisions.md` |
| Part 4 Q2: find the two cas that both succeeded | the checker's minimal history did not show them; the traces did | 5 lost-update pairs in q4a, 0 in q4b |
| "we are group 7" | Part 1 Q5 configuration | majority, `01` §3.2 |
| the kit's `inversion-run` | first check of our slow-link reproduction against the teachers' run | same anomaly; SC vs linearizable contrast |

## 3. Mechanisms proposed before we needed them

| mechanism | came up in | why it was left out | where it went |
|---|---|---|---|
| version numbers | Part 1, reader rule | Part 1 stores only values | Part 2 (`q2.py`) |
| tie-break by writer id | Part 2 | Part 2 Q1 asks only for a version | Part 3 (`q3.py`) |
| read write-back / read repair | Part 3, inversion | not in Parts 1–4 | Going further (`qx.py`) |
| timeouts + error replies in Parts 1–3 | Part 1 | not in the design; error 11 would be wrong for writes | rejected (D3) |
| lease / fencing for lock takeover | Part 4 | Part 4 asks to *observe* a crashed holder | Part 6 Q2, discussion only |
| queueing lock requests at the server | Part 4 | deadlock risk | rejected (D9) |

## 4. What we had to correct

**The assistant's predictions and explanations that the runs proved wrong:**

- Majority quorums under partitions (Part 1) were predicted
  non-linearizable; 3/3 runs were linearizable. The stale-copy window
  exists but no read hit it (`01` §3.4).
- Non-intersecting quorums were expected to show stale reads under
  latency; none of the 36 Part 1 runs had one. The example had to come
  from a partition run (`01` §3.3).
- q2local's one valid run was first explained by "fewer version ties";
  counting found 112 ties, as many as in failing runs. Explanation
  withdrawn (`02` §4.2).
- Part 4 Q4: the crash and partition runs were first done without
  latency and never caught a lock holder; the guide means them *on top
  of* `--latency 50 --rate 50` (D17).
- `inversion-run`: the first count said the pattern appears once;
  checking all 21 slow writes found a second inversion, which Knossos
  does not report because it stops at the first failure (`03` §5.1).
- The first version of `tools/sccheck.py` parsed no operation and so
  called an empty history consistent; caught because it printed 0
  operations per process.

**Tooling problems found along the way:**

- The WSL wall clock jumps backwards during runs, so merged timelines can
  show events in the wrong order. Handled with `tools/clockcheck.py` and
  by locating operations by history index (`worklog.md` §5).
- Editing a shell script while bash is running it is unsafe; the edit was
  reverted and redone after the run (`worklog.md` §7).

**Rejected:** the first answer to Part 1 Q1 ("return the value with the
highest version"), because Part 1 has no versions.

**Confirmed:** the `SLOW_PUT` test hook (D8), written before the kit's run
was available, holds n0's puts exactly like the teachers' `p3_slow.py`.

## 5. Review of the decisions

The assistant's second pass (11 Nov, details in `decisions.md`, last
section) is in the middle column; the group's verdict goes in the last.

| item | where | assistant's re-review | group |
|---|---|---|-------|
| reader rule of Part 1 (own copy first) | D2 | keep | ok    |
| version from a read quorum, not the local copy | D5 | keep (the kit's protocol does the same) | ok    |
| tie-break by client id (the kit uses server id) | D6, `03` §5.1 | keep (server id fails with 2 writers per server) | ok    |
| lock: refuse + random backoff, error 11 after 0.8 s | D9 | keep; costs documented | ok    |
| Part 5 execution: ours (`p3-inversion`) | `05` | keep | ok    |
| revised claim | `05` §4, record §1 | **changed**: cas "same version", not "same value"; (ii) clarified | ok    |

What the re-review corrected: the claim said "no two cas succeed from the
same value", but two cas from the same value can both succeed if a write
puts the value back in between; the lock guarantees, and the runs
checked, that no two cas succeed after reading the same *version*.

## 6. Optional (Part 3): ask a fresh AI whether the Part 2 store is linearizable

Ask in a **new** session that has not seen our runs:

> *"A key-value store on 3 servers. Each server keeps, per key, a value and
> an integer version. write(k, v): the receiving server asks all servers
> for their version, waits for 2 answers, takes max + 1, sends (v, version)
> to all, and replies after 2 acks; a server stores a put only if its
> version is strictly higher. read(k): asks all servers, waits for 2
> answers, returns the value with the highest version. Is this store
> linearizable? Why or why not?"*

- Its answer: …
- What we found: **not linearizable**. Concurrent writes get equal
  versions and each server keeps its own (`02` §3, `runs/p2-latency`);
  even with the Part 3 tie-break, a read can return a write still in
  progress and a later read the older one (`03` §4–5, kit
  `inversion-run`).
- Agreement / disagreement: …
