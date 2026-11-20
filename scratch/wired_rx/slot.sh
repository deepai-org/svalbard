#!/bin/bash
# Wired RX simulation slots (LOAD RULE: at most 4 simulations at once (coordinator 2026-11-20) for the wired RX owner INCLUDING sub-agents).
# usage: slot.sh <command...>   - waits for one of 3 slots, runs the command holding it, releases it on exit.
# EVERY command that starts ngspice (any length) goes through this.  One command = one simulation at a time (serial inside).
# FIFO since 07:40 UTC 2026-11-14: waiters take a ticket; only the oldest live ticket may take a free slot.
# Keep each wrapped command to ONE job (minutes, not hours) so that others get turns: wrap per job, not per queue.
D=/home/ubuntu/svalbard/scratch/wired_rx/slots
export OMP_NUM_THREADS=1
T="$D/tickets/$(date +%s%N).$$"
echo "$*" > "$T"
trap 'rm -f "$T"' EXIT
while true; do
  first=""
  for f in $(ls "$D/tickets" | sort); do
    p=${f##*.}
    if kill -0 "$p" 2>/dev/null; then first="$f"; break; else rm -f "$D/tickets/$f"; fi
  done
  if [ "$first" = "$(basename "$T")" ]; then
    for i in 1 2 3 4; do
      exec 9>"$D/slot$i.lock"
      if flock -n 9; then
        rm -f "$T"
        echo "$$ $(date -u +%H:%M:%S) $*" > "$D/slot$i.who"
        "$@"; rc=$?
        : > "$D/slot$i.who"
        exit $rc
      fi
      exec 9>&-
    done
  fi
  sleep 10
done
