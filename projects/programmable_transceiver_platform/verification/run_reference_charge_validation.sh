#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-reference-charge-validation"
python3 "$ROOT/projects/programmable_transceiver_platform/verification/freeze_reference_charge_validation.py"
mkdir "$OUT"
docker run --rm --name transceiver-reference-charge-validation --platform linux/arm64 --network none --cpus 1 --memory 4g --entrypoint /bin/bash \
 -v "$ROOT/projects/programmable_transceiver_platform/analog:/screen:ro" \
 -v "$ROOT/ip/blocks/analog/wifi_80211b:/wifi:ro" \
 -v "$ROOT/scratch/transceiver-reference-charge-validation-prepared:/prepared:ro" \
 -v "$OUT:/work" --workdir /work \
 sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 \
 -lc 'python3 /screen/adc/sar_command_replay.py baseline'
