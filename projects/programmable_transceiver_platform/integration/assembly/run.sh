#!/bin/bash
# Chip assembly of one chip, stage by stage, one heavy job at a time:   run.sh <rf|wired> [stage ...]
#   stages: abstract floorplan place lint route stream report drc lvs check fill precheck      (default: abstract .. report)
# Run directory scratch/integration/assembly-<chip> (ASM_RUN overrides); only the latest run is kept (each stage
# overwrites its outputs). The sign-off flows (integration/signoff, SIGNOFF_CHIP=<chip>) read chip/pt_chip_top.gds from it.
set -e
A=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$A/../../../.." && pwd)
CHIP=${1:?rf|wired}; shift
RUN=${ASM_RUN:-$ROOT/scratch/integration/assembly-$CHIP}; mkdir -p "$RUN/route"
STAGES=${*:-abstract floorplan place route stream report}
export OMP_NUM_THREADS=1 SIGNOFF_CHIP=$CHIP SIGNOFF_RUN=$RUN
for S in $STAGES; do
  T0=$(date +%s); echo "== $CHIP $S"
  case $S in
    abstract)  "$A/tool.sh" "$CHIP" -c 2 python3 /asm/kl_abstract.py > "$RUN/abstract.log" 2>&1; tail -1 "$RUN/abstract.log" | cut -c1-400 ;;
    floorplan) nice -n 10 python3 "$A/floorplan.py" "$CHIP" | grep -v '^pass2' | cut -c1-600 ;;
    place)     "$A/tool.sh" "$CHIP" -c 2 python3 /asm/kl_place.py > "$RUN/place.log" 2>&1; head -2 "$RUN/place.log" | cut -c1-600 ;;
    lint)      python3 "$A/place_lint.py" "$RUN" ;;      # pre-route placement lint (also the first step of route)
    route)     python3 "$A/place_lint.py" "$RUN" > "$RUN/place_lint.log" 2>&1 || { tail -12 "$RUN/place_lint.log"; echo "place lint failed: no route (PLACE_LINT=0 overrides)"; [ "${PLACE_LINT:-1}" = 0 ] || exit 1; }
               rm -f "$RUN"/route/{routed.def,groute.def,drt.rpt,congestion.rpt,unreachable.txt}; touch "$RUN/route/unreachable.txt"
               for k in 1 2 3 4 5 6; do      # pin-access passes: every pin without an access point is taken off its net (reported)
                 "$A/tool.sh" "$CHIP" -c 4 bash -c "SIG_M1=${SIG_M1:-0} PA_ONLY=1 openroad -exit /asm/route.tcl" > "$RUN/route/pa$k.log" 2>&1 || true
                 grep -q "PA CLEAN" "$RUN/route/pa$k.log" && break
                 N0=$(wc -l < "$RUN/route/unreachable.txt")
                 sed -n 's/.*No access point for \([^ ]*\) .*/\1/p' "$RUN/route/pa$k.log" >> "$RUN/route/unreachable.txt"
                 [ "$(wc -l < "$RUN/route/unreachable.txt")" -gt "$N0" ] || { echo "pin access fails without a named pin"; break; }
               done
               echo "   unreachable pins: $(wc -l < "$RUN/route/unreachable.txt")"
               "$A/tool.sh" "$CHIP" -c 4 bash -c "SIG_M1=${SIG_M1:-0} NDR=${NDR:-1} HOOK_W=${HOOK_W:-0.56} DRT_ITERS=${DRT_ITERS:-64} openroad -exit /asm/route.tcl" > "$RUN/route/route.log" 2>&1 || true
               grep -E "GRT-0228|ERROR|ROUTE DONE|Number of violations|ANTENNA PASS" "$RUN/route/route.log" | tail -3
               [ -s "$RUN/route/routed.def" ] || { echo "route wrote no routed.def: stop"; exit 1; } ;;
    stream)    "$A/tool.sh" "$CHIP" -c 2 python3 /asm/kl_stream.py > "$RUN/stream.log" 2>&1; tail -1 "$RUN/stream.log" | cut -c1-400 ;;
    report)    python3 "$A/report.py" "$CHIP" > "$RUN/report.log"; head -30 "$RUN/report.log" ;;
    drc)       "$A/../signoff/drc/run_all.sh" chip/pt_chip_top.gds pt_chip_top chip live 2 ;;
    lvs)       python3 "$A/../signoff/lvs/gen_netlist.py" "$RUN/lvs/pt_chip_top.ref.spice" --chip "$CHIP" 2>/dev/null || { mkdir -p "$RUN/lvs"; python3 "$A/../signoff/lvs/gen_netlist.py" "$RUN/lvs/pt_chip_top.ref.spice" --chip "$CHIP"; }
               "$A/../signoff/kl.sh" -c 2 lvs/top_lvs.py -rd gds=chip/pt_chip_top.gds -rd top=pt_chip_top -rd ref=lvs/pt_chip_top.ref.spice \
                 -rd out=lvs/chip -rd manifest=chip/manifest.json -rd flatten=retained_provider_ring,pt_pdn,pt_direct_land,pt_antdiode,pt_top_wiring,pt_island_bar,VIA_* > "$RUN/lvs/lvs.log" 2>&1 || true
               tail -5 "$RUN/lvs/lvs.log"
               # the macro's VDD/VSS stripes are not conn pins, so LVS by name cannot see them (PDS-25): place's check
               grep -o "macro supply [A-Z ]*OPEN\|macro supply OK" "$RUN/place.log" || echo "macro supply: NOT CHECKED (rerun place)"
               PS=0; "$A/tool.sh" "$CHIP" -c 1 python3 /asm/check_padsup.py > "$RUN/lvs/padsup.log" 2>&1 || PS=$?; tail -1 "$RUN/lvs/padsup.log"
               CC=0; python3 "$A/check_conn.py" "$CHIP" || CC=$?      # the connectivity gate fails the lvs stage (KH-1..3)
               [ $PS -eq 0 ] && [ $CC -eq 0 ] || exit 1 ;;      # pad supply gate (check_padsup.py) fails it too
    check)     python3 "$A/check_conn.py" "$CHIP" ;;      # connectivity gate (KH-1..3): unwired macro / pad core pins, non-port single-pin nets, unbound LVS instances
    fill)      "$A/../signoff/fill/run_fill.sh" rf 2 chip/pt_chip_top.gds      # "rf" = the fill keep-out set (common.NO_OVER blocks), not the chip: used for both chips
               "$A/../signoff/drc/run_drc.sh" fill/rf_filled.gds pt_chip_top density chip_filled_density live 2 ;;
    precheck)  rm -rf "$RUN/precheck"      # the shuttle's own precheck on the filled chip (about 3 h, 4 threads)
               env -u OMP_NUM_THREADS "$A/../signoff/precheck/run_precheck.sh" "$RUN/fill/rf_filled.gds" pt_chip_top "$RUN/precheck" 4 > "$RUN/precheck.out" 2>&1 || true
               python3 "$A/../signoff/precheck/summarise.py" "$RUN/precheck" | tail -25 ;;
    *) echo "unknown stage $S"; exit 2 ;;
  esac
  echo "   ($(( $(date +%s)-T0 )) s)"
done
