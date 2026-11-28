#!/bin/bash
# Signoff hook (integration/signoff/signoff.sh):   signoff_hook.sh <rf|wired> <ASM_RUN dir> <out dir> [--layout]
# --layout: the bench is wired from the netlist EXTRACTED from <run>/chip/pt_chip_top.gds (layout.sh, ~5 min KLayout, 1 cpu, run
# twice: as is and with the metal erased at the POR_BYPASS PD tie + one c_* consumer pin, which must FAIL naming both);
# summary gains mode=layout and the two extraction summaries (netlist_sha256 = that of the extracted netlist).
# Netlist: <run>/lvs/pt_chip_top.ref.spice (written by the run's lvs stage; KH_CONN=1 runs) when present, else it is
# regenerated from this tree with KH_CONN=1. Runs the smoke test and its negative control and writes
# <out>/summary.json: {"pass": bool, "chip", "netlist", "netlist_sha256", "faults_by_check": {...}, "selftest": bool,
# "test": <smoke summary>}. Exit 0 only if pass. Light: one simulator process, about 5 / 8 min (rf / wired) with the negative control.
set -u
H=$(cd "$(dirname "$0")" && pwd); CHIP=${1:?rf|wired}; RUN=${2:?run dir}; OUT=${3:?out dir}
export OMP_NUM_THREADS=1
TREE=$(cd "$H/../../../.." && pwd)
mkdir -p "$OUT"
MODE=conn
if [ "${4:-}" = --layout ]; then     # layout mode: netlist extracted from <run>/chip/pt_chip_top.gds; negative control = metal erased
  MODE=layout
  CUT=$(case $CHIP in rf) echo io_bidir_16.PD,lna.ct2,aosc.VSS ;; wired) echo io_bidir_16.PD,ctle.ctle_peak2,aosc.VSS ;; esac)
  "$H/layout.sh" "$CHIP" "$RUN" "$OUT/extract" > "$OUT/extract.log" 2>&1 && \
  "$H/layout.sh" "$CHIP" "$RUN" "$OUT/extract-cut" "cut=$CUT" > "$OUT/extract-cut.log" 2>&1
  EX=$?
  NL=(--netlist "$OUT/extract/layout.spice")
  python3 "$H/smoke.py" --chip "$CHIP" --tree "$TREE" "${NL[@]}" --out "$OUT/test" > "$OUT/test.log" 2>&1; RC=$?
  [ $EX -eq 0 ] || RC=1
  python3 "$H/selftest.py" --chip "$CHIP" --tree "$TREE" --layout-cut "$OUT/extract-cut/layout.spice" "$CUT" --out "$OUT/test" > "$OUT/selftest.log" 2>&1; ST=$?
else
NL=()
[ -s "$RUN/lvs/pt_chip_top.ref.spice" ] && NL=(--netlist "$RUN/lvs/pt_chip_top.ref.spice")
python3 "$H/smoke.py" --chip "$CHIP" --tree "$TREE" "${NL[@]}" --out "$OUT/test" > "$OUT/test.log" 2>&1; RC=$?
python3 "$H/selftest.py" --chip "$CHIP" --tree "$TREE" "${NL[@]}" --out "$OUT/test" > "$OUT/selftest.log" 2>&1; ST=$?
fi
python3 - "$OUT" "$RC" "$ST" "$MODE" "$RUN" <<'PY'
import json, sys, hashlib, collections
out, rc, st, mode, run = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
try: t = json.load(open(out+'/test/summary.json'))
except Exception as e: t = dict(result='NO SUMMARY', faults=[dict(check='harness', detail=str(e))], netlist='')
by = collections.Counter(f['check'] for f in t.get('faults', []))
sha = hashlib.sha256(open(t['netlist'], 'rb').read()).hexdigest() if t.get('netlist') else None
s = dict(mode=mode, chip=t.get('chip'), netlist=t.get('netlist'), netlist_sha256=sha, macro_sha=t.get('macro_sha'),
         pass_=None, selftest=st == 0, faults_by_check=dict(by), test=t)
s['pass'] = rc == 0 and st == 0 and t.get('result') == 'PASS'; del s['pass_']
if mode == 'layout':
    s['gds_sha256'] = hashlib.sha256(open(run+'/chip/pt_chip_top.gds', 'rb').read()).hexdigest()
    try: s['extract'] = {k: json.load(open(f'{out}/{k}/layout.spice.json')) for k in ('extract', 'extract-cut')}
    except Exception as e: s['extract'] = str(e)
json.dump(s, open(out+'/summary.json', 'w'), indent=1)
print(f"chip_smoke {mode} {s['chip']}: {'PASS' if s['pass'] else 'FAIL'} (test {t.get('result')}, selftest {'PASS' if st == 0 else 'FAIL'}, faults {dict(by)})")
sys.exit(0 if s['pass'] else 1)
PY
