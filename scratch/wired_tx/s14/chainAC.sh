#!/bin/bash
# runs qA (calibration proof, drawn netlist) then qC (attribution rows) in one slot
cd /home/ubuntu/svalbard/scratch/wired_tx/s14
while pgrep -f "q14.py qA.jobs" > /dev/null; do sleep 60; done
[ -e STOPQ ] || python3 q14.py qC.jobs
