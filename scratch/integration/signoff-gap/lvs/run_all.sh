#!/bin/bash
# rb_lvs over jobs.txt, 5 at a time. usage: run_all.sh [jobs file]
cd "$(dirname "$0")"
xargs -a "${1:-jobs.txt}" -P 5 -L 1 python3 rb_lvs.py > "${2:-run_all.log}" 2>&1
echo DONE >> "${2:-run_all.log}"
