#!/usr/bin/env bash
# Shared fixed-mount PLL/RX experiment launcher. User arguments stay separate argv.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
variant=${1:?experiment name required}
shift
output_name=transceiver-${variant//_/-}
creation=reuse
extra_mounts=()
reference_mounts=(-v "$ROOT/scratch/transceiver-rf-ac-clock:/clock:ro"
 -v "$ROOT/scratch/transceiver-rf-ideal-lo:/reference:ro"
 -v "$ROOT/scratch/transceiver-divider-chain:/chain:ro")
case "$variant" in
 closed_loop_buffered) baseline=transceiver-closed-loop-gear; command='python3 /screen/pll/closed_loop_buffered_screen.py'; forward=no ;;
 closed_loop_pwl_reference) baseline=transceiver-closed-loop-gear; command='python3 /screen/pll/closed_loop_pwl_reference_screen.py'; forward=no ;;
 vco_supply) baseline=transceiver-vco-split-tuning; command='python3 /screen/pll/vco_supply_screen.py'; forward=no ;;
 closed_loop_follower) baseline=transceiver-closed-loop-follower-prepared; command='python3 /screen/pll/closed_loop_buffered_screen.py --prepared "$@"'; forward=yes ;;
 closed_loop_follower_pwl) baseline=transceiver-closed-loop-follower-pwl-prepared; command='python3 /screen/pll/closed_loop_buffered_screen.py --prepared "$@"'; forward=yes ;;
 latest_rf_loop_extended) baseline=transceiver-latest-rf-loop-extended-prepared; command='python3 /screen/pll/closed_loop_buffered_screen.py --latest "$@"'; forward=yes ;;
 latest_loop_elaboration) baseline=transceiver-latest-rf-loop-prepared; command='python3 /screen/pll/loop_elaboration_screen.py --latest "$@"'; forward=yes ;;
 latest_rf_loop) baseline=transceiver-latest-rf-loop-prepared; command='python3 /screen/pll/closed_loop_buffered_screen.py --latest "$@"'; forward=yes ;;
 loop_elaboration) baseline=transceiver-closed-loop-follower-prepared; command='python3 /screen/pll/loop_elaboration_screen.py "$@"'; forward=yes ;;
 vco_charge_kick_fine) baseline=transceiver-vco-split-tuning; command='python3 /screen/pll/vco_charge_kick.py --fine'; forward=no; creation=fresh ;;
 vco_internal_kick) output_name=transceiver-vco-internal-kick-v2; baseline=transceiver-vco-split-tuning; command='python3 /screen/pll/vco_internal_kick.py --fine'; forward=no; creation=fresh ;;
 vco_channel_kick) baseline=transceiver-vco-split-tuning; command='python3 /screen/pll/vco_channel_kick.py --fine'; forward=no; creation=fresh ;;
 pfd_pump_breakpoint) baseline=transceiver-closed-loop-gear; command='python3 /screen/pll/pfd_pump_breakpoint_screen.py'; forward=no; creation=reuse; extra_mounts=(-v "$ROOT/scratch/transceiver-closed-loop-gear:/pulse:ro" -v "$ROOT/scratch/transceiver-closed-loop-pwl-reference:/pwl:ro") ;;
 pfd_reset_phase) baseline=transceiver-pfd-pump-breakpoint; command='python3 /screen/pll/pfd_reset_phase_screen.py'; forward=no; creation=reuse; extra_mounts=(-v "$ROOT/scratch/transceiver-closed-loop-gear:/pulse:ro" -v "$ROOT/scratch/transceiver-closed-loop-pwl-reference:/pwl:ro") ;;
 pfd_buffered_reference) baseline=transceiver-pfd-pump-breakpoint; command='python3 /screen/pll/pfd_buffered_reference_screen.py'; forward=no; creation=reuse; extra_mounts=(-v "$ROOT/scratch/transceiver-closed-loop-gear:/pulse:ro" -v "$ROOT/scratch/transceiver-closed-loop-pwl-reference:/pwl:ro") ;;
 pfd_matched_waveform) baseline=transceiver-pfd-pump-breakpoint; command='python3 /screen/pll/pfd_matched_waveform_screen.py'; forward=no; creation=reuse; extra_mounts=(-v "$ROOT/scratch/transceiver-closed-loop-gear:/pulse:ro" -v "$ROOT/scratch/transceiver-closed-loop-pwl-reference:/pwl:ro") ;;
 reference_breakpoint) baseline=transceiver-closed-loop-gear; command='python3 /screen/pll/reference_breakpoint_screen.py'; forward=no; creation=reuse; extra_mounts=(-v "$ROOT/scratch/transceiver-closed-loop-gear:/pulse:ro" -v "$ROOT/scratch/transceiver-closed-loop-pwl-reference:/pwl:ro") ;;
 rx_adc_event_offsets|rx_adc_separated_events)
  baseline=transceiver-rx-adc-loading/loaded; creation=fresh; forward=yes
  command='python3 /screen/integration/rx_adc_event_offsets.py "$@"'
  reference_mounts=()
  variants=transceiver-rx-adc-event-offsets-prepared
  if [[ "$variant" == rx_adc_separated_events ]]; then
   output_name=transceiver-rx-adc-separated-events-v2
   variants=transceiver-rx-adc-separated-events-prepared-v2
  fi
  extra_mounts=(-v "$ROOT/scratch/transceiver-rx-adc-connected-prepared:/prepared:ro"
   -v "$ROOT/scratch/$variants:/variants:ro")
  if [[ "${1:-}" == --preflight ]]; then output_name+="-preflight"; fi
  if [[ "${1:-}" == --preflight-v2 ]]; then output_name+="-preflight-v2"; set -- --preflight; fi ;;
 *) exit 2 ;;
esac
OUT="$ROOT/scratch/$output_name"
if [[ "$creation" == fresh ]]; then mkdir "$OUT"; else mkdir -p "$OUT"; fi
forwarded=()
if [[ "$forward" == yes ]]; then forwarded=(runner "$@"); fi
docker run --rm --platform linux/arm64 --network none --cpus 2 --memory 4g --entrypoint /bin/bash \
 -v "$ROOT/projects/programmable_transceiver_platform/analog:/screen:ro" \
 -v "$ROOT/ip/blocks/analog/wireline_serdes/pll:/vco:ro" \
 -v "$ROOT/ip/blocks/analog/wifi_80211b:/wifi:ro" \
 "${reference_mounts[@]}" \
 -v "$ROOT/scratch/$baseline:/baseline:ro" \
 "${extra_mounts[@]}" \
 -v "$OUT:/work" --workdir /work \
 sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 \
 -lc "$command" "${forwarded[@]}"
