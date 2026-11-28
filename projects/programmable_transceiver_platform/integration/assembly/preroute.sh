#!/bin/bash
# Pre-route in-context check (run.sh stage 'preroute', after place / lint, before route; minutes, not a route):
#   preroute.sh <rf|wired> [only=<inst,...>] [neg=<v4_overlap|v3_overlap|m5_space|ring_via> negblk=<inst>]
#   preroute.sh <rf|wired> selftest
# 1. windows   preroute_win.py build: one window per block / custom pad of placed.gds (bbox + 15 um) with all top-level
#              metal drawn before routing (provider ring, pt_pdn grid, island bars, plates, landings, pads, neighbours);
#              BEOL layers only (Metal2-5, Via2-5, MetalTop, Pad)
# 2. DRC       the signoff deck (shuttle PDK 792ef67, as signoff/drc/run_drc.sh), BEOL rule decks: beol,-antenna,-density,-cup
# 3. classify  preroute_win.py attr: markers per window; 'context' = touches top-level metal or a second instance (gated),
#              'internal' = the block alone (block owner's DRC, reported only); clip-edge artefacts dropped
# 4. supplies  grid_conn.py on placed.gds: every block / pad VDD / VSS pin on a pad-fed grid piece, except pins whose only
#              feed is a router hook (place.json hooks, drawn by the route)
# Verdict 'PREROUTE PASS' / 'PREROUTE FAIL' (exit 1): any context marker whose rule is not in PREROUTE_ACCEPT (comma list),
# or any unfed supply that no hook will feed. Window cache: each window's result is stored under a hash of its content
# (every top-level instance's kept shapes in it, relative to the window, + deck + margin) in PREROUTE_CACHE (default
# <data root>/scratch/integration/preroute-cache); a rerun checks only windows whose content changed. SUPPLIES=0 skips step 4.
# Output: $RUN/preroute/{result.json,summary.txt}. One heavy job (4 cpus, PREROUTE_CPUS).
set -u
A=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$A/../../../.." && pwd); SO=$A/../signoff
CHIP=${1:?rf|wired}; shift
RUN=${ASM_RUN:-$ROOT/scratch/integration/assembly-$CHIP}; O=$RUN/preroute; mkdir -p "$O"
DATA=${ASM_DATA:-$ROOT}
PDK_LIVE=${PDK_LIVE:-$DATA/scratch/integration/signoff-gap/precheck/pdk_792ef67}
KL_IMAGE=${KL_IMAGE:-sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305}
W=${PREROUTE_CPUS:-4}
CACHE=${PREROUTE_CACHE:-$DATA/scratch/integration/preroute-cache}; mkdir -p "$CACHE"
DECKID=$(cat "$PDK_LIVE"/drc/rule_decks/{metal,via,metaltop,mslot}.rb "$PDK_LIVE"/drc/gf180mcu.drc "$A/preroute_win.py" 2>/dev/null | sha256sum | cut -c1-16)
kl() { docker run --rm --network none --cpus "$W" --memory 24g --user "$(id -u):$(id -g)" -e HOME=/tmp -e OMP_NUM_THREADS=1 \
        -v "$RUN":/run:ro -v "$O":/o -v "$A":/a:ro -v "$PDK_LIVE/drc":/deck:ro -v "$CACHE":/c --entrypoint /bin/bash "$KL_IMAGE" -c \
        "export PATH=\$PATH:/foss/tools/klayout LD_LIBRARY_PATH=/foss/tools/klayout; cd /tmp; klayout -b -zz $*"; }

one() {   # one(tag, extra build -rd args): windows -> DRC -> classify; prints the context count
  local T=$1; shift; local D=$O/$T; mkdir -p "$D"; local t0=$(date +%s); local X=""; for a_ in "$@"; do X="$X -rd $a_"; done
  kl -r /a/preroute_win.py -rd mode=build -rd inp=/run/placed.gds -rd out=/o/$T/win.gds -rd win=/o/$T/win.json -rd cache=/c -rd deckid=$DECKID $X > "$D/build.log" 2>&1 || { tail -5 "$D/build.log"; return 2; }
  local t1=$(date +%s)
  if grep -q "(0 to check" "$D/build.log"; then echo "all windows cached" > "$D/drc.log"; : > "$D/report.lyrdb"; else
  kl -r /deck/gf180mcu.drc -rd input=/o/$T/win.gds -rd topcell=PREROUTE_WINDOWS -rd report=/o/$T/report.lyrdb \
     "-rd decks='beol,-antenna,-density,-cup'" -rd variant=gf180mcuD -rd workers=$W -rd threads=$W > "$D/drc.log" 2>&1
  grep -q "DRC Total Run time" "$D/drc.log" || { echo "$T: DRC did not finish"; tail -5 "$D/drc.log"; return 2; }; fi
  local t2=$(date +%s)
  kl -r /a/preroute_win.py -rd mode=attr -rd wgds=/o/$T/win.gds -rd inp=/run/placed.gds -rd win=/o/$T/win.json -rd rdb=/o/$T/report.lyrdb -rd res=/o/$T/result.json -rd cache=/c > "$D/attr.log" 2>&1 || { tail -5 "$D/attr.log"; return 2; }
  local t3=$(date +%s); rm -f "$D/win.gds"; gzip -f "$D/report.lyrdb"
  echo "$T: windows $((t1-t0)) s ($(grep -o '([0-9]* to check, [0-9]* cached' "$D/build.log" | tr -d '(')), DRC $((t2-t1)) s, classify $((t3-t2)) s; $(grep -m1 '^windows' "$D/attr.log" | sed 's/.*); //')"
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

supplies() {   # supplies([tag]) ; NEG_LAND=<inst> drops that block's direct landing (negative control)
  local G=${1:-grid_conn}
  python3 - "$RUN" <<'EOF'
import json, sys
R = sys.argv[1] + '/'
p = json.load(open(R + 'place.json')); pads = json.load(open(R + 'pads.json'))
I = [dict(name=n, master=b['master'], cell=b['master'], trans=b['trans'], kind=b.get('kind', 'block'), bbox=b['bbox']) for n, b in p['blocks'].items()]
I += [dict(name=n, master=v['master'], cell=v['master'], trans=v['trans'], kind='pad', bbox=v['bbox']) for n, v in pads['pads'].items()]
json.dump(dict(top='pt_chip_top', instances=I), open(R + 'preroute/manifest.json', 'w'))
EOF
  ASM_RUN=$RUN GC_GDS=placed.gds GC_MAN=preroute/manifest.json bash "$A/tool.sh" "$CHIP" python3 /repo/scratch/integration/m1-pdn/grid_conn.py > "$O/$G.txt" 2>&1
  python3 - "$RUN" "$G" <<'EOF'
import json, sys
R = sys.argv[1] + '/'
t = open(R + 'preroute/' + sys.argv[2] + '.txt').read()
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
  # DRC: one clean block window must pass; the same window with one drawn fault per class must fail; the pad_txpad window
  # with a PAD-16 replica (a cut 0.13 um off a provider-ring Via4) must fail. Supplies: a block whose only feed is its
  # direct landing (place.json direct_landings, no router hook) must turn up unfed when that landing is removed.
  CLEAN=${PREROUTE_CLEAN:-pt_vthdac}; PADW=${PREROUTE_PADW:-pad_txpad}; FAIL=0
  CACHE=$O/st_cache; rm -rf "$CACHE"; mkdir -p "$CACHE"      # fresh: every selftest window is really checked
  one st_clean only=$CLEAN >/dev/null; n=$(gate st_clean | tail -1); echo "clean window $CLEAN: context $n $([ "$n" = 0 ] && echo PASS || { echo 'FAIL (must be 0)'; FAIL=1; })"
  for neg in v4_overlap v3_overlap m5_space; do
    one st_$neg only=$CLEAN neg=$neg negblk=$CLEAN >/dev/null; n=$(gate st_$neg | tail -1)
    echo "negative $neg in $CLEAN: context $n $([ "$n" -gt 0 ] && echo 'fails (PASS)' || { echo 'NOT DETECTED (FAIL)'; FAIL=1; })"
  done
  one st_ring_via only=$PADW neg=ring_via negblk=$PADW >/dev/null; n=$(gate st_ring_via | tail -1)
  echo "negative ring_via (PAD-16 replica) in $PADW: context $n $([ "$n" -gt 0 ] && echo 'fails (PASS)' || { echo 'NOT DETECTED (FAIL)'; FAIL=1; })"
  if [ "${SUPPLIES:-1}" != 0 ]; then
    NL=$(python3 -c "
import json; p = json.load(open('$RUN/place.json')); h = {(x['inst'], x['net'].split('__')[0]) for x in p.get('hooks', [])}
print(next(d['inst'] for d in p.get('direct_landings', []) if (d['inst'], d['net']) not in h and d.get('via4', 0) > 0))")
    n=$(NEG_LAND=$NL supplies st_neg_land | tail -1)
    echo "negative supply landing removed ($NL): unfed $n $([ "$n" -gt 0 ] && echo 'fails (PASS)' || { echo 'NOT DETECTED (FAIL)'; FAIL=1; })"
  fi
  [ $FAIL = 0 ] && echo "PREROUTE SELFTEST PASS" || { echo "PREROUTE SELFTEST FAIL"; exit 1; }
  exit 0
fi

T0=$(date +%s)
one chip "$@" || { echo "PREROUTE FAIL (tool)"; exit 1; }
echo "context markers not accepted (rule, owners):"; NC=$(gate chip | tee "$O/gate.txt" | tail -1); sed '$d' "$O/gate.txt"
NS=0; case " $* " in *only=*|*neg=*) ;; *) [ "${SUPPLIES:-1}" = 0 ] && { echo "supplies: skipped (SUPPLIES=0)"; } || { echo "supplies:"; NS=$(supplies | tee "$O/supplies.txt" | tail -1); sed '$d' "$O/supplies.txt"; } ;; esac
echo "chip $CHIP run $(basename "$RUN"): context $NC, unfed $NS, $(( $(date +%s)-T0 )) s" | tee "$O/summary.txt"
[ "$NC" = 0 ] && [ "$NS" = 0 ] && echo "PREROUTE PASS" || { echo "PREROUTE FAIL"; exit 1; }
