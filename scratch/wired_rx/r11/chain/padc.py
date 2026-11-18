"""Coordinator questions (PC-22): (a) does the CTLE still cover the republished pad's loss and C at 3.125 / 3.24 Gb/s at the slow and
pessimistic corners, (b) the largest pad capacitance tolerated.  LINEAR estimate (chain AC of the extracted pad r-typ/high +
COB P2 + CTLE r4 staged + sampler bank load -> peak-distortion eye, best peak code), extra C per leg added at the BOND-PAD node.
Limits as declared for the chain: eye >= 60 mVppd and >= 0.25 UI wide at 60 mVppd; T3 = 120 mVppd TX, T2 = 400 mVppd + 6 dB channel.
r10 calibration of this estimate against clocked transients: one bank within 2 %.
  padc.py ck [ck..]   -> padc.json   (run through ../../slot.sh)"""
import sys, json
import numpy as np
import rc11
from rc11 import ch10, L, H
res = rc11.jload('padc.json')
ac0 = ch10.ac
for ck in sys.argv[1:]:
    ch10.TCODE = rc11.TCODE[ck]
    for cx in (0, 150, 300, 450, 600, 900):
        def ac(ck_, code, banks=1, **kw):
            return ac0(ck_, code, extra=[f'CXP pdp 0 {cx}f', f'CXN pdn 0 {cx}f'] if cx else (), tag=f'{ck_}_c{code}_cx{cx}')
        ch10.ac = ac
        row = {}
        for rate in (2.5, 3.125, 3.24):
            for stim in ('T3', 'T2'):
                best, allc = ch10.pick(ck, rate * 1e9, stim)
                row[f'{rate:g}G_{stim}'] = dict(code=best['code'], eye_mVppd=float(best['eye_mVppd']), width_ui=best['width_ui_ge60'],
                                                ok=bool(best['eye_mVppd'] >= 60 and best['width_ui_ge60'] >= 0.25))
        r = ac(ck, 0); g = lambda fq: round(float(20 * np.log10(abs(np.interp(fq, r['f'], abs(r['h']))))), 2)
        row['gain_code0_dB'] = {'20M': g(20e6), '1.25G': g(1.25e9), '1.56G': g(1.5625e9), '1.62G': g(1.62e9)}
        r7 = ac(ck, 7); g7 = lambda fq: round(float(20 * np.log10(abs(np.interp(fq, r7['f'], abs(r7['h']))))), 2)
        row['gain_code7_dB'] = {'20M': g7(20e6), '1.62G': g7(1.62e9)}
        res[f'{rc11.PADV}_{ck}_cx{cx}'] = row; (H / 'padc.json').write_text(json.dumps(res, indent=1))
        print(rc11.PADV, ck, 'extra C fF', cx, {k: (v['eye_mVppd'], v['width_ui'], v['code']) for k, v in row.items() if 'G_' in k}, row['gain_code0_dB'], flush=True)
ch10.ac = ac0
