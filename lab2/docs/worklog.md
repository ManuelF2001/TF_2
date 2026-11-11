# Work log – what was done, in order

A chronological account of everything done for Lab 2 (by the AI assistant,
at the group's request: see `ai-log.md`), so that the group can retrace or
redo any step. Times are 2026-10-30, local.

## 1. Inventory (14:30)

`~/TF_2` contained only `kit.tar.bz2` (the Lab 2 kit) and `lab2.pdf` (the
guide). The guide says to extract the kit *over the Lab 1 kit*; Lab 1 was
found in `~/TF` (git repository, with `kit/`, `maelstrom/`, `env.sh`,
`lab1/` and a user-space Java 17 + gnuplot in `~/.local/opt`). The Lab 1
documents (`~/TF/lab1/README.md`, `docs/`) were read to follow the same
conventions: one program per design, `scenarios.sh` + `run_all.sh`,
`results/results.tsv`, `docs/` with one file per part, a filled-in
`record/record.tex`, honest AI log.

## 2. Organisation (14:37)

```
mkdir archives lab2; mv kit.tar.bz2 archives/; mv lab2.pdf lab2/
rsync -a --exclude store --exclude __pycache__ ~/TF/kit/ kit/   # Lab 1 kit
tar -xjf archives/kit.tar.bz2                                   # Lab 2 kit over it
ln -s /home/kernel/TF/maelstrom maelstrom
```

`cmp` against the Lab 1 kit: `summary.py` new; `AGENTS.md`, `README.md`,
`record.tex` changed; everything else identical (`decisions.md` D1).
Wrote `env.sh` (Java, gnuplot, `MAELSTROM`) and checked the installation:
`./run.sh echo echo.py` → *Everything looks good!* Wrote the top-level
`README.md`.

## 3. Part 1 program and scripts (14:40)

Design restated in the header of `code/q1.py`, then implemented;
`code/ms.py` copied from the kit (it must sit next to the programs).
`scenarios.sh` (one scenario, N repetitions, one line per run in
`results/results.tsv`) and `run_all.sh` (every run of the documents).
Smoke test: `bash scenarios.sh code/q1.py 2 2 nofaults` → linearizable,
traces as expected. Then `bash run_all.sh part1` (36 runs, ≈ 20 min) in the
background.

## 4. The other programs, while Part 1 ran (14:45–14:55)

`q2.py`, `q2local.py`, `q3.py`, `q4a.py`, `q4b.py`, `qx.py`, each with its
design in the header (`decisions.md` D5–D10); all checked for syntax.
`q4b.py` (the most intricate) and the `SLOW_PUT` hook of `q3.py` were
smoke-tested in a scratch directory (`/tmp/lab2-smoke`), so as not to
mix with the cited runs: q4b linearizable with cas succeeding; q3 with
`SLOW_PUT=n0=0.5` non-linearizable on key 0, as intended.

Documents written meanwhile (they do not depend on results): `theory.md`,
`00-predict.md`, `code.md`, `decisions.md`, `ai-log.md`, top-level
`README.md`.

## 5. Tools, and a problem with the clock (14:55–15:05)

To explain anomalies, `tools/anomaly.py` reads which operations the checker
could not linearize (`results.edn`) and prints the merged timeline of the
key just before them. While testing it on the first non-intersecting
latency run, the timeline showed impossible orders (a read at n0 returning
2 *after* n0 had stored 3). Reading `node-logs/n0.log` in file order showed
the cause: **the wall clock of the WSL virtual machine jumped back by
0.234 s** during the run (it is periodically re-synchronised with
Windows). Trace events and `jepsen.log` use the wall clock, so
`timeline.py` sorts events wrongly around a jump; the checker is not
affected (it uses the order of the history). Measures taken:

- `tools/clockcheck.py` reports the jumps of a run (most runs after
  14:51 have one, of 0.1–0.7 s);
- `tools/anomaly.py` finds the failing operations by their *index* in the
  history, not by time, and warns when a jump falls in the window it prints;
- every execution explained in the documents was checked against the
  per-node log order (which is always right), and preferably chosen in
  runs without a jump.

Also written: `tools/table.py` (results.tsv → markdown table) and
`tools/after.py` (ok/fail/info per server and operation, before and after a
crash time).

## 6. Part 1 results and analysis (15:00–15:10)

36 runs done (15:02). For each configuration, the anomaly found by the
checker was reconstructed (`01-wait-for-some.md` §3). A search over the
history order of all 36 runs (scratch script, not kept) found **no pure
stale read**: every anomaly involved concurrent writes; this changed the
answer for the non-intersecting configuration, which we then explained
with a partition run. One prediction was wrong (majority under
partitions: 3/3 linearizable); `01` §3.4 explains why the window was not
hit. The Part 1 rows of the class table went into `06-compare.md`.

## 7. Parts 2–4 and going further (15:03–15:39, one background queue)

`run_all.sh part2`, `part3`, `part4`, `further` ran one after the other
(≈ 50 runs). Meanwhile:

- Part 2: version ties counted in the node logs of every run (65–123 per
  run under load, also in the runs the checker accepted); the q2local
  comparison for the checkpoint; my first explanation of q2local's valid
  run ("fewer ties") was **wrong** and was dropped after counting (112
  ties).
- Part 3: tie-breaks counted (110–160 per run, all resolved); 16 runs with
  N = 5 summarised per configuration with `tools/after.py`; the inversion
  found in the slow-n0 runs and, without any hook, in the ROWA partition
  run.
- Part 4: lost-update pairs searched in the traces (5 in q4a, 0 in q4b);
  lock statistics per run (locks taken, refusals, give-ups, locks still
  held at the end).
- A mistake avoided: I edited `run_all.sh` while a bash process was
  executing it. Bash reads scripts incrementally, so the running process
  could have resumed at a shifted offset; the edit was reverted at once
  (the file was byte-identical again before the running block ended) and
  redone after the queue finished.

## 8. Extra runs (15:39–15:49)

`run_all.sh part4b` (lock + latency + crash / partitions, `decisions.md`
D17; 4 more crash runs until a crash hit a lock holder) and `part2b`
(partition runs of q2/q2local, D18). Findings: a blocked key after a
partition, and after a crash of the holder (and of a lock request still
in flight); q2local's stale version not hit.

## 9. Documents, record, cited runs (15:10–16:00)

Part documents `01`–`08` written from the results; `record/record.tex`
filled in (3 pages, TikZ diagram of the Part 5 execution) and compiled
with Tectonic; `cite_runs.sh` copies the 27 cited runs to `runs/` and
writes `runs/INDEX.md`, which marks the 9 cited by the record (the ones
to submit). Final count: **118 Maelstrom runs** in `results/results.tsv`
(plus 3 smoke tests in `/tmp`, not recorded).

## 10. Session 2 – 2026-11-11: group 7, `inversion-run`, Part 0, AI log

Prompt and assessment in `ai-log.md` §2.

- `inversion-run.tar.bz2` (downloaded by the group into `~/TF_2`) was
  extracted in `kit/` as the guide says, and the archive moved to
  `archives/` (`.gitignore`d, like `kit.tar.bz2`).
- `tools/clockcheck.py`: no clock jump; `tools/anomaly.py` and
  `../kit/timeline.py inversion-run --history --key 0 | grep -v cas`: the
  anomaly at 3.345 / 3.738 s. `jepsen.log` gives the command line
  (`p3_slow.py`, rate 10, no latency, concurrency 2n). All 21 slow writes
  by p3 were then inspected by hand: a second inversion at 10.991 /
  11.284 s (my first count said "only one").
- `tools/sccheck.py` written; first version parsed no operation (wrong
  field order in `history.edn`) and so "proved" an empty history SC;
  fixed. Results: kit run SC (whole history, and with p1 merged into p0
  or p0 into p1); our `runs/p3-inversion` full history: stopped after
  15 min without an answer.
- Documents: `03` §5.1 (new), `05` §5 (new), `00-predict.md` rewritten,
  `ai-log.md` rewritten, `decisions.md` D8/D13/D14, `01` §3 (group 7),
  `code.md` §11, READMEs; record: Group 7, Part 1 Q5 paragraph, kit run in
  §3–§5; recompiled with Tectonic, still 3 pages.
- Later the same day: `00-predict.md` now holds Manuel's own Part 0
  answers (given by him), with the comparison against the runs; the
  assistant's reference answers were removed.
- Re-review of every decision against `q4b.py` and the runs
  (`decisions.md`, last section): no code change; the claim's cas
  statement ("same value" → "same version"), claim (ii) and the SC
  sentence of `05` §4 made precise; record recompiled.
