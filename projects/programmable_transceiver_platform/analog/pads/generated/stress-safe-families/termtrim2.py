#!/usr/bin/env python3
"""Item 5b, design 2: poly-dominated, segmented on-die termination with a 4-bit trim (wirepad).
Per leg 29 identical unit legs PAD -> ppolyf_u (2 x LU um) -> U_i -> nfet_03v3 (WS/0.28 um, gate TERM_GATE_x)
-> TERM_VCM; 14 base units always on with TERM_ENABLE, 15 trim units on per TERM_TRIM[3:0] (binary 1/2/4/8),
the rest gated off (their C stays). Replaces the drawn 16/1.3 ppolyf_u strap + 8 x 20 um switches in the
extracted wirepad model (the strap's extracted coupling C is left in: conservative). Benches: stress_safe_usb
'term' (8.9 mA, R = (V(PAD_P) - VCM)/8.9 mA) at TERM_VCM 0 and 1.0 V, and the 1.25/2.4 GHz C with term on/off.
    python3 termtrim2.py <LU> <WS> <out.json>"""
import json
import re
import sys
from pathlib import Path

import numpy as np

PADS = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
sys.path.insert(0, str(PADS))
import stress_safe_clamp as s  # noqa: E402
import stress_safe_usb as u  # noqa: E402

L = Path(__file__).resolve().parent
BASE = L / 'v2/wired_receive_usb/pad/physical.spice'
W = L / 'trim2work'
NB, NT = 14, 15   # base units (argv[4] overrides), binary trim units


def variant(k, lu, ws):
    t = re.sub(r'\n\+\s*', ' ', BASE.read_text()); out = []; dropped = 0; cur = None
    for l in t.splitlines():
        f = l.split()
        if l.startswith('.subckt'):
            cur = f
        if l.startswith('X') and len(f) > 5 and f[5] == 'nfet_03v3' and f[2] in ('TERM_GATE_P', 'TERM_GATE_N') and f[3] == 'TERM_VCM':
            dropped += 1; continue
        if l.startswith('X') and len(f) > 4 and f[4] == 'ppolyf_u' and set(f[1:3]) in ({'PAD_P', 'TERM_P_R'}, {'PAD_N', 'TERM_N_R'}):
            dropped += 1; continue
        if l.startswith('.ends') and cur and 'ESD_RAIL' in cur[2:] and not any(x.startswith('XTU_') for x in out[-3:]):
            n_on = NB + k
            for leg in ('P', 'N'):
                for i in range(NB + NT):
                    g = f'TERM_GATE_{leg}' if i < n_on else 'VSS'
                    out.append(f'XTUR_{leg}{i} PAD_{leg} TU_{leg}{i} VSS ppolyf_u r_width=2u r_length={lu}u')
                    out.append(f'XTU_{leg}{i} TU_{leg}{i} {g} TERM_VCM VSS nfet_03v3 w={ws}u l=0.28u ad={0.44*ws:.4g}p as={0.44*ws:.4g}p pd={2*ws+0.88:.4g}u ps={2*ws+0.88:.4g}u')
        out.append(l)
    if dropped != 18 or sum(x.startswith('XTU_') for x in out) != 2 * (NB + NT):
        raise ValueError(f'expected 16 switches + 2 straps, dropped {dropped}')
    p = W / f'wp_k{k}_{lu}_{ws}_{NB}.spice'; W.mkdir(exist_ok=True); p.write_text('\n'.join(out) + '\n')
    return p


def term(model, pr, t, vdd, vcm, name):
    u.WIREPAD_MODEL = model; u.MIRROR_BIAS = True
    d, _ = u.deck('term', pr, t, vdd, W, name)
    if vcm:
        d = d.replace('VTERM_VCM TERM_VCM 0 0\n', f'VTERM_VCM TERM_VCM 0 {vcm}\n')
    x = np.atleast_2d(s.run(W, name, d, timeout_s=1200))
    return (float(x[0, 1]) - vcm) / 8.9e-3


def cap(model, pr, t, name, on):
    u.WIREPAD_MODEL = model
    d, _ = u.deck('cap', pr, t, 3.3, W, name)
    if on:
        d = d.replace('VTERM_ENABLE TERM_ENABLE 0 0\n', 'VTERM_ENABLE TERM_ENABLE 0 3.3\n').replace('VTERM_VCM TERM_VCM 0 0\n', 'VTERM_VCM TERM_VCM 0 1.65\n')
    d = d.replace('ac lin 1 1e9 1e9', 'ac lin 2 1.25e9 2.4e9')
    x = np.atleast_2d(s.run(W, name, d, timeout_s=1200))
    return {f'{x[i,0]/1e9:g}GHz': float(abs(complex(x[i, 1], x[i, 2]).imag) / (2 * np.pi * x[i, 0])) * 1e12 for i in range(len(x))}


def main():
    global NB
    lu, ws, rep = float(sys.argv[1]), float(sys.argv[2]), Path(sys.argv[3])
    if len(sys.argv) > 4:
        NB = int(sys.argv[4])
    out = dict(scope=__doc__.strip(), unit=dict(poly='ppolyf_u 2 x %g um' % lu, switch='nfet_03v3 %g/0.28 um' % ws, base=NB, trim=NT), codes={}, cap={})
    for k in (0, 4, 8, 12, 15):
        m = variant(k, lu, ws); r = {}
        for pr, t, vdd in (('typical', 27, 3.3), ('ss', 32, 3.15), ('ss', 22, 3.15), ('ff', 22, 3.35), ('ff', 32, 3.35)):
            for vcm in (0., 0.5, 1.0):
                r[f'{pr}_{t}_{vdd}_vcm{vcm:g}'] = round(term(m, pr, t, vdd, vcm, f't2_{k}_{lu}_{ws}_{NB}_{pr}_{t}_{vdd}_{vcm:g}'), 2)
        out['codes'][str(k)] = r; print(k, json.dumps(r), flush=True)
        rep.write_text(json.dumps(out, indent=1))
    m = variant(8, lu, ws)
    for pr, t in (('typical', 27), ('ff', 32)):
        out['cap'][f'{pr}_{t}'] = dict(off=cap(m, pr, t, f't2c_off_{lu}_{ws}_{NB}_{pr}_{t}', False), on=cap(m, pr, t, f't2c_on_{lu}_{ws}_{NB}_{pr}_{t}', True))
    rep.write_text(json.dumps(out, indent=1)); print(json.dumps(out['cap']))


if __name__ == '__main__':
    main()
