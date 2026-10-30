#!/usr/bin/env python3

# Count client operation results by type and by server, before and after a
# time (e.g. a crash at 5 s), from the merged history of a run.
#
#   tools/after.py <run> [seconds]        (default 5)
#
# Example output line:  after 5.0 s  n0  write ok=0 fail=0 info=12
# Uses ../kit/timeline.py --history (time 0 = first client request; the
# crash time of MS_CRASH is measured from the nodes' init, a few ms earlier).

import collections
import re
import subprocess
import sys
from pathlib import Path

run = sys.argv[1]
cut = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
kit = Path(__file__).resolve().parent.parent.parent / 'kit'
out = subprocess.run([sys.executable, str(kit / 'timeline.py'), run, '--history'],
                     capture_output=True, text=True).stdout

node_of = {}            # process -> node of its last invoke
counts = collections.Counter()
for line in out.splitlines():
    m = re.match(r'\s*([\d.]+)\s+p(\d+)\s+(\w+)\s+(\w+) .*?(?:-> (n\d+))?$', line)
    if not m:
        continue
    t, p, kind, f, node = m.groups()
    if kind == 'invoke':
        node_of[p] = node
        continue
    when = 'before' if float(t) < cut else 'after'
    counts[(when, node_of.get(p, '?'), f, kind)] += 1

for when in ('before', 'after'):
    for node in sorted({k[1] for k in counts}):
        for f in ('read', 'write', 'cas'):
            c = {kind: counts[(when, node, f, kind)] for kind in ('ok', 'fail', 'info')}
            if any(c.values()):
                print(f"{when:6} {cut:.1f} s  {node}  {f:5} ok={c['ok']} fail={c['fail']} info={c['info']}")
