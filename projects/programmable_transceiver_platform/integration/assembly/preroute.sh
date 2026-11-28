#!/bin/bash
# Pre-route in-context check (run.sh stage 'preroute', after place / lint, before route; minutes, not a route):
#   preroute.sh <rf|wired> [only=<inst,...>] [neg=<v4_overlap|v3_overlap|m5_space>]
#   preroute.sh <rf|wired> selftest
# 1. windows   preroute_win.py build: one window per block / custom pad of placed.gds (bbox + 15 um) with all top-level
#              metal drawn before routing (provider ring, pt_pdn grid, island bars, plates, landings, pads, neighbours);
#              BEOL layers only (Metal2-5, Via2-5, MetalTop, Pad); pads finalized as the flow imports them (PAD_FIX=1, pad_cup.py)
# 2. DRC       the signoff deck (shuttle PDK 792ef67, as signoff/drc/run_drc.sh), BEOL rule decks: beol,-antenna,-density,-cup
# 3. classify  preroute_win.py attr: markers per window; 'context' = touches top-level metal or a second instance (gated),
#              'internal' = the block alone (block owner's DRC, reported only); clip-edge artefacts dropped
# 4. supplies  grid_conn.py on placed.gds: every block / pad VDD / VSS pin on a pad-fed grid piece, except pins whose only
#              feed is a router hook (place.json hooks, drawn by the route)
# Verdict 'PREROUTE PASS' / 'PREROUTE FAIL' (exit 1): any context marker whose rule is not in PREROUTE_ACCEPT (comma list),
# or any unfed supply that no hook will feed. Output: $RUN/preroute/{result.json,summary.txt}. One heavy job (4 cpus, PREROUTE_CPUS).
set -u
A=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$A/../../../.." && pwd); SO=$A/../signoff
CHIP=${1:?rf|wired}; shift
RUN=${ASM_RUN:-$ROOT/scratch/integration/assembly-$CHIP}; O=$RUN/preroute; mkdir -p "$O"
DATA=${ASM_DATA:-$ROOT}
PDK_LIVE=${PDK_LIVE:-$DATA/scratch/integration/signoff-gap/precheck/pdk_792ef67}
KL_IMAGE=${KL_IMAGE:-sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305}
W=${PREROUTE_CPUS:-4}
kl() { docker run --rm --network none --cpus "$W" --memory 24g --user "$(id -u):$(id -g)" -e HOME=/tmp -e OMP_NUM_THREADS=1 \
        -v "$RUN":/run:ro -v "$O":/o -v "$A":/a:ro -v "$PDK_LIVE/drc":/deck:ro --entrypoint /bin/bash "$KL_IMAGE" -c \
        "export PATH=\$PATH:/foss/tools/klayout LD_LIBRARY_PATH=/foss/tools/klayout; cd /tmp; klayout -b -zz $*"; }

one() {   # one(tag, extra build -rd args): windows -> DRC -> classify; prints the context count
  local T=$1; shift; local D=$O/$T; mkdir -p "$D"; local t0=$(date +%s); local X=""; for a_ in "$@"; do X="$X -rd $a_"; done
  kl -r /a/preroute_win.py -rd mode=build -rd inp=/run/placed.gds -rd out=/o/$T/win.gds -rd win=/o/$T/win.json  -rd padfix=${PAD_FIX:-1} $X > "$D/build.log" 2>&1 || { tail -5 "$D/build.log"; return 2; }
  local t1=$(date +%s)
  kl -r /deck/gf180mcu.drc -rd input=/o/$T/win.gds -rd topcell=PREROUTE_WINDOWS -rd report=/o/$T/report.lyrdb \
     "-rd decks='beol,-antenna,-density,-cup'" -rd variant=gf180mcuD -rd workers=$W -rd threads=$W > "$D/drc.log" 2>&1
  grep -q "DRC Total Run time" "$D/drc.log" || { echo "$T: DRC did not finish"; tail -5 "$D/drc.log"; return 2; }
  local t2=$(date +%s)
  kl -r /a/preroute_win.py -rd mode=attr -rd wgds=/o/$T/win.gds -rd inp=/run/placed.gds -rd win=/o/$T/win.json -rd rdb=/o/$T/report.lyrdb -rd res=/o/$T/result.json > "$D/attr.log" 2>&1 || { tail -5 "$D/attr.log"; return 2; }
  local t3=$(date +%s); rm -f "$D/win.gds"; gzip -f "$D/report.lyrdb"
  echo "$T: windows $((t1-t0)) s, DRC $((t2-t1)) s, classify $((t3-t2)) s; $(grep -m1 '^markers' "$D/attr.log")"
}

gate() {  # gate(tag): context markers not accepted -> count
  python3 - "$O/$1/result.json" "${PREROUTE_ACCEPT:-}" <<'EOF'
import json, sys
r = json.load(open(sys.argv[1])); acc = {a for a in sys.argv[2].split(',') if a}
bad = [c for c in r['by_class'] if c['cls'] == 'context' and c['rule'] not in acc]
for c in bad[:30]: print(f"   {c['n']:6d} {c['rule']:10s} {c['owners']}")
print(sum(c['n'] for c in bad))
EOF
}

supplies() {
  python3 - "$RUN" <<'EOF'
import json, sys
R = sys.argv[1] + '/'
p = json.load(open(R + 'place.json')); pads = json.load(open(R + 'pads.json'))
I = [dict(name=n, master=b['master'], cell=b['master'], trans=b['trans'], kind=b.get('kind', 'block'), bbox=b['bbox']) for n, b in p['blocks'].items()]
I += [dict(name=n, master=v['master'], cell=v['master'], trans=v['trans'], kind='pad', bbox=v['bbox']) for n, v in pads['pads'].items()]
json.dump(dict(top='pt_chip_top', instances=I), open(R + 'preroute/manifest.json', 'w'))
EOF
  ASM_RUN=$RUN GC_GDS=placed.gds GC_MAN=preroute/manifest.json bash "$A/tool.sh" "$CHIP" python3 /repo/scratch/integration/m1-pdn/grid_conn.py > "$O/grid_conn.txt" 2>&1
  python3 - "$RUN" <<'EOF'
import json, sys
R = sys.argv[1] + '/'
t = open(R + 'preroute/grid_conn.txt').read()
if '\nJSON\n' not in t: print('grid_conn failed'); print(t[-600:]); print(-1); sys.exit()
g = json.loads(t.split('\nJSON\n')[1].splitlines()[0]); p = json.load(open(R + 'place.json'))
hooked = {(h['inst'], h['net'].split('__')[0]) for h in p.get('hooks', [])}
bad = [u for u in g['unfed'] if (u['inst'], u['net']) not in hooked]
print(f"   unfed before routing {len(g['unfed'])}, of them fed by a router hook {len(g['unfed']) - len(bad)}, island bars fed {g['island_bars']['ok']}")
for u in bad[:20]: print('   UNFED', u['inst'], u['net'], u['master'], u['pins'][:4])
print(len(bad))
EOF
}

if [ "${1:-}" = selftest ]; then
  # known-good: one clean block window must pass; known-bad: the same window with one drawn fault per class must fail
  # with that class; real known-bad windows (fpw-14): pad_txpad (PAD-16, PAD_FIX=0), the RAIL_wired_tx bar on wiredtx
  CLEAN=${PREROUTE_CLEAN:-pt_vthdac}; FAIL=0
  one st_clean only=$CLEAN >/dev/null; n=$(gate st_clean | tail -1); echo "clean window $CLEAN: context $n $([ "$n" = 0 ] && echo PASS || { echo 'FAIL (must be 0)'; FAIL=1; })"
  for neg in v4_overlap v3_overlap m5_space; do
    one st_$neg only=$CLEAN neg=$neg negblk=$CLEAN >/dev/null; n=$(gate st_$neg | tail -1)
    echo "negative $neg in $CLEAN: context $n $([ "$n" -gt 0 ] && echo 'fails (PASS)' || { echo 'NOT DETECTED (FAIL)'; FAIL=1; })"
  done
  PAD_FIX=0 one st_pad_old only=pad_txpad >/dev/null; n=$(gate st_pad_old | tail -1)
  echo "known-bad pad_txpad as published (PAD-16): context $n $([ "$n" -gt 0 ] && echo 'fails (PASS)' || { echo 'NOT DETECTED (FAIL)'; FAIL=1; })"
  [ $FAIL = 0 ] && echo "PREROUTE SELFTEST PASS" || { echo "PREROUTE SELFTEST FAIL"; exit 1; }
  exit 0
fi

T0=$(date +%s)
one chip "$@" || { echo "PREROUTE FAIL (tool)"; exit 1; }
echo "context markers not accepted (rule, owners):"; NC=$(gate chip | tee "$O/gate.txt" | tail -1); sed '$d' "$O/gate.txt"
NS=0; case " $* " in *only=*|*neg=*) ;; *) echo "supplies:"; NS=$(supplies | tee "$O/supplies.txt" | tail -1); sed '$d' "$O/supplies.txt" ;; esac
echo "chip $CHIP run $(basename "$RUN"): context $NC, unfed $NS, $(( $(date +%s)-T0 )) s" | tee "$O/summary.txt"
[ "$NC" = 0 ] && [ "$NS" = 0 ] && echo "PREROUTE PASS" || { echo "PREROUTE FAIL"; exit 1; }
