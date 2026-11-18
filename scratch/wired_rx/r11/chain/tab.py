"""Compact tables of bench A (tran.json) and bench B (capb.json)."""
import json, sys
from pathlib import Path
H = Path(__file__).resolve().parent
t = json.loads((H / 'tran.json').read_text()) if (H / 'tran.json').exists() else {}
for k, v in t.items():
    if 'eye_mVppd' not in v: print(k, 'ERROR', str(v.get('error'))[:80]); continue
    if v.get('mode') == 'full':
        print(f"A {k}: eye {v['eye_mVppd']}/{v['eye_width_ui_ge60']}UI clean phases {v.get('clean_phases')} run {v.get('longest_clean_run')} {'PASS' if v['pass'] else 'FAIL'}")
    else:
        print(f"A {k}: eye {v['eye_mVppd']}/{v['eye_width_ui_ge60']}UI at-instant {v.get('min_eye_at_instant_mVppd')} margin {v.get('min_margin_ui')}UI err {v.get('bit_errors')}/{v.get('bits_checked')} code {v.get('ctle_code')} {'PASS' if v['pass'] else 'FAIL'}")
b = json.loads((H / 'capb.json').read_text()) if (H / 'capb.json').exists() else {}
for k, v in b.items():
    print(f"B {k}: bits {v.get('bits')} data err {v.get('bit_errors')} edge err {v.get('edge_errors')} pd {v.get('pd_ok')} strobe err {v.get('strobe_word_errors')} {'PASS' if v.get('pass') else 'FAIL'} {str(v.get('error') or '')[:60]}")
c = json.loads((H / 'clk.json').read_text()) if (H / 'clk.json').exists() else {}
for k, v in c.items():
    if 'codes' in v: print(f"C {k}: spread code0 {v['spread_code0_ps']} ps, range {min(v['range_ps'])}, covers {v['range_covers']}, trimmed spread {v['spread_trimmed_ps']} ps, duty {min(x['duty'] for x in v['trimmed'])}-{max(x['duty'] for x in v['trimmed'])}, mA {v['idd_ptrim_mA']['trimmed']}")
    else: print('C', k, v.get('error'))
