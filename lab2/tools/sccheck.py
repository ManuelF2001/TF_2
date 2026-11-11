#!/usr/bin/env python3

# Is the history of one key sequentially consistent?
#
#   tools/sccheck.py <run> [--key K] [--merge A,B]
#
# Knossos (the Maelstrom checker) only tests linearizability. Sequential
# consistency (SC) keeps register semantics and each process's program order
# but drops real time between processes. This tool searches for such an
# order: a depth-first search over "how many operations of each process are
# already placed" plus the register's current value, with memoisation. A read
# can be placed only if it returns the current value; a write always can.
#
# Only :ok reads and writes count: failed operations had no effect, and cas
# is ignored (until Part 4 every cas fails). Pending (:info) writes are not
# handled; the runs we check with it have none.
#
# --merge A,B pretends that process B's operations were issued by process A
# (merged in history order): Part 5 Q3, "would the answer change if the
# operations had been performed by the same client?".
#
# The search is exponential in the worst case; on a 20 s run at rate 10 it
# takes a few seconds, at rate 50 it may not finish.

import re
import sys
from pathlib import Path

args = sys.argv[1:]
run = Path(args[0])
key = int(args[args.index('--key') + 1]) if '--key' in args else 0
merge = args[args.index('--merge') + 1].split(',') if '--merge' in args else None


def field(pat, line):
    m = re.search(pat, line)
    return m.group(1) if m else None


ops = []   # (index, process, f, value)
for line in (run / 'history.edn').read_text().splitlines():
    kv = re.search(r':value \[(\d+) (nil|-?\d+)\]', line)
    t, f = field(r':type :(\w+)', line), field(r':f :(\w+)', line)
    p, i = field(r':process (\d+)', line), field(r':index (\d+)', line)
    if not (kv and t and f and p and i) or t != 'ok' or f == 'cas':
        continue
    if int(kv.group(1)) != key:
        continue
    v = kv.group(2)
    ops.append((int(i), p, f, None if v == 'nil' else int(v)))
ops.sort()

procs = {}
for _, p, f, v in ops:
    if merge and p == merge[1]:
        p = merge[0]
    procs.setdefault(p, []).append((f, v))
names = sorted(procs, key=int)
seqs = [procs[p] for p in names]
print('key %d, ok operations per process: %s'
      % (key, ', '.join('p%s=%d' % (p, len(procs[p])) for p in names)))

seen = set()
stack = [(tuple(0 for _ in seqs), None)]
most = 0
while stack:
    pos, val = stack.pop()
    if (pos, val) in seen:
        continue
    seen.add((pos, val))
    most = max(most, sum(pos))
    if all(pos[j] == len(seqs[j]) for j in range(len(seqs))):
        print('SEQUENTIALLY CONSISTENT (%d states explored)' % len(seen))
        sys.exit(0)
    for j, seq in enumerate(seqs):
        if pos[j] == len(seq):
            continue
        f, v = seq[pos[j]]
        if f == 'read' and v != val:
            continue
        stack.append((pos[:j] + (pos[j] + 1,) + pos[j + 1:], v))
print('NOT sequentially consistent (%d states explored; at most %d of %d '
      'operations could be placed)' % (len(seen), most, len(ops)))
sys.exit(1)
