#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
output_name=${1:?output directory name required}
runner_name=${2:?relative Python checker path required}
[[ "$output_name" =~ ^[a-z0-9-]+$ && "$runner_name" =~ ^[a-zA-Z0-9_]+(/[a-zA-Z0-9_]+)*\.py$ ]] || exit 2
OUT="$ROOT/scratch/$output_name"
case "${4:-reuse}" in
 reuse) mkdir -p "$OUT" ;;
 fresh) mkdir "$OUT" ;;
 *) exit 2 ;;
esac
extra_mounts=()
leading_mounts=()
container_name=()
cpu_count=2
runner_arguments=""
input_target=baseline
case "${3:-basic}" in
 basic) ;;
 wifi_src) leading_mounts=(-v "$ROOT/ip/blocks/analog/wifi_80211b:/src:ro") ;;
 paired_inputs)
  [[ "${5:-}" =~ ^[a-z0-9-]+$ && "${6:-}" =~ ^[a-z0-9-]+$ ]] || exit 2
  input_target=base ;;
 prepared_replay)
  [[ "${5:-}" =~ ^[a-z0-9-]+$ ]] || exit 2
  extra_mounts=(-v "$ROOT/ip/blocks/analog/wifi_80211b:/wifi:ro")
  container_name=(--name "$output_name")
  cpu_count=1
  runner_arguments=" baseline"
  input_target=prepared ;;
 wifi) extra_mounts=(-v "$ROOT/ip/blocks/analog/wifi_80211b:/wifi:ro") ;;
 rf_references|rf_chain)
  if [[ "$3" == rf_chain ]]; then input_target=chain; fi
  extra_mounts=(-v "$ROOT/ip/blocks/analog/wireline_serdes/pll:/vco:ro"
                -v "$ROOT/ip/blocks/analog/wifi_80211b:/wifi:ro"
                -v "$ROOT/scratch/transceiver-rf-ac-clock:/clock:ro"
                -v "$ROOT/scratch/transceiver-rf-ideal-lo:/reference:ro") ;;
 *) exit 2 ;;
esac
if [[ -n "${5:-}" ]]; then
 [[ "$5" =~ ^[a-z0-9-]+$ ]] || exit 2
 extra_mounts+=(-v "$ROOT/scratch/$5:/$input_target:ro")
fi
if [[ "${3:-basic}" == paired_inputs ]]; then
 extra_mounts+=(-v "$ROOT/scratch/$6:/candidate:ro")
fi
docker run --rm "${container_name[@]}" --platform linux/arm64 --network none --cpus "$cpu_count" --memory 4g --entrypoint /bin/bash \
 "${leading_mounts[@]}" \
 -v "$ROOT/projects/programmable_transceiver_platform/analog:/screen:ro" \
 "${extra_mounts[@]}" \
 -v "$OUT:/work" --workdir /work \
 sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 \
 -lc "python3 /screen/$runner_name$runner_arguments"
