#!/usr/bin/env python3
"""ctab.py tag [tag ...]: checks T-A..T-D of cbench.py on bench/<tag>-term.json; prints a table and PASS/FAIL per check."""
import json, sys
def cross(r):
    for c in range(1, 16):
        if r[c] <= 100 < r[c - 1]: return c - 1 + (r[c - 1] - 100) / (r[c - 1] - r[c])
    return -1.0 if r[0] <= 100 else 99.0
allr = {}
for tag in sys.argv[1:]:
    d = json.load(open(f'bench/{tag}-term.json')); T = d['term']; allr[tag] = T; okA = okB = okC = True
    print(f'== {tag} (sha {d["model_sha256"][:8]}, VCM {d.get("vcm")}); TERM_ENABLE off: {d.get("negative_control_off_min_ohm", float("nan")):.3g} ohm')
    for k, v in T.items():
        r = v['r_diff']; i = min(range(16), key=lambda c: abs(r[c] - 100)); x = cross(r)
        a = 95 <= r[i] <= 105; b = 2 <= i <= 13; c = abs(v['r_p'][i] - v['r_n'][i]) <= 1.0; okA &= a; okB &= b; okC &= c
        print(f'  {k:16s} code0 {r[0]:6.1f} code15 {r[15]:6.1f}  100 ohm at {x:5.1f}  best code {i:2d}: {r[i]:6.1f} (P-N {v["r_p"][i] - v["r_n"][i]:+.2f})  {"" if a and b and c else "FAIL " + ("A" if not a else "") + ("B" if not b else "") + ("C" if not c else "")}')
    print(f'  T-A {"PASS" if okA else "FAIL"}  T-B {"PASS" if okB else "FAIL"}  T-C {"PASS" if okC else "FAIL"}')
    inw = [k for k in T if not k.endswith('_3.5')]
    best = min(range(16), key=lambda c: max(abs(T[k]['r_diff'][c] - 100) for k in inw)); lo = min(T[k]['r_diff'][best] for k in inw); hi = max(T[k]['r_diff'][best] for k in inw)
    print(f'  T-D single code {best}: {lo:.1f} .. {hi:.1f} ohm over the in-window corners  {"PASS" if 80 <= lo and hi <= 120 else "FAIL"}')
