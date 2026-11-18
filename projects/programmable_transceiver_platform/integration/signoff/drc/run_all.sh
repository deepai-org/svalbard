#!/bin/bash
# Full-chip KLayout DRC with the three deck selections the shuttle precheck runs, one after another (one heavy job):
#   main "all,-antenna,-density,-cup", antenna, density.  On the GDS as it is on disk.
#   run_all.sh <gds rel. to run dir> <topcell> <tag> [live|proj] [workers=1]
# Results under <run>/drc/<tag>_{main,antenna,density}/ (counts.json, by_owner.json, meta.txt).
. "$(dirname "$0")/../env.sh"
GDS=$1; TOPC=$2; TAG=$3; WHICH=${4:-live}; W=${5:-1}
for D in density antenna main; do
  case $D in main) DK="all,-antenna,-density,-cup";; *) DK=$D;; esac
  "$SO/drc/run_drc.sh" "$GDS" "$TOPC" "$DK" "${TAG}_$D" "$WHICH" "$W"
  [ -f "$RUN/drc/${TAG}_$D/report.lyrdb.gz" ] && N=25 python3 "$SO/drc/locate.py" "$RUN/drc/${TAG}_$D/report.lyrdb.gz" > "$RUN/drc/${TAG}_$D/by_owner.txt"
done
