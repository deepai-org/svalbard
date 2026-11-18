#!/bin/bash
# usage: runq2.sh JOBFILE ; lines "NEED|command": waits (outside any slot) until file NEED exists (NEED may be -), then one ../../slot.sh call
cd "$(dirname "$0")"; export OMP_NUM_THREADS=1
while IFS='|' read -r need line; do
  [ -z "$line" ] && continue
  if [ "$need" != "-" ]; then until [ -f "$need" ] || [ -f STOP ]; do sleep 20; done; fi
  [ -f STOP ] && break
  echo "## $(date -u +%H:%M:%S) $line" >> "$1.log"
  ../../slot.sh bash -c "$line" >> "$1.log" 2>&1
done < "$1"
date -u > "$1.done"
