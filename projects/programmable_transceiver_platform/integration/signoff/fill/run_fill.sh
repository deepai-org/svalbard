#!/bin/bash
# Full-die dummy fill with the shuttle PDK's fill scripts (792ef67: COMP, Poly2, Metal1-5), with a keep-out set.
#   run_fill.sh <kset: none|must|rf|analog|allblocks> [threads=2] [input gds rel. to run dir = skel/pt_chip_skel.gds]
# Output <run>/fill/<kset>_filled.gds, <kset>_fill.log (runtime, peak memory). One heavy job per call.
. "$(dirname "$0")/../env.sh"
K=$1; THR=${2:-2}; IN=${3:-skel/pt_chip_skel.gds}
[ "$THR" -le 4 ] || { echo "threads > 4 not allowed"; exit 2; }
mkdir -p "$RUN/fill"
SRC=$IN
if [ "$K" != none ]; then "$SO/kl.sh" fill/keepout.py -rd inp=$IN -rd out=fill/${K}_ko.gds -rd kset=$K || exit 1; SRC=fill/${K}_ko.gds; fi
T0=$(date +%s)
docker run --rm --network none --cpus "$THR" --memory 40g --user "$(id -u):$(id -g)" -e HOME=/tmp -e OMP_NUM_THREADS=1 \
  -v "$RUN":/run -v "$SO":/so:ro -v "$PDK_LIVE/scripts":/pdkscripts:ro --entrypoint /bin/bash "$KL_IMAGE" -c \
  "export PATH=\$PATH:/foss/tools/klayout LD_LIBRARY_PATH=/foss/tools/klayout; cd /tmp; /usr/bin/time -v klayout -b -zz -r /so/fill/fill_wrap.rb -rd input=/run/$SRC -rd output=/run/fill/${K}_filled.gds -rd thr=$THR -rd pdkscripts=/pdkscripts" > "$RUN/fill/${K}_fill.log" 2>&1
RC=$?; T1=$(date +%s)
echo "exit=$RC seconds=$((T1-T0)) threads=$THR input=$SRC" >> "$RUN/fill/${K}_fill.log"
[ "$K" != none ] && rm -f "$RUN/fill/${K}_ko.gds"
grep -E "Maximum resident|exit=" "$RUN/fill/${K}_fill.log"; ls -la "$RUN/fill/${K}_filled.gds"
