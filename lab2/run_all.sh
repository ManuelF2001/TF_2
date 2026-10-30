#!/usr/bin/env bash

# Reproduce every run cited in the Lab 2 documents. Results are appended to
# results/results.tsv (one line per run). About 40 s per run.
#
#   bash run_all.sh            everything (~1 h 30)
#   bash run_all.sh part1      Part 1: q1.py, 3 configurations x 4 scenarios x 3 runs
#   bash run_all.sh part2      Part 2: q2.py (and the q2local.py alternative)
#   bash run_all.sh part2b     Part 2: more partition runs of q2.py and q2local.py
#   bash run_all.sh part3      Part 3: q3.py under load, availability with N=5, inversion
#   bash run_all.sh part4      Part 4: cas without lock (q4a.py), with lock (q4b.py)
#   bash run_all.sh part4b     Part 4: lock under latency + crash / partitions
#   bash run_all.sh further    Going further: read with write-back (qx.py)

cd "$(dirname "$0")"
part=${1:-all}
want() { [ "$part" = all ] || [ "$part" = "$1" ]; }
s() { bash scenarios.sh "$@"; }

if want part1; then
    # ROWA (1,3), majority (2,2), non-intersecting (1,2); one scenario for
    # the three configurations at a time, as in the guide
    for scenario in nofaults latency crash-n1 partition; do
        for q in "1 3" "2 2" "1 2"; do
            s code/q1.py $q $scenario 3
        done
    done
fi

if want part2; then
    # majority from now on; the scenarios of Part 1, then more load
    for scenario in nofaults crash-n1 partition; do
        s code/q2.py 2 2 $scenario 1
    done
    s code/q2.py 2 2 latency 5
    s code/q2.py 2 2 latency-high 5
    # checkpoint: the other answer to question 1 (version from own copy)
    s code/q2local.py 2 2 latency 3
fi

if want part2b; then
    # added after the first Part 2 runs: partitions expose the stale
    # version of a coordinator that was cut off (q2local), not just ties
    s code/q2.py 2 2 partition 2
    s code/q2local.py 2 2 partition 3
fi

if want part3; then
    # question 2: the tie-breaking rule, under latency and load
    s code/q3.py 2 2 latency 5
    s code/q3.py 2 2 latency-high 5
    # question 3: availability with N=5
    for q in "3 3" "1 5" "2 4" "4 2"; do
        for scenario in nofaults crash-n1 crash-n1-n2 partition; do
            s code/q3.py $q $scenario 1 5
        done
    done
    # questions 4-5: a write that reached only its coordinator (our own
    # version of inversion-run: puts from n0 delayed 0.5 s)
    s code/q3.py 2 2 slow-n0 3
fi

if want part4; then
    # cas without a lock: lost updates
    s code/q4a.py 2 2 latency 3
    # cas and write under a majority lock
    s code/q4b.py 2 2 latency 3
    s code/q4b.py 2 2 crash-n1 3
    s code/q4b.py 2 2 partition 3
fi

if want part4b; then
    # the guide's Part 4 Q4 adds the crash and the partitions ON TOP of
    # --latency 50 --rate 50 (we first ran them without latency, part4):
    # with latency a lock is held long enough for a fault to hit it
    s code/q4b.py 2 2 latency-crash-n1 3
    s code/q4b.py 2 2 latency-partition 3
    # 4 more crash runs, trying to catch n1 while it holds a lock quorum
    s code/q4b.py 2 2 latency-crash-n1 4
fi

if want further; then
    # read with write-back: the inversion should disappear
    s code/qx.py 2 2 slow-n0 3
    for scenario in nofaults crash-n1 partition; do
        s code/qx.py 1 5 $scenario 1 5
    done
    s code/qx.py 3 3 nofaults 1 5
    s code/qx.py 2 2 latency 3
fi
