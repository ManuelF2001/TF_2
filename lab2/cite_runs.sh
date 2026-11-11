#!/usr/bin/env bash

# Copy the runs cited in the documents and the record from store/ (all raw
# runs, not submitted) to runs/<name> (submitted), and write runs/INDEX.md.
#
#   bash cite_runs.sh
#
# Edit the list below to change what is cited. Each line: name  store-run-id

cd "$(dirname "$0")"
mkdir -p runs
index=runs/INDEX.md
{
echo "# Cited runs"
echo
echo "Copies of the Maelstrom runs cited in \`docs/\` and \`record/\` (the raw"
echo "runs are in \`store/lin-kv/\`, not submitted). Regenerate with"
echo "\`bash cite_runs.sh\`."
echo
echo "| name | store run | program | N | QR | QW | scenario | summary |"
echo "|---|---|---|---|---|---|---|---|"
} > "$index"

while read -r name id; do
    [ -z "$name" ] && continue
    case $name in \#*) continue ;; esac
    src=store/lin-kv/$id
    if [ ! -d "$src" ]; then echo "missing $src" >&2; continue; fi
    rm -rf "runs/$name"
    cp -rL "$src" "runs/$name"
    line=$(grep -F "$id" results/results.tsv | head -1)
    IFS=$'\t' read -r prog n qr qw scenario summary _ <<< "$line"
    echo "| \`$name\` | \`$id\` | $prog | ${n#N=} | ${qr#QR=} | ${qw#QW=} | $scenario | $summary |" >> "$index"
done <<'EOF'
# Part 1
p1-rowa-latency            20261030T144816.502Z
p1-majority-latency        20261030T144955.465Z
p1-nonint-latency          20261030T145229.686Z
p1-rowa-crash              20261030T145333.767Z
p1-rowa-partition          20261030T145816.949Z
p1-majority-ring           20261030T145950.982Z
p1-majority-partition      20261030T150022.454Z
p1-nonint-partition        20261030T150125.015Z
# Part 2
p2-latency                 20261030T150432.624Z
p2local-latency            20261030T151027.829Z
p2local-partition          20261030T154523.537Z
# Part 3
p3-latency                 20261030T151132.003Z
p3-rowa-crash              20261030T152008.900Z
p3-rowa-partition          20261030T152111.376Z
p3-42-crash2               20261030T152450.974Z
p3-inversion               20261030T152554.648Z
p3-inversion-2             20261030T152627.198Z
# Part 4
p4-lost-update             20261030T152732.164Z
p4-lock-latency            20261030T152909.496Z
p4-split-quorum            20261030T153958.994Z
p4-starvation              20261030T154031.997Z
p4-blocked-key             20261030T154242.759Z
p4-crash-inflight          20261030T154722.633Z
p4-crash-holder            20261030T154828.000Z
# Going further
px-slow-n0                 20261030T153357.110Z
px-rowa-crash              20261030T153606.693Z
px-latency                 20261030T153744.144Z
EOF
{
echo
echo "**Cited by the record** (submit these with it, as the guide asks: \"the"
echo "store/ directories of the runs it cites (only those)\"):"
echo "\`p1-rowa-latency\`, \`p1-majority-latency\`, \`p2-latency\`, \`p3-inversion\`,"
echo "\`p3-rowa-partition\`, \`p4-lost-update\`, \`p4-crash-holder\`, \`p4-blocked-key\`,"
echo "\`px-rowa-crash\`. The others are cited only in \`docs/\`."
echo
echo "**Not ours:** the kit's \`inversion-run\` (teachers' \`p3_slow.py\`) is in"
echo "\`../kit/inversion-run\`; the record mentions it, but it is not a run of"
echo "ours and is not submitted."
} >> "$index"
echo "copied $(ls runs | grep -vc INDEX) runs; index in $index"
