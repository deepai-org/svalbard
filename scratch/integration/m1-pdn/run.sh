#!/bin/bash
# Power-delivery model regression and results of one chip, one job at a time:  run.sh rf|wired
# sanity.py (solver vs hand / ngspice, chip-independent) -> e0 (builder vs hand, negative control) -> e7 static IR + bonds
# -> e8 decap plan + negative controls -> e9 victims (single-phase and two-phase macro) -> e11 island impedance (+ RQ-3a on rf)
cd "$(dirname "$0")" || exit 2; export OMP_NUM_THREADS=1; c=${1:?rf|wired}; mkdir -p out/$c
python3 sanity.py > out/sanity.txt || exit 1
python3 e0_sanity_model.py chip=$c > out/$c/e0.txt || exit 1
python3 e7_static.py chip=$c > out/$c/e7_static_base.txt
python3 e8_decap.py chip=$c > out/$c/e8_decap.txt
python3 e9_victims.py chip=$c > out/$c/e9_victims_base.txt
python3 e9_victims.py chip=$c res=0.15 tag=twophase > out/$c/e9_victims_twophase.txt
python3 e11_islands.py chip=$c > out/$c/e11_islands.txt
grep -h -E "^E0|^E7|^E8|^RQ-3a|negative control" out/$c/*.txt; tail -1 out/sanity.txt
