#!/usr/bin/env bash
# Freeze stage 1 (control and digital): harden rtl/pt_digital_macro.sv with LibreLane and
# produce the signoff evidence evidence/digital-hardening-evidence.json.
#
#   run_digital_hardening.sh [stage ...]      default: pnr export sta gls pads report
#     pnr     LibreLane Classic flow (synthesis .. Magic/KLayout DRC, Netgen LVS, antenna)
#     export  GDS re-export with the analog image's Magic 8.3.678 (block-deliverables GDS rule),
#             KLayout GF180 DRC (sak-drc.sh -k) and antenna deck on that exported GDS
#     sta     per-clock / per-corner signoff STA on the routed design with extracted SPEF
#             (OpenSTA), fmax bisection per clock, host-link skew windows
#     gls     gate-level simulation of the post-route netlist: regfile command stream (lockstep
#             against the RTL macro), reset-safe outputs (RESET_N and POR), SPI status reads
#     pads    provider gf180mcu_fd_io Liberty screen for the host link (toggle-rate estimate)
#     report  evidence JSON
# Containers: --network none, bounded CPU/memory, OMP_NUM_THREADS=1, at most one at a time.
# Chip (required): CHIP=rf|wired selects the configuration (digital_hardening/<chip>/config.json merged over
# digital_hardening/config.json: PT_CHIP parameter and outline) and the chip's CP4-1 clamp list.
# Output: scratch/digital_hardening-<chip>/ (override with OUT=...).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
PROJ="$ROOT/projects/programmable_transceiver_platform"
CHIP="${CHIP:?CHIP=rf|wired}"
OUT="${OUT:-$ROOT/scratch/digital_hardening-$CHIP}"
DIGITAL_IMAGE="${SVALBARD_DIGITAL_IMAGE:-svalbard/librelane-gf180-guarded:2026.11}"
ANALOG_IMAGE="${SVALBARD_ANALOG_IMAGE:-sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305}"
CPUS="${CPUS:-6}"
MEM="${MEM:-16g}"
TAG="${TAG:-FREEZE1}"
stages=("$@"); [ ${#stages[@]} -eq 0 ] && stages=(pnr export sta gls pads report)
mkdir -p "$OUT"
if [ -z "${SVALBARD_DIGITAL_IMAGE:-}" ]; then
  docker build --network none -t "$DIGITAL_IMAGE" \
    -f "$PROJ/verification/digital_hardening/Dockerfile" \
    "$PROJ/verification/digital_hardening" > "$OUT/toolchain-build.log" 2>&1
fi
docker image inspect "$DIGITAL_IMAGE" --format '{{.Id}} {{.Architecture}}' > "$OUT/digital-image.txt"
docker image inspect "$ANALOG_IMAGE" --format '{{.Id}} {{.Architecture}}' > "$OUT/analog-image.txt"
RUN="$OUT/design/runs/$TAG"
# snapshot of the step script for this output directory (a running flow does not follow later edits of the tree)
[ -f "$OUT/repair_design_pt.tcl" ] || cp "$PROJ/verification/digital_hardening/repair_design_pt.tcl" "$OUT/repair_design_pt.tcl"

# The flow's repair_design step script is replaced by digital_hardening/repair_design_pt.tcl (gain buffering
# before the final global placement, see its header and config.json meta.substituting_steps).
dk() { # dk <image> <cpus> <mem> <command>
  docker run --rm --name "dig-$CHIP-$(date +%s%N | cut -c1-13)" --network none --cpus "$2" --memory "$3" --memory-swap "$3" --pids-limit 4096 \
    --user "$(id -u):$(id -g)" -e HOME=/out/home -e TMPDIR=/out/tmp -e OMP_NUM_THREADS=1 -e PT_CHIP="$CHIP" \
    -v "$PROJ:/src:ro" -v "$OUT:/out" \
    -v "$OUT/repair_design_pt.tcl:/usr/local/lib/python3.12/dist-packages/librelane/scripts/openroad/repair_design.tcl:ro" \
    --entrypoint /bin/bash "$1" -lc "$4"
}

for stage in "${stages[@]}"; do
case "$stage" in
pnr)
  rm -rf "$OUT/design"; mkdir -p "$OUT/design/rtl" "$OUT/home" "$OUT/tmp"
  cp "$PROJ/verification/digital_hardening/repair_design_pt.tcl" "$OUT/repair_design_pt.tcl"
  sha256sum "$OUT/repair_design_pt.tcl" > "$OUT/repair_design_pt.sha256"
  cp "$PROJ"/rtl/*.sv "$PROJ"/rtl/*.svh "$PROJ"/rtl/*.vh "$OUT/design/rtl/"
  cp "$PROJ/integration/pt_digital_macro.sdc" "$PROJ/verification/digital_hardening/config.json" "$PROJ/verification/digital_hardening/pin_order.cfg" \
     "$PROJ/integration/pt_cts_h2d.tcl" "$OUT/design/"
  # FIRM placements (host-link blocks, clock roots) for this chip's outline
  python3 "$PROJ/verification/digital_hardening/hio_shift.py" "$CHIP" "$OUT/design/hio_placement.cfg"
  # In-window characterized Liberty (libchar.py): synthesis, placement, CTS and resizer optimize setup
  # against ss_032C_3v15 (and hold against ff) directly, not a derated tt library.
  mkdir -p "$OUT/design/lib"; cp "$PROJ"/verification/digital_hardening/liberty/*.lib "$OUT/design/lib/"
  # Optional overrides (recorded in the evidence), e.g. LL_OVERRIDE='{"RT_MAX_LAYER": "Metal5"}'
  # chip configuration (split, D10): PT_CHIP and the outline of digital_hardening/<chip>/config.json
  python3 -c 'import json,sys;p=sys.argv[1];c=json.load(open(p));o=json.load(open(sys.argv[2]));o.pop("about",None);c.update(o);json.dump(c,open(p,"w"),indent=2)' \
    "$OUT/design/config.json" "$PROJ/verification/digital_hardening/$CHIP/config.json"
  if [ -n "${LL_OVERRIDE:-}" ]; then
    python3 -c 'import json,sys;p=sys.argv[1];c=json.load(open(p));c.update(json.loads(sys.argv[2]));json.dump(c,open(p,"w"),indent=2)' \
      "$OUT/design/config.json" "$LL_OVERRIDE"
    echo "$LL_OVERRIDE" > "$OUT/config-override.json"
  fi
  pnr_rc=0
  # Gain-based fanout buffering in repair_design (OpenROAD -buffer_gain; the LibreLane step reads
  # DESIGN_REPAIR_BUFFER_GAIN from the environment): builds balanced repeater trees instead of the
  # serial buf_1/buf_2 chains the slew-driven repair left on high-fanout control nets (TC1-TC4).
  BUFFER_GAIN="${PT_REPAIR_BUFFER_GAIN:-4.0}"; echo "$BUFFER_GAIN" > "$OUT/repair-buffer-gain.txt"
  dk "$DIGITAL_IMAGE" "$CPUS" "$MEM" "set -e; cd /out/design; export DESIGN_REPAIR_BUFFER_GAIN=$BUFFER_GAIN PT_GAIN_BEFORE_GPL=1 ${PT_SCLK_PERIOD:+PT_SCLK_PERIOD=$PT_SCLK_PERIOD}; librelane --version > /out/librelane-version.txt 2>&1 || true
    if [ -f /opt/svalbard/toolchain.json ]; then cp /opt/svalbard/toolchain.json /out/toolchain.json; fi
    librelane --manual-pdk --pdk-root /pdk -p gf180mcuD -s gf180mcu_fd_sc_mcu7t5v0 -j $CPUS --run-tag $TAG \
      --hide-progress-bar config.json > /out/librelane.log 2>&1" || pnr_rc=$?
  echo "librelane_rc=$pnr_rc" >> "$OUT/librelane.log"
  tail -n 30 "$OUT/librelane.log"
  # Gates on the two repair passes, whatever the flow's own result: the replaced step script really ran (pass 1
  # then pass 2), every dont-touch name resolved, and no clamp pin has anything before its isolation AND2 (CP4-1).
  gate=0
  p1=$(ls "$RUN"/*-openroad-repairdesignpostgpl/openroad-repairdesignpostgpl.log 2>/dev/null | head -n 1)
  p2=$(ls "$RUN"/*-openroad-repairdesignpostgpl-1/openroad-repairdesignpostgpl-1.log 2>/dev/null | head -n 1)
  { [ -n "$p1" ] && grep -q "pt: repair_design pass 1" "$p1"; } || { echo "GATE: repair pass 1 missing" >&2; gate=1; }
  { [ -n "$p2" ] && grep -q "pt: repair_design pass 2" "$p2"; } || { echo "GATE: repair pass 2 missing" >&2; gate=1; }
  if grep -l "STA-0101" "$RUN"/*-openroad-repairdesign*/*.log "$RUN"/*-openroad-resizertiming*/*.log 2>/dev/null | head -n 1 | grep -q .; then
    echo "GATE: a dont-touch name did not resolve (STA-0101)" >&2; gate=1; fi
  for nl in "$RUN"/*-openroad-repairdesignpostgpl-1/*.nl.v "$RUN"/*-openroad-resizertimingpostcts/*.nl.v "$RUN"/*-openroad-resizertimingpostgrt/*.nl.v "$RUN"/final/nl/*.nl.v; do
    [ -f "$nl" ] || continue
    python3 "$PROJ/verification/digital_hardening/clamp_check.py" "$nl" --chip "$CHIP" > "$OUT/clamp_check.$(basename "$(dirname "$nl")").log" 2>&1 || { echo "GATE: clamp_check failed on $nl" >&2; gate=1; }
  done
  echo "gate_rc=$gate" >> "$OUT/librelane.log"
  if [ "$gate" -ne 0 ]; then exit 3; fi
  if [ "$pnr_rc" -ne 0 ]; then exit "$pnr_rc"; fi
  ;;
export)
  rm -rf "$OUT/export"; mkdir -p "$OUT/export"
  cp "$RUN/final/def/pt_digital_macro.def" "$OUT/export/"
  cp "$PROJ/verification/digital_hardening/magic_export.tcl" "$PROJ/verification/digital_hardening/export.sh" "$OUT/export/"
  docker run --rm --network none --cpus 3 --memory 8g -e OMP_NUM_THREADS=1 --user "$(id -u):$(id -g)" -e HOME=/work \
    --entrypoint /bin/bash -v "$OUT/export:/work" -w /work "$ANALOG_IMAGE" /work/export.sh > "$OUT/export/stage.log" 2>&1 || true
  tail -n 5 "$OUT/export/stage.log" || true
  # XOR of the 8.3.678 GDS against LibreLane's 8.3.623 GDS (canary KLayout).
  dk "$DIGITAL_IMAGE" 2 6g "cd /out/export && klayout -b -r /src/verification/digital_hardening/xor.py \
      -rd a=/out/export/pt_digital_macro.gds -rd b=/out/design/runs/$TAG/final/gds/pt_digital_macro.gds \
      -rd out=/out/export/xor.json > /out/export/xor.log 2>&1" || true
  ;;
sta)
  rm -rf "$OUT/sta"; mkdir -p "$OUT/sta"
  dk "$DIGITAL_IMAGE" 4 12g "cd /out/sta && python3 /src/verification/digital_hardening/sta_signoff.py \
      --run /out/design/runs/$TAG --sdc /src/integration/pt_digital_macro.sdc --out /out/sta > /out/sta/sta.log 2>&1" || true
  tail -n 20 "$OUT/sta/sta.log"
  ;;
gls)
  rm -rf "$OUT/gls"; mkdir -p "$OUT/gls"
  python3 "$PROJ/verification/digital_hardening/gls_commands.py" --out "$OUT/gls"
  dk "$DIGITAL_IMAGE" 2 8g "cd /out/gls && sh /src/verification/digital_hardening/gls.sh /out/design/runs/$TAG/final/pnl/pt_digital_macro.pnl.v > /out/gls/gls.log 2>&1" || true
  python3 "$PROJ/verification/digital_hardening/gls_check.py" --out "$OUT/gls" | tail -n 30
  ;;
pads)
  rm -rf "$OUT/pads"; mkdir -p "$OUT/pads"
  dk "$DIGITAL_IMAGE" 1 2g "cd /out/pads && python3 /src/verification/digital_hardening/hostio_pad_screen.py --out /out/pads/hostio-pad-screen.json > /out/pads/pads.log 2>&1" || true
  tail -n 20 "$OUT/pads/pads.log"
  ;;
report)
  python3 "$PROJ/verification/digital_hardening/report.py" --out "$OUT" --tag "$TAG" \
    --evidence "$PROJ/evidence/digital-hardening-evidence.json"
  ;;
*) echo "unknown stage $stage" >&2; exit 2 ;;
esac
done
