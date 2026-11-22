#!/bin/bash
cd /home/ubuntu/svalbard/scratch/wired_rx/r12/cap/lde
while read -r a; do ../../../slot.sh python3 ldecell.py $a >> lde.log 2>&1; done <<'L'
r7f typical 625e6 1.0 10
r7f ff 625e6 1.0 10
r7f ss 810e6 1.0 10
r7fpess ss 810e6 1.0 10
r7f ff 480e6 0.85 10
r7f ff 810e6 0.75 10
r7fpess ss 480e6 1.0 10
r7f typical 625e6 2.0 20
L
echo ALL >> lde.log
