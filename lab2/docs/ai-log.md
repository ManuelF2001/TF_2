# AI log

The lab requires logging "the prompts that mattered and what you had to
correct or reject, including any mechanism the assistant proposed before
you needed it". Be honest here: the final discussion is individual, and the
examiner can ask any member to explain any line.

## Session 1 — Claude Code (Claude Opus 5.5), 2026-10-30

**Prompt:** *"Complete Lab2, while doing that organize every folder and
content, explain everything you did in mds and explain everything that the
software also does in mds and doubts you have you follow what you think
its best and also explain what you did in md"*

This asks the assistant to do the whole lab, including the parts the guide
says must be done **without AI and without a computer** (Part 0
individually; Part 1 Q1–Q2, Part 2 Q1, Part 3 Q4, Part 4 Q3 "as a group,
without a computer"). Under `kit/AGENTS.md` this is an **"answer directly"**
request, which must be noted here (it is also in §5 of the record).
The group must still:

- write its own Part 0 answers and compare them with `00-predict.md`;
- check every decision in `decisions.md` (D2–D11) and change the code if
  the group decides differently (each program's header lists its design);
- be able to explain every line of the final program `code/q4b.py` and of
  the steps before it (`code.md`).

**What the assistant did** (details in `worklog.md`):

1. Organised `~/TF_2` like Lab 1 (`kit/` = Lab 1 kit + Lab 2 kit extracted
   over it; `archives/`; `env.sh`; Maelstrom shared with Lab 1 by symlink).
2. Restated the design of each part in the program header *before* writing
   it, and implemented **only** that design, one file per step (`q1.py` …
   `q4b.py`, `qx.py`), as the guide's "implement exactly the design of the
   current part" and `AGENTS.md` require.
3. Ran every scenario (118 Maelstrom runs, `results/results.tsv`),
   wrote predictions *before* the corresponding runs, and wrote the
   documents from the actual results, with the traces that support each
   explanation.
4. Wrote `tools/` (`anomaly.py`: the operations the checker could not
   linearize and the timeline around them; `after.py`, `clockcheck.py`,
   `table.py`) and `cite_runs.sh`; filled in and compiled the record.

**Suggested 3-line summary** (as `AGENTS.md` asks): *Asked to complete
Lab 2 directly. Implemented one program per part's design, ran 118
Maelstrom runs, wrote all documents and the record from the results.
Group to check: Part 0, the decisions in `decisions.md`, the claim.*

## Mechanisms proposed before they were needed (rejected for the part at hand)

The guide asks to note mechanisms the assistant proposed before the group
decided on them. Since the assistant was both "group" and "assistant" here,
these are the mechanisms it *considered* and deliberately left out of a
part, adding them only in the part that asks for them:

| mechanism | considered in | left out because | added in |
|---|---|---|---|
| version numbers | Part 1 (reader rule) | Part 1 design: "only its value" | Part 2 (`q2.py`) |
| tie-break by writer id | Part 2 | Part 2 Q1 asks only for the version | Part 3 (`q3.py`) |
| read write-back / read repair | Part 3 (inversion) | not in Parts 1–4 | Going further (`qx.py`) |
| timeouts + error reply in Parts 1–3 | Part 1 | not in the design; error 11 would be wrong for writes | never (D3) |
| lease / lock takeover | Part 4 | Part 4 asks to *observe* a crashed holder | discussed only (Part 6 Q2) |
| queueing lock requests at the server | Part 4 | deadlock risk (D9) | rejected |

## Corrections / things learnt from the runs (not from the assistant's predictions)

- `kit/AGENTS.md` was updated for Lab 2: it now explicitly lists versions,
  tie-breaking and write-back among the mechanisms an assistant must not
  add unasked. The assistant's first idea for Part 1 Q1 ("return the value
  with the highest version") had to be rejected for that reason: Part 1
  has no versions.
- **Wrong prediction:** majority quorums under partitions in Part 1 were
  predicted non-linearizable (stale own copy after a heal); 3/3 runs were
  linearizable: the window exists but no read hit it (`01` §3.4).
- **Wrong expectation:** non-intersecting quorums were expected to show
  stale reads under latency; a search of all 36 Part 1 runs found **none**
  without a concurrent write (puts reach the third server as fast as the
  acks come back). The non-intersection example had to come from a
  partition run (`01` §3.3).
- **Wrong explanation, retracted:** the assistant first explained
  q2local's one valid run by "a narrower tie window"; counting showed 112
  ties in that run, as many as in failing runs (`02` §4.2).
- **Misreading of the guide, corrected:** Part 4 Q4's crash and
  partitions are meant *on top of* `--latency 50 --rate 50`; the first
  runs without latency never caught a lock holder (`decisions.md` D17).
- **Tooling:** the WSL wall clock jumps backwards during runs, which makes
  merged timelines wrong around the jump; found while explaining an
  anomaly, handled with `tools/clockcheck.py` and index-based
  `tools/anomaly.py` (`worklog.md` §5). Editing a shell script while bash
  executes it is unsafe (`worklog.md` §7).
- The kit's `inversion-run.tar.bz2` (eLearning) was not available; the
  assistant reproduced the execution with a `SLOW_PUT` test hook instead
  (`decisions.md` D8). The group should compare with the real run.

**Accepted / changed / rejected by the group:** *(fill in)*

## Optional (Part 3): ask an AI whether the Part 2 store is linearizable

*(The guide suggests asking an assistant before Part 3. Do it in a
**fresh** session that has not seen our runs, paste its answer here, and
compare with `03-concurrent-writers.md`.)*

- Assistant's answer: …
- What we found: Part 2 is **not** linearizable: equal versions from
  concurrent writes leave replicas with different values (`02` §3); and
  even with the tie-break of Part 3, a read can return a write still in
  progress and a later read the older value (`03` §4).
- Agreement / disagreement: …
