#!/usr/bin/env bash
# RF receive family: extracted simulations -> generated/<block>-evidence.json, generated/rf_rx_chain.json,
# generated/rf_rx-summary.json.
#
# DEFAULT = EVIDENCE ONLY.  No netlist is rewritten and no layout is regenerated: the benches run on the cells that are
# on disk (generated/<block>.ext.spice) and the evidence records their sha256.  Regenerating a layout changes the GDS
# hash, and bbfilter_i / bbfilter_q / bb_tap are published, so layout regeneration is opt-in and per block:
#
#   ./run_rf_rx.sh                       evidence: chain, rxmix_i/q, bbfilter_i/q, bb_tap (full corner sets; hours at JOBS=1)
#   ./run_rf_rx.sh --quick               evidence, nominal points only
#   ./run_rf_rx.sh --blocks chain rxmix_i rxmix_q bb_tap --corners reduced
#                                        any characterize.py option is passed through (--blocks, --corners full|reduced|min,
#                                        --resume-chain, --chain-lo-stretch)
#   ./run_rf_rx.sh --regen-layout=rxmix_i,rxmix_q [...]
#                                        OPT-IN: first run netlists.py and generate_<block>.py (layout, DRC, extraction, LVS,
#                                        GDS export) for the NAMED blocks only, then the evidence run.  A published block
#                                        (PUBLISHED below) is refused unless --allow-published is also given, and the run
#                                        stops if netlists.py changed the netlist of a published block that was not named.
#   ./run_rf_rx.sh --readme [...]        also re-render README.md section 5 from the evidence (summarize.py --readme);
#                                        without it README.md is not touched.
#   JOBS=3 ./run_rf_rx.sh                concurrent simulations (default 1; machine rule: at most 3 per owner)
#
# The LNA is not characterised here: python3 lna_close.py currents|stab|stab_lf|band|chain|neg|write writes
# generated/lna-evidence.json (`--blocks lna` only prints that).  Chain rows that need the LNA chain points say
# 'not available' until lna_close.py chain has been run on the cells on disk.
#
# Host needs python3 + docker.  Every tool runs in a pinned image, offline and bounded
# (--network none --cpus 3 --memory 6g, OMP_NUM_THREADS=1; see rfrx_flow.py):
#   Magic / Netgen : svalbard/librelane-gf180-canary:2026.08
#                    sha256:b60278092f08c0a42fa93ed640d15d84eec53d7799790962781157ec34ceff43
#   ngspice        : hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3
#                    (local image id sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305)
# Raw output: <repo>/scratch/rf_rx/ (gitignored).
set -euo pipefail
cd "$(dirname "$0")"
export OMP_NUM_THREADS=1

PUBLISHED="bbfilter_i bbfilter_q bb_tap"
ALL="lna rxmix_i rxmix_q bbfilter_i bbfilter_q bb_tap"
REGEN="" ALLOW_PUBLISHED=0 README=0
ARGS=()
for a in "$@"; do
  case "$a" in
    --regen-layout=*) REGEN="${a#--regen-layout=}"; REGEN="${REGEN//,/ }" ;;
    --regen-layout)   echo "--regen-layout needs a block list: --regen-layout=rxmix_i,rxmix_q" >&2; exit 2 ;;
    --allow-published) ALLOW_PUBLISHED=1 ;;
    --readme) README=1 ;;
    *) ARGS+=("$a") ;;
  esac
done

for img in sha256:b60278092f08c0a42fa93ed640d15d84eec53d7799790962781157ec34ceff43 \
           sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305; do
  docker image inspect "$img" >/dev/null || { echo "missing pinned image $img" >&2; exit 2; }
done

if [ -n "$REGEN" ]; then
  for b in $REGEN; do
    case " $ALL " in *" $b "*) ;; *) echo "unknown block '$b' (known: $ALL)" >&2; exit 2 ;; esac
    case " $PUBLISHED " in *" $b "*)
      [ "$ALLOW_PUBLISHED" = 1 ] || { echo "refusing to regenerate the layout of PUBLISHED block $b (GDS hash would change); add --allow-published if that is intended" >&2; exit 2; } ;;
    esac
  done
  before=$(sha256sum $(for b in $PUBLISHED; do echo "$b.spice"; done))
  python3 netlists.py
  after=$(sha256sum $(for b in $PUBLISHED; do echo "$b.spice"; done))
  if [ "$before" != "$after" ]; then
    changed=$(diff <(echo "$before") <(echo "$after") | awk '/^>/{print $3}' | sed 's/\.spice$//' | tr '\n' ' ')
    for b in $changed; do
      case " $REGEN " in *" $b "*) ;; *)
        echo "netlists.py changed the netlist of published block $b, which was not named in --regen-layout: its GDS no longer matches its netlist. Stopping (restore $b.spice or regenerate it deliberately)." >&2; exit 3 ;;
      esac
    done
  fi
  for b in $REGEN; do
    echo "regenerating layout: $b"
    python3 "generate_${b}.py"
  done
else
  echo "evidence only: no netlist rewritten, no layout regenerated (opt in with --regen-layout=<blocks>)"
fi

python3 characterize.py --jobs "${JOBS:-1}" ${ARGS[@]+"${ARGS[@]}"}
if [ "$README" = 1 ]; then python3 summarize.py --readme; else python3 summarize.py; fi
