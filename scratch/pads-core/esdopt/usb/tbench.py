#!/usr/bin/env python3
"""tbench.py <model.spice> <tag> [--off] [--corners all|tt]: USB HS termination per leg vs TERM_TRIM code (esdopt/usb, 2026-11-20).
Deck as stress_safe_usb.py `term` (the published PD43 method): 8.9 mA forced into the pad (PAD_P in instance A, PAD_N in instance B),
TERM_ENABLE = VDD, TERM_TRIM<k> = code bit k AND TERM_ENABLE, TERM_VCM = 0 V (pt_termination grounds it), all other controls 0,
DVDD (ring supply, candidate only) = VDD; R_leg = V(pad) / 8.9 mA, code swept 0..7 (dc on a code source driving B-sources).
Corners: tt 27 C 3.3 V + tt / ss / ff / sf / fs x 22, 32 C x 3.15, 3.35 V + ss 22 / 32 C 3.50 V (23). ss / ff move MOS, resistor, diode and
MIM together; sf / fs the MOS only (as rextract/cbench.py).  --off: TERM_ENABLE = 0 (negative control, tt only).
Output: bench/<tag>-term.json."""
import sys, json, re, argparse
from pathlib import Path
import numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
import stress_safe_clamp as s, stress_safe_family_sims as f
from loading_audit import anchor_floating_conductors
HERE = Path(__file__).resolve().parent
CORNERS = [('typical', 27, 3.3)] + [(p, t, v) for p in ('typical', 'ss', 'ff', 'sf', 'fs') for t in (22, 32) for v in (3.15, 3.35)] + [('ss', 22, 3.5), ('ss', 32, 3.5)]
I = 8.9e-3


def load(path):
    text = re.sub(r'\n\+\s*', ' ', Path(path).read_text())
    text = '\n'.join(l for l in text.splitlines() if not l.startswith('.lib '))
    text = re.sub(r'#(?=[\s=)]|$)', '_h', text, flags=re.M)
    body, _ = anchor_floating_conductors(text + '\n', 1e12)
    wrap = next(l for l in body.splitlines() if l.startswith('.subckt tx_protected_pad '))
    return body, wrap.split()[1], wrap.split()[2:]


def corner(deck, process, temp):
    if process in ('typical', 'ss', 'ff'): return s.corner(deck, process, temp)
    deck, n = re.subn(r'(sm141064\.ngspice) typical\n', rf'\1 {process}\n', deck); assert n == 1
    return deck.replace('.temp 27\n', f'.temp {temp}\n')


def deck(body, cell, ports, pr, t, vdd, W, name, en=True):
    d = f.header() + body + f'\nVDD VDD 0 {vdd}\nVSS VSS 0 0\nVTERM_VCM TERM_VCM 0 0\nVTERM_ENABLE TERM_ENABLE 0 {vdd if en else 0}\nVcode code 0 0\nRcode code 0 1k\n'
    for k in range(3):
        d += f'BTRIM{k} TERM_TRIM{k} 0 V = {vdd if en else 0} * (floor((v(code)+0.5)/{1 << k}) - 2*floor((v(code)+0.5)/{2 << k}))\n'
    for x in 'AB':
        m = {'PAD_P': f'PP{x}', 'PAD_N': f'PN{x}', 'RX_P': f'RXP{x}', 'RX_N': f'RXN{x}', 'ATB_ESD_RAIL': f'ATB{x}', 'DVDD': 'VDD'}
        for p in ports:
            if p not in m and p not in ('VDD', 'VSS', 'TERM_VCM', 'TERM_ENABLE') and not p.startswith('TERM_TRIM'):
                m[p] = f'{p}_{x}'; d += f'V{p}_{x} {p}_{x} 0 0\n'
        d += f'X{x} ' + ' '.join(m.get(p, p) for p in ports) + f' {cell}\n'
        for q in (f'RXP{x}', f'RXN{x}'): d += f'C{q} {q} 0 50f\nR{q} {q} 0 1g\n'
        if 'ATB_ESD_RAIL' in ports: d += f'RATB{x} ATB{x} 0 10meg\n'
    d += 'IPA 0 PPA DC 8.9m\nRPNA PNA 0 1g\nIPB 0 PNB DC 8.9m\nRPPB PPB 0 1g\n'
    d = corner(d, pr, t) + s.control(W, name, 'dc Vcode 0 7 1', 'v(PPA) v(PNB)')
    return d


def main():
    a = argparse.ArgumentParser(); a.add_argument('model'); a.add_argument('tag'); a.add_argument('--off', action='store_true'); a.add_argument('--corners', default='all')
    a = a.parse_args()
    body, cell, ports = load(a.model)
    W = HERE / 'benchrun' / a.tag; W.mkdir(parents=True, exist_ok=True)
    out = dict(model=str(Path(a.model).resolve()), model_sha256=s.sha(a.model), current_a=I, term={})
    cs = [('typical', 27, 3.3)] if (a.off or a.corners == 'tt') else CORNERS
    for pr, t, vdd in cs:
        name = f'term_{pr}_{t}_{vdd}' + ('_off' if a.off else '')
        x = np.atleast_2d(s.run(W, name, deck(body, cell, ports, pr, t, vdd, W, name, en=not a.off), timeout_s=3600))
        rp, rn = x[:, 1] / I, x[:, 2] / I
        out['term'][f'{pr}_{t}_{vdd}'] = dict(r_p=rp.round(3).tolist(), r_n=rn.round(3).tolist())
        print(pr, t, vdd, 'R_P', rp.round(2).tolist(), 'R_N', rn.round(2).tolist(), flush=True)
    (HERE / 'bench').mkdir(exist_ok=True); (HERE / 'bench' / f'{a.tag}-term.json').write_text(json.dumps(out, indent=1) + '\n')
    for q in W.glob('*.dat'): q.unlink()


if __name__ == '__main__':
    main()
