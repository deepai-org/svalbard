#!/bin/bash
# KLayout DRC with the PDK deck on a GDS in the run directory.
#   run_drc.sh <gds, relative to the run dir> <topcell> <decks> <tag> [live|proj] [workers=1]
# decks as the precheck passes them: main = "all,-antenna,-density,-cup", "antenna", "density".
# live = shuttle PDK 792ef67 deck, proj = project PDK f6eeac7 deck; both run on the project's KLayout 0.30.9.
# Result: <run>/drc/<tag>/counts.json (per rule), run.log, report.lyrdb.gz (if under 30 MB). One heavy job per call.
. "$(dirname "$0")/../env.sh"
GDS=$1; TOPC=$2; DECKS=$3; TAG=$4; WHICH=${5:-live}; W=${6:-1}
[ "$W" -le 4 ] || { echo "workers > 4 not allowed"; exit 2; }
[ "$WHICH" = live ] && DECK=$PDK_LIVE/drc || DECK=$PDK_PROJ/drc
O=$RUN/drc/$TAG; mkdir -p "$O"; rm -f "$O"/report.lyrdb*
T0=$(date +%s)
docker run --rm --network none --cpus "$W" --memory 40g --user "$(id -u):$(id -g)" -e HOME=/tmp -e OMP_NUM_THREADS=1 \
  -v "$DECK":/deck:ro -v "$RUN":/run:ro -v "$O":/out --entrypoint /bin/bash "$KL_IMAGE" -c \
  "export PATH=\$PATH:/foss/tools/klayout LD_LIBRARY_PATH=/foss/tools/klayout; cd /tmp; klayout -b -zz -r /deck/gf180mcu.drc -rd input=/run/$GDS -rd topcell=$TOPC -rd report=/out/report.lyrdb -rd decks='$DECKS' -rd variant=gf180mcuD -rd workers=$W -rd threads=$W" > "$O/run.log" 2>&1
RC=$?; T1=$(date +%s)
python3 -I "$SO/drc/count_lyrdb.py" "$O/report.lyrdb" > "$O/counts.json" 2>/dev/null || echo '{"total": null, "error": "no report"}' > "$O/counts.json"
grep -E "ratio: " "$O/run.log" | sed 's/.*: \([A-Za-z0-9]* ratio\)/\1/' > "$O/ratios.txt"
echo "gds=$GDS sha256=$(sha256sum "$RUN/$GDS" | cut -c1-64) decks=$DECKS deck=$WHICH workers=$W exit=$RC seconds=$((T1-T0))" > "$O/meta.txt"
if [ -f "$O/report.lyrdb" ]; then gzip -f "$O/report.lyrdb"; [ "$(stat -c %s "$O/report.lyrdb.gz")" -gt 30000000 ] && rm -f "$O/report.lyrdb.gz"; fi
echo "$TAG: exit $RC, $((T1-T0)) s, $(tr '\n' ' ' < "$O/counts.json" | cut -c1-600)"
