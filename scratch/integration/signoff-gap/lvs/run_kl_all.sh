#!/bin/bash
cd "$(dirname "$0")"
xargs -a "${1:-kljobs.txt}" -P ${3:-2} -L 1 python3 kl_lvs.py > "${2:-run_kl_all.log}" 2>&1
echo DONE >> "${2:-run_kl_all.log}"
