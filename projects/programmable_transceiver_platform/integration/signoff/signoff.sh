#!/bin/bash
# Signoff of one assembled chip, one command:   signoff.sh <rf|wired> <ASM_RUN dir> [--all] [--collect-only]
#                                                [--update-baseline [--provisional] --reason "..."]
# Runs / collects every check (cheap first, stops at the first fail unless --all), writes <run>/signoff/signoff.json and
# a table, compares with baseline/<chip>.json (git). Exit 0 only if every check passes with no regression. See signoff.py.
export OMP_NUM_THREADS=1
exec python3 "$(cd "$(dirname "$0")" && pwd)/signoff.py" "$@"
