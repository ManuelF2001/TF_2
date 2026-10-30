#!/usr/bin/env python3

# One line per Maelstrom lin-kv run: linearizability verdict, operation counts,
# messages between servers per operation, and the keys found non-linearizable.
#
#   ./summary.py [run directories...]     (default: store/latest)

import re
import sys
from pathlib import Path

def summary(run):
    text = (Path(run) / 'results.edn').read_text()
    workload = text[text.index(':workload'):]
    lin = re.search(r':valid\? (\w+)', workload).group(1)
    stats = text[text.index(':stats'):text.index(':by-f')]
    counts = {k: int(re.search(rf':{k}-count (\d+)', stats).group(1)) for k in ('ok', 'fail', 'info')}
    servers = text[text.index(':servers'):]
    mpo = re.search(r':msgs-per-op ([\d.]+)', servers)
    bad = sorted({k for k, v in re.findall(r'(\d+) \{:linearizable \{:valid\? (\w+)', workload) if v == 'false'}, key=int)
    by_f = {f: int(n) for f, n in re.findall(r':(read|write|cas) \{:valid\? \w+,\s+:count \d+,\s+:ok-count (\d+)', text)}
    return (f"lin={'yes' if lin == 'true' else 'NO '} ok={counts['ok']:<4} fail={counts['fail']:<4} "
            f"info={counts['info']:<4} msgs/op={mpo.group(1) if mpo else '-':<5} "
            f"cas_ok={by_f.get('cas', 0):<4} bad_keys={','.join(bad) or '-'}")

if __name__ == '__main__':
    for run in sys.argv[1:] or ['store/latest']:
        print(f"{summary(run)}  {Path(run).resolve().name}")
