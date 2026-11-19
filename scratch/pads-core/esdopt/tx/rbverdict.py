#!/usr/bin/env python3
"""rbverdict.py pos|neg <rb_lvs log> [swap.log]: judge read-back LVS from the tool's JSON line, not its exit code (rb_lvs.py exits 0 on a
mismatch). pos: status match AND netgen unique. neg: swap.log must say 'swapped 2' AND status mismatch (a crash or a missing input is NOT a pass)."""
import json, sys
mode, log = sys.argv[1], sys.argv[2]
try: r = json.loads([l for l in open(log) if l.startswith('{')][-1])
except Exception as e: print(f'FAIL (no result: {type(e).__name__})'); sys.exit(1)
if mode == 'pos': ok = r['status'] == 'match' and r.get('netgen_unique') is True
else:
    sw = open(sys.argv[3]).read() if len(sys.argv) > 3 else ''
    ok = 'swapped 2' in sw and r['status'] == 'mismatch'
print(('PASS' if ok else 'FAIL') + f" (status {r['status']}, unique {r.get('netgen_unique')}, {r.get('what')})"); sys.exit(0 if ok else 1)
