# Cited runs

Copies of the Maelstrom runs cited in `docs/` and `record/` (the raw
runs are in `store/lin-kv/`, not submitted). Regenerate with
`bash cite_runs.sh`.

| name | store run | program | N | QR | QW | scenario | summary |
|---|---|---|---|---|---|---|---|
| `p1-rowa-latency` | `20261030T144816.502Z` | q1.py | 3 | 1 | 3 | latency | lin=NO  ok=703  fail=282  info=0    msgs/op=2.8751268 cas_ok=0    bad_keys=0 |
| `p1-majority-latency` | `20261030T144955.465Z` | q1.py | 3 | 2 | 2 | latency | lin=NO  ok=578  fail=377  info=0    msgs/op=2.4209423 cas_ok=0    bad_keys=0 |
| `p1-nonint-latency` | `20261030T145229.686Z` | q1.py | 3 | 1 | 2 | latency | lin=NO  ok=639  fail=316  info=0    msgs/op=2.6764398 cas_ok=0    bad_keys=0 |
| `p1-rowa-crash` | `20261030T145333.767Z` | q1.py | 3 | 1 | 3 | crash-n1 | lin=yes ok=111  fail=61   info=32   msgs/op=2.1323528 cas_ok=0    bad_keys=- |
| `p1-rowa-partition` | `20261030T145816.949Z` | q1.py | 3 | 1 | 3 | partition | lin=NO  ok=138  fail=77   info=3    msgs/op=2.582569 cas_ok=0    bad_keys=0 |
| `p1-majority-ring` | `20261030T145950.982Z` | q1.py | 3 | 2 | 2 | partition | lin=yes ok=13   fail=139  info=34   msgs/op=1.6344086 cas_ok=0    bad_keys=- |
| `p1-majority-partition` | `20261030T150022.454Z` | q1.py | 3 | 2 | 2 | partition | lin=yes ok=99   fail=95   info=7    msgs/op=2.0547264 cas_ok=0    bad_keys=- |
| `p1-nonint-partition` | `20261030T150125.015Z` | q1.py | 3 | 1 | 2 | partition | lin=NO  ok=126  fail=80   info=8    msgs/op=2.457944 cas_ok=0    bad_keys=0 |
| `p2-latency` | `20261030T150432.624Z` | q2.py | 3 | 2 | 2 | latency | lin=NO  ok=532  fail=315  info=0    msgs/op=3.244392 cas_ok=0    bad_keys=0 |
| `p2local-latency` | `20261030T151027.829Z` | q2local.py | 3 | 2 | 2 | latency | lin=NO  ok=548  fail=384  info=0    msgs/op=2.3519313 cas_ok=0    bad_keys=0 |
| `p2local-partition` | `20261030T154523.537Z` | q2local.py | 3 | 2 | 2 | partition | lin=yes ok=125  fail=70   info=1    msgs/op=2.3520408 cas_ok=0    bad_keys=- |
| `p3-latency` | `20261030T151132.003Z` | q3.py | 3 | 2 | 2 | latency | lin=yes ok=554  fail=267  info=0    msgs/op=3.5225334 cas_ok=0    bad_keys=- |
| `p3-rowa-crash` | `20261030T152008.900Z` | q3.py | 5 | 1 | 5 | crash-n1 | lin=yes ok=98   fail=72   info=29   msgs/op=5.3165827 cas_ok=0    bad_keys=- |
| `p3-rowa-partition` | `20261030T152111.376Z` | q3.py | 5 | 1 | 5 | partition | lin=NO  ok=120  fail=69   info=5    msgs/op=6.546392 cas_ok=0    bad_keys=0 |
| `p3-42-crash2` | `20261030T152450.974Z` | q3.py | 5 | 4 | 2 | crash-n1-n2 | lin=yes ok=36   fail=127  info=38   msgs/op=3.522388 cas_ok=0    bad_keys=- |
| `p3-inversion` | `20261030T152554.648Z` | q3.py | 3 | 2 | 2 | slow-n0 | lin=NO  ok=645  fail=314  info=0    msgs/op=3.3409803 cas_ok=0    bad_keys=0 |
| `p3-inversion-2` | `20261030T152627.198Z` | q3.py | 3 | 2 | 2 | slow-n0 | lin=NO  ok=656  fail=313  info=0    msgs/op=3.360165 cas_ok=0    bad_keys=0 |
| `p4-lost-update` | `20261030T152732.164Z` | q4a.py | 3 | 2 | 2 | latency | lin=NO  ok=553  fail=165  info=0    msgs/op=4.8245125 cas_ok=35   bad_keys=0 |
| `p4-lock-latency` | `20261030T152909.496Z` | q4b.py | 3 | 2 | 2 | latency | lin=yes ok=428  fail=149  info=2    msgs/op=6.7668395 cas_ok=8    bad_keys=- |
| `p4-split-quorum` | `20261030T153958.994Z` | q4b.py | 3 | 2 | 2 | latency-crash-n1 | lin=yes ok=337  fail=108  info=25   msgs/op=5.106383 cas_ok=2    bad_keys=- |
| `p4-starvation` | `20261030T154031.997Z` | q4b.py | 3 | 2 | 2 | latency-crash-n1 | lin=yes ok=362  fail=88   info=21   msgs/op=5.1252656 cas_ok=6    bad_keys=- |
| `p4-blocked-key` | `20261030T154242.759Z` | q4b.py | 3 | 2 | 2 | latency-partition | lin=yes ok=392  fail=125  info=3    msgs/op=6.3807693 cas_ok=4    bad_keys=- |
| `p4-crash-inflight` | `20261030T154722.633Z` | q4b.py | 3 | 2 | 2 | latency-crash-n1 | lin=yes ok=347  fail=100  info=19   msgs/op=4.995708 cas_ok=0    bad_keys=- |
| `p4-crash-holder` | `20261030T154828.000Z` | q4b.py | 3 | 2 | 2 | latency-crash-n1 | lin=yes ok=362  fail=79   info=17   msgs/op=5.0524015 cas_ok=2    bad_keys=- |
| `px-slow-n0` | `20261030T153357.110Z` | qx.py | 3 | 2 | 2 | slow-n0 | lin=yes ok=640  fail=314  info=0    msgs/op=3.60587 cas_ok=0    bad_keys=- |
| `px-rowa-crash` | `20261030T153606.693Z` | qx.py | 5 | 1 | 5 | crash-n1 | lin=yes ok=27   fail=127  info=42   msgs/op=7.7602043 cas_ok=0    bad_keys=- |
| `px-latency` | `20261030T153744.144Z` | qx.py | 3 | 2 | 2 | latency | lin=yes ok=471  fail=326  info=0    msgs/op=3.663739 cas_ok=0    bad_keys=- |

**Cited by the record** (submit these with it, as the guide asks: "the
store/ directories of the runs it cites (only those)"):
`p1-rowa-latency`, `p1-majority-latency`, `p2-latency`, `p3-inversion`,
`p3-rowa-partition`, `p4-lost-update`, `p4-crash-holder`, `p4-blocked-key`,
`px-rowa-crash`. The others are cited only in `docs/`.
