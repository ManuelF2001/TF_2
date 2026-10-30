# Fault-Tolerant Distributed Systems — practical work, Lab 2

```
TF_2/
├── README.md        this file
├── .gitignore       store/, maelstrom, archives/, caches (if this becomes a git repo)
├── env.sh           Java 17 + gnuplot on the PATH, MAELSTROM -> ./maelstrom
├── archives/        original download: kit.tar.bz2 (Lab 2 kit)
├── kit/             course kit: Lab 1 kit + Lab 2 kit extracted over it, unmodified
├── maelstrom ->     symlink to ~/TF/maelstrom (Maelstrom 0.2.4, from Lab 1)
└── lab2/            Lab 2 — Quorums (everything we did is here)
```

Lab 1 is in `~/TF` (same layout: `kit/`, `maelstrom/`, `env.sh`, `lab1/`).

`kit/` and `maelstrom/` are kept exactly as distributed, so that they can be
re-extracted at any time; all our work is in `lab2/`. How `kit/` was built
from the two kit archives, and why Maelstrom is a symlink, is explained in
[`lab2/docs/decisions.md`](lab2/docs/decisions.md) (D0, D1).

## Setup on this machine

Java 17 and gnuplot were installed for Lab 1 without sudo in
`~/.local/opt` (see `~/TF/README.md`). Before running anything by hand:

```bash
source ~/TF_2/env.sh
```

(`lab2/scenarios.sh` does it automatically.) Installation check, inside
`kit/`: `./run.sh echo echo.py` ends with *Everything looks good!*
(done on 2026-10-30; then `rm -rf kit/store`).

If the symlink is broken (another machine), extract Maelstrom 0.2.4 here:
`tar -xjf ~/TF/archives/maelstrom.tar.bz2 -C ~/TF_2` after `rm maelstrom`.

## Lab 2

Start at [`lab2/README.md`](lab2/README.md).
