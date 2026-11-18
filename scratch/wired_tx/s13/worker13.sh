#!/bin/bash
# worker13.sh <jobfile>: runs the jobs of a file one after the other (one simulation at a time); stop with STOPQ.
# Start at most as many workers as free slots (MANDATE: 3 heavy jobs per owner including sub-agents).
cd /home/ubuntu/svalbard/scratch/wired_tx/s13
export OMP_NUM_THREADS=1
while IFS= read -r j; do
  [ -e STOPQ ] && break
  [ -z "$j" ] && continue
  tag=$(echo "$j" | python3 -c "import sys,json;print(json.loads(sys.stdin.read())['tag'])")
  [ -e resultsC/$tag.json ] && continue
  python3 chain13.py "$j" 2>&1 | tail -1 | cut -c1-500 >> "$1.log"
  rm -f runsC/$tag/data/wave.txt runsC/$tag/phase/wave.txt runsC/$tag/data/*.spice runsC/$tag/phase/*.spice
done < "$1"
echo finished >> "$1.log"
