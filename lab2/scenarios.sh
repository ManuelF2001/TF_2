#!/usr/bin/env bash

# Run one Lab 2 scenario and append one line per run to results/results.tsv:
#   program  N  QR  QW  scenario  <./summary.py line>  run-directory
#
#   bash scenarios.sh <program.py> <QR> <QW> <scenario> [repeats] [N]
#
# e.g.  bash scenarios.sh code/q1.py 2 2 latency 3
#       bash scenarios.sh code/q3.py 3 3 crash-n1 1 5
#
# Scenarios (Part 1 table, plus the ones used later):
#   nofaults       no options
#   latency        --latency 50 --rate 50
#   latency-high   --latency 100 --rate 100
#   crash-n1       MS_CRASH="n1@5"           (n1 crash-stops 5 s after start)
#   crash-n1-n2    MS_CRASH="n1@5,n2@5"
#   partition      --nemesis partition
#   latency-crash-n1     --latency 50 --rate 50, MS_CRASH="n1@5"   (Part 4 Q4)
#   latency-partition    --latency 50 --rate 50 --nemesis partition (Part 4 Q4)
#   slow-n0        SLOW_PUT="n0=0.5" --latency 10 --rate 50
#                  (programs from q3.py on: puts sent by n0 to the other
#                   servers are delayed 0.5 s; see docs/03-*.md)
#
# Run from anywhere: the store/ directory is created in lab2/. Needs
# ../env.sh if Java and gnuplot are not installed system-wide. The
# programs read QR and QW from the environment.

cd "$(dirname "$0")"
[ -f ../env.sh ] && source ../env.sh

program=$1
qr=$2
qw=$3
scenario=$4
repeats=${5:-1}
nodes=${6:-3}
crash=""
slow=""
case $scenario in
    nofaults)      opts="" ;;
    latency)       opts="--latency 50 --rate 50" ;;
    latency-high)  opts="--latency 100 --rate 100" ;;
    crash-n1)      opts=""; crash="n1@5" ;;
    crash-n1-n2)   opts=""; crash="n1@5,n2@5" ;;
    partition)     opts="--nemesis partition" ;;
    latency-crash-n1)  opts="--latency 50 --rate 50"; crash="n1@5" ;;
    latency-partition) opts="--latency 50 --rate 50 --nemesis partition" ;;
    slow-n0)       opts="--latency 10 --rate 50"; slow="n0=0.5" ;;
    *) echo "unknown scenario $scenario" >&2; exit 1 ;;
esac

mkdir -p results
for i in $(seq "$repeats"); do
    QR=$qr QW=$qw MS_CRASH="$crash" SLOW_PUT="$slow" \
        ../kit/run.sh lin-kv "$program" --node-count "$nodes" $opts \
        > results/last-output.txt 2>&1
    run=$(readlink -f store/latest)
    line="$(basename "$program")\tN=$nodes\tQR=$qr\tQW=$qw\t$scenario\t$(../kit/summary.py store/latest | sed 's/  [^ ]*$//')\t${run#$PWD/}"
    echo -e "$line" | tee -a results/results.tsv
done
