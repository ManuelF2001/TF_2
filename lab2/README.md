# Lab 2 – Quorums

Guide: [`lab2.pdf`](lab2.pdf). Deliverable due **Friday, 13 November**:
lab record (≤ 3 pages, `record/record.tex`) + code + the `store/` runs it
cites (`runs/`).

**The question:** is there a middle ground between waiting for one server
and waiting for all of them? A key-value store in which every operation
waits for *some* servers: what does it need to be correct, and how many
failures does it tolerate?

## Results at a glance

118 Maelstrom runs (`results/results.tsv`). "lin" = runs the checker found
linearizable.

| step | program | what it adds | key result |
|---|---|---|---|
| Part 1 | `q1.py` | wait for Qr / Qw answers, values only | no faults: lin 9/9; **latency + load: 0/9** (copies diverge); ROWA: 0 writes after 1 crash |
| Part 2 | `q2.py` | versions (writer asks a read quorum first) | latency: 0/5, latency 100: 2/5 — concurrent writes get **equal versions** |
| Part 3 | `q3.py` | tie-break `[number, client]` | latency + load: **10/10**; but **new–old inversion** with a slow link (0/3) and in ROWA partitions |
| Part 3 Q3 | `q3.py`, N = 5 | 4 configurations × 4 scenarios | majority survives 2 crashes; ROWA: 0 writes after 1 crash; (4,2): nothing with 2 crashes |
| Part 4 | `q4a.py` | cas = read, compare, write | 0/3: **lost updates** (two cas from the same value both succeed) |
| Part 4 | `q4b.py` | majority lock for cas and write | **19/19 lin**; ≈ 3.5 locked ops/s per key; a crashed or cut-off lock holder **blocks the key forever** |
| Further | `qx.py` | write-back on reads | slow link 0/3 → **3/3**; ROWA reads now need all 5 servers |

The final store (`q4b.py`) is regular-not-atomic for reads, atomic for
writes and cas, and tolerates 1 failure of 3, except for keys whose lock
the failed server held: claim in `docs/05-explain-execution.md` §4.

**Group 7** (Part 1 Q5: majority, `docs/01-wait-for-some.md` §3.2). The
kit's `inversion-run` is in `../kit/inversion-run`: same anomaly as our
reproduction, not linearizable but sequentially consistent
(`docs/03-concurrent-writers.md` §5.1, `docs/05-explain-execution.md` §5).

## Layout

```
lab2/
├── README.md               this file
├── lab2.pdf                the lab guide
├── code/                   one program per design step (decisions.md D7)
│   ├── q1.py               Part 1: values only, QR/QW quorums
│   ├── q2.py               Part 2: + versions (coordinator asks a read quorum first)
│   ├── q2local.py          Part 2, alternative: version from the coordinator's own copy
│   ├── q3.py               Part 3: + tie-break, tag = [number, client]  (+ SLOW_PUT test hook)
│   ├── q4a.py              Part 4: + cas (read, compare, write), no lock
│   ├── q4b.py              Part 4: + majority lock for cas and write   <- final store
│   ├── qx.py               Going further: q3 + read write-back
│   └── ms.py               unmodified copy of kit/ms.py (must sit next to the programs)
├── docs/
│   ├── theory.md           quorums, intersection, versions, regular vs atomic, cas, locks, availability
│   ├── code.md             what the software does: every program and script explained
│   ├── decisions.md        every doubt and the choice made (D0–D16)
│   ├── worklog.md          what was done, in order
│   ├── 00-predict.md       Part 0 – predictions
│   ├── 01-wait-for-some.md Part 1 – 12 combinations, 3 runs each, explained anomalies
│   ├── 02-agree-on-newest.md   Part 2 – versions, diagram, runs, checkpoint
│   ├── 03-concurrent-writers.md Part 3 – tie-break, availability N=5, new-old inversion
│   ├── 04-compare-and-set.md   Part 4 – lost updates, lock design, lock runs
│   ├── 05-explain-execution.md Part 5 – one execution explained, classified; revised claim
│   ├── 06-compare.md       Part 6 – class table rows, lock takeover
│   ├── 07-going-further.md Going further – write-back
│   ├── 08-exit-record.md   Exit record (four lines)
│   └── ai-log.md           AI log (deliverable item 5)
├── record/
│   ├── record.tex          the lab record (≤ 3 pages)
│   └── record.pdf          compiled
├── tools/
│   ├── anomaly.py          where did the checker find a run non-linearizable? (+ timeline window)
│   ├── after.py            ok/fail/info per server and operation, before/after a time
│   ├── clockcheck.py       did the wall clock jump during a run? (WSL, worklog.md §5)
│   ├── sccheck.py          is the history of a key sequentially consistent? (Part 5 Q3)
│   └── table.py            results/results.tsv -> markdown table
├── runs/                   copies of the cited runs (INDEX.md lists them)
├── results/results.tsv     one line per run: program, N, QR, QW, scenario, summary.py line, store dir
├── scenarios.sh            run one scenario N times and record it
├── run_all.sh              rerun everything (≈ 1 h 30)
├── cite_runs.sh            copy the cited runs from store/ to runs/
└── store/                  all raw Maelstrom runs (not submitted)
```

Suggested reading order: `theory.md` → `00` … `08` → `code.md`;
`decisions.md` for every choice we had to make.

## Running

From `lab2/` (in WSL):

```bash
source ../env.sh                                  # Java + gnuplot + MAELSTROM
QR=2 QW=2 ../kit/run.sh lin-kv code/q4b.py        # one run; results in store/latest
../kit/summary.py                                 # lin=, counts, msgs/op
../kit/timeline.py --history --key 0 | grep -v cas
tools/anomaly.py store/latest --hide-cas          # what the checker could not linearize

bash scenarios.sh code/q3.py 3 3 crash-n1 1 5     # QR=3 QW=3, n1 crashes, 1 run, N=5
bash run_all.sh part3                             # every run of Part 3
bash cite_runs.sh                                 # refresh runs/
```

Scenarios: `nofaults`, `latency`, `latency-high`, `crash-n1`,
`crash-n1-n2`, `partition`, `latency-crash-n1`, `latency-partition`,
`slow-n0` (header of `scenarios.sh`).

Compile the record: `cd record && tectonic record.tex` (Tectonic is in
`~/.local/bin`), or upload `record.tex` to Overleaf.

## Before submitting (13 November) — what the group still has to do

- [x] Group number (7) in `record/record.tex`.
- [ ] Fill in the member names and **Contributions** in
      `record/record.tex` (and recompile).
- [x] Part 0: Manuel's answers in `docs/00-predict.md`, compared with
      the runs. Other members: add yours there.
- [ ] Check the design decisions in `docs/decisions.md` (D2, D5, D6, D9 in
      particular); if the group decides otherwise, change the program and
      rerun (`run_all.sh partN`).
- [x] Part 1 Q5, group 7 → majority: `docs/01-wait-for-some.md` §3.2,
      cited in the record (§2).
- [x] `inversion-run.tar.bz2` extracted in `kit/` and compared with our
      reproduction (`docs/03-concurrent-writers.md` §5.1).
- [ ] Fill in the last column of `docs/ai-log.md` §6 (what *you*
      accepted, changed or rejected) and the last bullet of §5 of the
      record; optionally ask a *fresh* AI session whether the Part 2 store
      is linearizable (suggested prompt in `docs/ai-log.md` §7).
- [ ] Replace our rows in `docs/06-compare.md` with the class table.
- [ ] Every member can explain every line of `code/q4b.py` and the steps
      before it (`docs/code.md`): the final discussion is individual.
- [ ] Submit: `record/record.pdf` (+ `.tex`), `code/`, and the 9 runs cited
      by the record (listed at the end of `runs/INDEX.md`).
