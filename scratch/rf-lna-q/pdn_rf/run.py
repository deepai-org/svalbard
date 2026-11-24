"""stab_lf on the metal-aware LNA (rext) with the pt_rf assembly PDN (spec/power-delivery.md 5.4 / assembly rerun):
die decap 4.74 nF, 0.44 nH per rail (pessimistic set), isw_rf 0.05 ohm. Decap loss below the plan's Q 1.8 (pessimistic).
Negative control: lossless 3 nF / 2 nH (known fail, -6.4 ohm on ext). Limit: Re(Zcm) >= 1.0 ohm, 5 MHz-1 GHz."""
import os, sys, json
os.environ['RFRX_LNA_SRC'] = 'rext'
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx')
import lna_close as C, lna_match as LM, tb
from pathlib import Path
OUT = Path(__file__).parent
PLAN = [dict(cdie=4.74e-9, rdie=0.1, rsw=0.05, lsup=0.44e-9), dict(cdie=4.74e-9, rdie=0.05, rsw=0.05, lsup=0.44e-9)]
NEG = dict(cdie=3e-9, rdie=0.03, rsw=0.2, lsup=2e-9)
def one(c, lob, k, tag):
    tb.set_lobias(lob)
    try:
        r = LM.stability(C.OUT / 'stab_lf', 'extpr', c, deg='lowr', f1=5e6, f2=1e9, ppd=400, **k)
    except Exception as e:
        r = dict(error=repr(e))
    finally:
        tb.set_lobias(False)
    return dict(tag=tag, corner=c, lobias=lob, case=k, pass_cm=bool((r.get('min_re_zcm_real_mixer_ohm') or -1) >= 1.0), **r)
jobs = [(C.FF, False, PLAN[0], 'plan'), (C.FF, False, PLAN[1], 'plan low loss'), (C.FF, True, PLAN[1], 'plan low loss duplex'),
        (C.NOM, False, PLAN[1], 'plan low loss'), (C.SS, False, PLAN[1], 'plan low loss'), (C.FF, False, NEG, 'negative control (must fail)')]
rows = C.par([(lambda j=j: one(*j)) for j in jobs], 3)
(OUT / 'result.json').write_text(json.dumps(rows, indent=1, default=str))
for r in rows: print(r['tag'], r['corner'], r['lobias'], r.get('min_re_zcm_real_mixer_ohm'), r.get('error'))
