#!/usr/bin/env python3

# Summarise results/results.tsv as a markdown table, one row per
# (program, N, QR, QW, scenario), in the order they were first run.
#
#   tools/table.py [program ...]        e.g. tools/table.py q1.py

import re
import sys
from pathlib import Path

rows = {}
for line in (Path(__file__).resolve().parent.parent / 'results' / 'results.tsv').read_text().splitlines():
    prog, n, qr, qw, scenario, summary, run = line.split('\t')
    if len(sys.argv) > 1 and prog not in sys.argv[1:]:
        continue
    f = dict(re.findall(r'(\w+(?:/op)?)=(\S+)', summary))
    rows.setdefault((prog, n, qr, qw, scenario), []).append((f, Path(run).name))

print('| program | N | (QR,QW) | scenario | linearizable | ok / fail / info per run | msgs/op | runs |')
print('|---|---|---|---|---|---|---|---|')
for (prog, n, qr, qw, scenario), runs in rows.items():
    lin = [f['lin'] for f, _ in runs]
    verdict = f"{lin.count('yes')}/{len(lin)} yes" if 'NO' in lin else f'yes ×{len(lin)}'
    counts = ' · '.join(f"{f['ok']}/{f['fail']}/{f['info']}" for f, _ in runs)
    mpo = sum(float(f['msgs/op']) for f, _ in runs if f['msgs/op'] != '-') / len(runs)
    cas = [int(f['cas_ok']) for f, _ in runs]
    extra = f" (cas_ok {'/'.join(map(str, cas))})" if any(cas) else ''
    print(f"| {prog} | {n[2:]} | ({qr[3:]},{qw[3:]}) | {scenario} | {verdict} | {counts}{extra} | {mpo:.2f} | "
          + ', '.join(r for _, r in runs) + ' |')
