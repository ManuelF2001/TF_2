#!/usr/bin/env python3

# Did the wall clock jump during a run?
#
#   tools/clockcheck.py <run> [<run> ...]
#
# trace() events carry time.time() (wall clock), and so do jepsen.log lines;
# ../kit/timeline.py sorts by these times. Under WSL the virtual machine's
# wall clock is periodically corrected (stepped) to the Windows host's, so it
# can jump backwards by tenths of a second during a run. Each node writes its
# log in execution order, so a trace event whose time is lower than the
# previous event of the same node reveals a step. Around a step, the merged
# timeline can show events in the wrong order (the node log files, and the
# checker, which uses the order of the history, are not affected).

import json
import sys
from pathlib import Path

for run in sys.argv[1:]:
    steps = []
    for log in sorted(Path(run, 'node-logs').glob('*.log')):
        last = None
        for line in log.read_text(errors='replace').splitlines():
            if line.startswith('TRACE '):
                t = json.loads(line[6:])['t']
                if last is not None and t < last - 0.001:
                    steps.append((log.stem, last, t))
                last = t if last is None else max(last, t)
    worst = max((a - b for _, a, b in steps), default=0)
    print(f'{Path(run).resolve().name}: {len(steps)} backward steps, largest {worst:.3f} s'
          + ''.join(f'\n    {n}: {a:.3f} -> {b:.3f}' for n, a, b in steps[:5]))
