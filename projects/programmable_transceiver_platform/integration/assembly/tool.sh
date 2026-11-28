#!/bin/bash
# Run one command in the LibreLane GF180 image (OpenROAD + KLayout python), network off, one heavy job.
#   tool.sh <chip> [-c cpus] <command...>      (cpus <= 4, OMP_NUM_THREADS=1)
# Mounts: /repo = repository (read-only), /run = scratch/integration/assembly-<chip> (read-write), /asm = this directory.
A=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$A/../../../.." && pwd)
CHIP=$1; shift; RUN=${ASM_RUN:-$ROOT/scratch/integration/assembly-$CHIP}; mkdir -p "$RUN"
CPUS=1; [ "$1" = -c ] && { CPUS=$2; shift 2; }
[ "$CPUS" -le 4 ] || { echo "cpus > 4 not allowed" >&2; exit 2; }
# ASM_DATA=<main checkout> (worktree runs): /repo is that checkout, with this tree's integration/ mounted over it
MNT="-v $ROOT:/repo:ro"; [ -n "$ASM_DATA" ] && MNT="-v $ASM_DATA:/repo:ro -v $ROOT/projects/programmable_transceiver_platform/integration:/repo/projects/programmable_transceiver_platform/integration:ro"
# ASM_MOUNTS="<host path>:<path under /repo> ..." (worktree runs): extra read-only mounts over /repo, e.g. a re-generated block GDS
for m_ in $ASM_MOUNTS; do MNT="$MNT -v ${m_%%:*}:/repo/${m_#*:}:ro"; done
# ASM_DATA: every tracked checker script under scratch/integration (grid_conn.py, ...) comes from THIS tree, not from the data
# checkout's copy (fpw-14: signoff ran the main checkout's stale grid_conn.py). Files only, so untracked data there stays visible.
SCR_=""
if [ -n "$ASM_DATA" ]; then
  # (a file the data checkout lacks cannot be bind-mounted into the read-only /repo: it is not mounted, and the guard stops a
  # command that names it)
  while IFS= read -r f_; do [ -e "$ASM_DATA/$f_" ] || continue; MNT="$MNT -v $ROOT/$f_:/repo/$f_:ro"; SCR_="$SCR_ /repo/$f_"; done < <(git -C "$ROOT" ls-files 'scratch/integration/*.py' 'scratch/integration/*.sh' 2>/dev/null)
  # guard: a /repo/scratch/... script named in the command must be one of those (or an ASM_MOUNTS path), else stop loudly
  for p_ in $(printf '%s\n' "$@" | grep -o '/repo/scratch/[^ "'"'"']*\.\(py\|sh\)' | sort -u); do
    case " $SCR_ " in *" $p_ "*) ;; *)
      ok_=0; for m_ in $ASM_MOUNTS; do case "$p_" in /repo/${m_#*:}*) ok_=1;; esac; done
      [ $ok_ = 1 ] || { echo "tool.sh: $p_ is not from the tree under test ($ROOT): refusing (ASM_DATA run)" >&2; exit 3; } ;;
    esac
  done
fi
IMG=${ASM_IMAGE:-svalbard/librelane-gf180-guarded:2026.11}
exec docker run --rm -e HALO="${HALO:-0.2}" --name "asm-$CHIP-$$" --label svalbard.assembly=1 --network none --cpus "$CPUS" --memory "${ASM_MEM:-24g}" --user "$(id -u):$(id -g)" \
  -e HOME=/tmp -e OMP_NUM_THREADS=1 -e KH_CONN="${KH_CONN:-0}" -e GRID_SWAP="${GRID_SWAP:-1}" -e PLAN_FP="${PLAN_FP:-0}" ${MACRO_DIR:+-e MACRO_DIR=$MACRO_DIR} ${SLOT_HALO:+-e SLOT_HALO=$SLOT_HALO} ${PLATES:+-e PLATES=$PLATES} ${PAD_CUP:+-e PAD_CUP=$PAD_CUP} ${GC_GDS:+-e GC_GDS=$GC_GDS} ${GC_MAN:+-e GC_MAN=$GC_MAN} ${HOOK_DUAL:+-e HOOK_DUAL=$HOOK_DUAL} ${SLOT_CLEAN:+-e SLOT_CLEAN=$SLOT_CLEAN} -e GR_ADJ="${GR_ADJ:-0.15}" -e CHIP="$CHIP" -e THREADS="$CPUS" \
  $MNT -v "$RUN":/run -v "$A":/asm:ro --entrypoint /bin/bash "$IMG" -c \
  'export PATH=/foss/tools/bin:/foss/tools/klayout:$PATH; cd /run; exec "$@"' tool "$@"
