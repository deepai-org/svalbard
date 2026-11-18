#!/bin/bash
# Live wafer.space precheck (gf180mcu-precheck 1.7.4, KLayout 0.30.12, Magic 8.3.677, LibreLane 3.1.0.dev3,
# PDK open_pdks 792ef67) on any layout, native aarch64, network off.
#   run_precheck.sh <abs gds/oas> <topcell> <workdir> [threads=4]
# Environment (optional): PC_ID (8 chars, default DEADBEEF), PC_SLOT (1x1), PC_COB (1; 0 = no --cob),
#   PC_WORKERS (1), PC_EXTRA (extra precheck.py arguments, e.g. "--to KLayout.Density" or "--skip Magic.DRC"),
#   PC_MEM (28g), PC_CPUSET (cpu list for the container; default 4 consecutive cores chosen at random).
# The container is pinned to <threads> cores: the density and antenna steps do not pass a thread count to the deck
# (LibreLane gives the density deck "thr=", which it ignores), so the deck would otherwise take every core.
# The work directory must not exist or be empty. Result: <workdir>/runs/precheck/ (LibreLane run directory),
# <workdir>/out/<topcell>.oas (the layout the precheck would hand on: ID/QR inserted, dummy metal merged),
# <workdir>/precheck.log, <workdir>/exit_code. Then: summarise.py <workdir>.
# Environment build and rebuild: NOTES.md. Machine rule: threads <= 4, one heavy job at a time.
set -u
SO=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$SO/../../../../.." && pwd)
ENVD=${PC_ENV:-$ROOT/scratch/integration/signoff-run/pc}      # precheck/ (1.7.4 tree) and pdk/ (792ef67)
VOL=${PC_NIX_VOLUME:-signoff_nix}                             # docker volume holding /nix (dev shell closure)
IMG=${PC_NIX_IMAGE:-nixos/nix:2.28.3}
[ $# -ge 3 ] || { sed -n 2,11p "$0"; exit 2; }
IN=$(realpath "$1"); TOP=$2; WD=$3; THR=${4:-4}
[ -f "$IN" ] || { echo "no input $IN" >&2; exit 2; }
[ "$THR" -le 4 ] || { echo "threads > 4 not allowed" >&2; exit 2; }
mkdir -p "$WD"; WD=$(realpath "$WD")
[ -z "$(ls -A "$WD")" ] || { echo "work directory $WD is not empty" >&2; exit 2; }
mkdir -p "$WD/out"
COB="--cob"; [ "${PC_COB:-1}" = 0 ] && COB=""
BN=$(basename "$IN")
NC=$(nproc); S0=$(( (RANDOM % (NC / 4)) * 4 )); CPUSET=${PC_CPUSET:-$S0-$((S0 + THR - 1))}
docker run --rm --network none --cpus "$THR" --cpuset-cpus "$CPUSET" --memory "${PC_MEM:-28g}" --user "$(id -u):$(id -g)" \
  -e HOME=/tmp -e OMP_NUM_THREADS=1 -e PDK_ROOT=/pdk -e PDK=gf180mcuD \
  -v "$VOL":/nix:ro -v "$ENVD/precheck":/precheck:ro -v "$ENVD/pdk":/pdk:ro \
  -v "$IN":/in/"$BN":ro -v "$WD":/wd -w /wd "$IMG" \
  /nix/var/signoff-devshell/entrypoint python3 /precheck/precheck.py \
    --input /in/"$BN" --top "$TOP" --slot "${PC_SLOT:-1x1}" $COB --id "${PC_ID:-DEADBEEF}" \
    --workers "${PC_WORKERS:-1}" --threads "$THR" --dir /wd --run-tag precheck \
    --output /wd/out/"$TOP".oas ${PC_EXTRA:-} > "$WD/precheck.log" 2>&1
RC=$?
echo $RC > "$WD/exit_code"
tail -5 "$WD/precheck.log"
echo "precheck exit code $RC (0 = pass). Log: $WD/precheck.log"
exit $RC
