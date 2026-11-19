#!/bin/bash
# Project KLayout 0.30.9 (aarch64 image), batch mode, network off.
#   kl.sh [-c cpus] <script.py|.rb|.drc> [-rd k=v ...]
# Mounts: /repo = repository (read-only), /run = scratch/integration/signoff-run-<chip> (read-write), /so = this directory (read-only).
# Machine rule: cpus <= 4, OMP_NUM_THREADS=1.
SO=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$SO/../../../.." && pwd)
RUN=${SIGNOFF_RUN:-$ROOT/scratch/integration/signoff-run-${SIGNOFF_CHIP:?SIGNOFF_CHIP=rf|wired}}; mkdir -p "$RUN"
CPUS=1; [ "$1" = -c ] && { CPUS=$2; shift 2; }
[ "$CPUS" -le 4 ] || { echo "cpus > 4 not allowed" >&2; exit 2; }
IMG=${KL_IMAGE:-sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305}
S=$1; shift
exec docker run --rm --network none --cpus "$CPUS" --memory "${KL_MEM:-28g}" --user "$(id -u):$(id -g)" -e HOME=/tmp -e OMP_NUM_THREADS=1 \
  -v "$ROOT":/repo:ro -v "$RUN":/run -v "$SO":/so:ro ${KL_EXTRA} --entrypoint /bin/bash "$IMG" -c \
  'export PATH=$PATH:/foss/tools/klayout LD_LIBRARY_PATH=/foss/tools/klayout; cd /run; exec klayout -b -zz -r "$@"' kl "/so/$S" "$@"
