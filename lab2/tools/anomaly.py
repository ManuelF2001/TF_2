#!/usr/bin/env python3

# Where did the checker find a lin-kv run non-linearizable?
#
#   tools/anomaly.py <run> [--key K] [--before 1.5] [--after 0.2] [--hide-cas]
#
# For each non-linearizable key (or only --key K) prints the operation the
# checker could not linearize (":op") and the last one it could
# (":previous-ok"), from results.edn, then the merged timeline of that key
# (../kit/timeline.py --history --key K) in the window [t - before, t + after]
# around the failing operation, in timeline.py's time base (0 = first client
# request).

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

parser = argparse.ArgumentParser(description='Where did the checker find a lin-kv run non-linearizable?')
parser.add_argument('run')
parser.add_argument('--key', help='only this key')
parser.add_argument('--before', type=float, default=1.5, help='seconds of history before the failing op')
parser.add_argument('--after', type=float, default=0.2, help='seconds after it')
parser.add_argument('--hide-cas', action='store_true', help='leave out cas operations (Parts 1-3: always error 10)')
args = parser.parse_args()

KIT = Path(__file__).resolve().parent.parent.parent / 'kit'
run = Path(args.run)
text = (run / 'results.edn').read_text()
workload = text[text.index(':workload'):]

def op(name, chunk):
    m = re.search(r':' + name + r' \{(.*?)\}', chunk, re.S)
    if not m:
        return None
    fields = dict(re.findall(r':(\w+) (\[[^\]]*\]|[^,\s}]+)', m.group(1)))
    return fields

# Knossos identifies operations by their :index in the history. The i-th
# operation line of jepsen.log is history entry i, and jepsen.log has the
# wall-clock time that timeline.py and the trace() events also use. (The
# :time field of the history is a monotonic clock that can drift from the
# wall clock, by almost 0.5 s under WSL, so it is not used.)
OP = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3})\S*\t\w+\t\[jepsen worker (?:\d+|nemesis)\] jepsen\.util: (.*)$')
stamps = [(datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S,%f').timestamp(), m.group(2))
          for m in map(OP.match, (run / 'jepsen.log').read_text(errors='replace').splitlines()) if m]
t0 = min((t for t, rest in stamps if '\t:invoke\t' in rest and not rest.startswith(':nemesis')), default=0)

def when(o):
    return stamps[int(o['index'])][0] - t0

# Wall-clock steps (see tools/clockcheck.py): a trace event older than the
# previous one of the same node. Around them timeline.py's order is unreliable.
steps = []
for log in sorted((run / 'node-logs').glob('*.log')):
    last = None
    for line in log.read_text(errors='replace').splitlines():
        if line.startswith('TRACE '):
            t = float(re.search(r'"t": ([\d.]+)', line).group(1))
            if last is not None and t < last - 0.001:
                steps.append((log.stem, last - t0, t - t0))
            last = t if last is None else max(last, t)

found = False
for m in re.finditer(r'(\d+) \{:linearizable \{:valid\? false', workload):
    key = m.group(1)
    if args.key is not None and key != args.key:
        continue
    found = True
    chunk = workload[m.start():]
    nxt = re.search(r'\n\s+\d+ \{:linearizable', chunk[10:])
    chunk = chunk[:nxt.start() + 10] if nxt else chunk
    # :previous-ok is the last operation the checker could linearize; the
    # operations it then could not are the ones whose model, in
    # :final-paths, is Inconsistent.
    prev = op('previous-ok', chunk)
    bad = None
    print(f'=== key {key}')
    if prev:
        print(f"last linearizable  p{prev['process']} {prev['type']} {prev['f']} {prev['value']}"
              f"   (t = {when(prev):.3f} s)")
    seen = set()
    for m2 in re.finditer(r'\{:op \{([^}]*)\},\s*:model #knossos\.model\.Inconsistent\{:msg "([^"]*)"\}', chunk):
        o = dict(re.findall(r':(\w+) (\[[^\]]*\]|[^,\s}]+)', m2.group(1)))
        if (o['index'], m2.group(2)) in seen:
            continue
        seen.add((o['index'], m2.group(2)))
        bad = o if bad is None or int(o['index']) > int(bad['index']) else bad
        print(f"cannot linearize   p{o['process']} {o['type']} {o['f']} {o['value']}"
              f"   (t = {when(o):.3f} s): {m2.group(2)}")
    bad = bad or op('op', chunk)
    if bad:
        t = when(bad)
        lo, hi = t - args.before, t + args.after
        out = subprocess.run([sys.executable, str(KIT / 'timeline.py'), str(run),
                              '--history', '--key', key], capture_output=True, text=True).stdout
        jumps = sorted({(round(a, 3), round(b, 3)) for _, a, b in steps if b <= hi and a >= lo})
        if jumps:
            print('WARNING: the wall clock jumped back inside this window '
                  f'({", ".join(f"{a:.3f} -> {b:.3f}" for a, b in jumps[:3])}): '
                  'check the order of events in node-logs/*.log')
        print(f'--- timeline of key {key}, {lo:.3f} .. {hi:.3f} s')
        for line in out.splitlines():
            try:
                tl = float(line.split()[0])
            except (ValueError, IndexError):
                continue
            if args.hide_cas and ' cas ' in line:
                continue
            if lo <= tl <= hi or 'nemesis' in line.split()[1:2]:
                print(line)
if not found:
    print('no non-linearizable key' + (f' {args.key}' if args.key else ''))
