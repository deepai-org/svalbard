#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
output_name=${1:?output directory name required}
runner_name=${2:?Python checker filename required}
[[ "$output_name" =~ ^[a-z0-9-]+$ && "$runner_name" =~ ^[a-zA-Z0-9_]+\.py$ ]] || exit 2
OUT="$ROOT/scratch/$output_name"
mkdir -p "$OUT"
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,size=512m --entrypoint /bin/sh -v "$ROOT/projects/programmable_transceiver_platform:/src:ro" -v "$OUT:/out" sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17 -c "python3 /src/verification/$runner_name"
