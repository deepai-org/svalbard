#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT="$ROOT/scratch/transceiver-mapping-equivalence"
# Explicit artifact comparison; hashes identify exactly what is proven.
python3 "$ROOT/projects/programmable_transceiver_platform/verification/mapping_equivalence.py" \
 "$ROOT/scratch/transceiver-delay-mapping/mapped/pt_digital_mapped.json" \
 "$ROOT/scratch/transceiver-delay-mapping-sized/buffered/pt_digital_mapped.json" "$OUT"
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m \
 --entrypoint /bin/sh -v "$OUT:/out" \
 sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -c '
 set -eu
 LIB=/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
 sha256sum "$LIB" > /out/library.sha256
 yosys -Q -T -p "read_liberty -ignore_miss_func $LIB; read_json /out/gold-cut.json /out/gate-cut.json; miter -equiv -flatten gold gate miter; hierarchy -top miter; flatten; opt; check -assert; sat -verify -prove trigger 0 -timeout 120" > /out/proof.log
 if yosys -Q -T -p "read_liberty -ignore_miss_func $LIB; read_json /out/gold-cut.json /out/gate-negative.json; miter -equiv -flatten gold gate miter; hierarchy -top miter; flatten; opt; check -assert; sat -verify -prove trigger 0 -timeout 120" > /out/negative-proof.log 2>&1; then
  echo "Intentional output inversion escaped proof" >&2; exit 1
 fi
 grep -q "proof did fail" /out/negative-proof.log
 printf "%s\n" "MAPPING_EQUIVALENCE_PASS; deliberate status-bit inversion rejected"' 
python3 "$ROOT/projects/programmable_transceiver_platform/verification/report_mapping_equivalence.py" "$OUT"
