#!/bin/bash
# Signoff hook (integration/signoff/signoff.sh):   signoff_hook.sh <rf|wired> <ASM_RUN dir> <out dir>
# Netlist: <run>/lvs/pt_chip_top.ref.spice (written by the run's lvs stage; KH_CONN=1 runs) when present, else it is
# regenerated from this tree with KH_CONN=1. Runs the smoke test and its negative control and writes
# <out>/summary.json: {"pass": bool, "chip", "netlist", "netlist_sha256", "faults_by_check": {...}, "selftest": bool,
# "test": <smoke summary>}. Exit 0 only if pass. Light: one simulator process, about 5 / 8 min (rf / wired) with the negative control.
set -u
H=$(cd "$(dirname "$0")" && pwd); CHIP=${1:?rf|wired}; RUN=${2:?run dir}; OUT=${3:?out dir}
export OMP_NUM_THREADS=1
TREE=$(cd "$H/../../../.." && pwd)
mkdir -p "$OUT"
NL=()
[ -s "$RUN/lvs/pt_chip_top.ref.spice" ] && NL=(--netlist "$RUN/lvs/pt_chip_top.ref.spice")
python3 "$H/smoke.py" --chip "$CHIP" --tree "$TREE" "${NL[@]}" --out "$OUT/test" > "$OUT/test.log" 2>&1; RC=$?
python3 "$H/selftest.py" --chip "$CHIP" --tree "$TREE" "${NL[@]}" --out "$OUT/test" > "$OUT/selftest.log" 2>&1; ST=$?
python3 - "$OUT" "$RC" "$ST" <<'PY'
import json, sys, hashlib, collections
out, rc, st = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
try: t = json.load(open(out+'/test/summary.json'))
except Exception as e: t = dict(result='NO SUMMARY', faults=[dict(check='harness', detail=str(e))], netlist='')
by = collections.Counter(f['check'] for f in t.get('faults', []))
sha = hashlib.sha256(open(t['netlist'], 'rb').read()).hexdigest() if t.get('netlist') else None
s = dict(chip=t.get('chip'), netlist=t.get('netlist'), netlist_sha256=sha, macro_sha=t.get('macro_sha'),
         pass_=None, selftest=st == 0, faults_by_check=dict(by), test=t)
s['pass'] = rc == 0 and st == 0 and t.get('result') == 'PASS'; del s['pass_']
json.dump(s, open(out+'/summary.json', 'w'), indent=1)
print(f"chip_smoke {s['chip']}: {'PASS' if s['pass'] else 'FAIL'} (test {t.get('result')}, selftest {'PASS' if st == 0 else 'FAIL'}, faults {dict(by)})")
sys.exit(0 if s['pass'] else 1)
PY
