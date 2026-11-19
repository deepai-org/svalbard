#!/bin/bash
# Die-fit of one chip, strictly one step after another, one thread:  chip.sh <rf|wired> [TRIES=6]
# ledger (first pass) -> decap (5.4 nF plan) -> ledger (tiles booked) -> packer S / T / LB -> overheads -> summary
cd "$(dirname "$0")" || exit 2; export OMP_NUM_THREADS=1 CHIP=$1; T=${2:-6}
mkdir -p run/$1
python3 ledger.py > /dev/null && python3 decap.py > /dev/null && python3 ledger.py > /dev/null || exit 1
for s in S T LB; do t=$(echo $s | tr A-Z a-z); SCEN=$s TRIES=$T TAG=$t nice -n 10 python3 fit.py > run/$1/$t.log 2>&1 || { echo "fit $s failed"; exit 1; }; done
python3 overheads.py s t lb > run/$1/overheads.log 2>&1 || exit 1
python3 summarize.py
