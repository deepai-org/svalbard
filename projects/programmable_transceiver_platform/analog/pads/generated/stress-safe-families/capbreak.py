#!/usr/bin/env python3
"""Item 5: wired pad capacitance breakdown at 1.25 GHz (extracted pad models, all controls off, VDD 3.3 V,
PAD_P at DC 1.65 V with AC 1 V, PAD_N AC-grounded). Variants remove one contributor class from the inner
subckt and report the C drop (contributor = full - variant). Diagnostic only.
    python3 capbreak.py <family> <model> <out.json> [corner:temp ...]"""
import json
import re
import sys
from pathlib import Path

import numpy as np

PADS = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
sys.path.insert(0, str(PADS))
import stress_safe_clamp as s  # noqa: E402
import stress_safe_family_sims as f  # noqa: E402

F = 1.25e9
W = Path(__file__).resolve().parent / 'capwork'


def inner_bounds(lines):
    i = next(k for k, l in enumerate(lines) if l.startswith('.subckt ') and 'ESD_RAIL' in l.split()[2:])
    j = next(k for k in range(i, len(lines)) if lines[k].startswith('.ends'))
    return i, j


def variants(model):
    lines = model.splitlines(); i, j = inner_bounds(lines)
    body = lines[i + 1:j]
    pad_res = [l.split()[0] for l in body if l.startswith('X') and len(l.split()) > 4 and 'PAD_P' in l.split()[1:3]
               and re.search(r'ppolyf|rnpoly|rpoly|nplus_|pplus_', l.split()[4])]

    def drop(pred):
        return '\n'.join(lines[:i + 1] + [l for l in body if not pred(l)] + lines[j:]) + '\n'
    v = {'full': model,
         'no_wire_C': drop(lambda l: l.startswith('C') and 'PAD_P' in l.split()[1:3]),
         'no_steering_diodes': drop(lambda l: l[:1] in 'DX' and 'PAD_P' in l.split()[1:3] and re.search(r'diode_(pd2nw|nd2ps)_06v0', l)),
         'no_mos_on_pad': drop(lambda l: l.startswith('X') and len(l.split()) > 5 and l.split()[5] in f.MOS and 'PAD_P' in l.split()[1:4])}
    for r in pad_res:   # cut one resistor branch at a time (the branch's C behind the resistor disappears)
        v[f'cut_{r}'] = drop(lambda l, r=r: l.split()[:1] == [r])
    return v


def cap(fam, text, cell, ports, corner, temp, name, on=()):
    d = f.header() + text + 'VSS VSS 0 0\nVDD VDD 0 3.3\nRATB ATB 0 10meg\n'
    for p in ports:
        if p in ('PAD_P', 'PAD_N', 'VSS', 'VDD', 'ATB_ESD_RAIL'):
            continue
        if p in ('RX_P', 'RX_N'):
            d += f'CCORE_{p} {p} 0 50f\nRCORE_{p} {p} 0 1g\n'; continue
        if p == 'VCM' or p == 'TERM_VCM':
            d += f'V{p} {p} 0 1.65\n'; continue
        d += f'V{p} {p} ' + ('VDD 0' if (p in f.HIGH_DEFAULT or p in on) else '0 0') + '\n'
    d += 'Xpad ' + ' '.join('ATB' if p == 'ATB_ESD_RAIL' else p for p in ports) + f' {cell}\n'
    d += f'VACP PAD_P 0 DC 1.65 AC 1\nVACN PAD_N 0 DC 1.65\n'
    d = s.corner(d, corner, temp) + s.control(W, name, f'ac lin 1 {F} {F}', 'i(VACP)')
    x = np.atleast_2d(s.run(W, name, d, timeout_s=1200))
    y = complex(x[0, 1], x[0, 2])
    return abs(y.imag) / (2 * np.pi * F)


def main():
    fam, model, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    corners = sys.argv[4:] or ['typical:27']
    f.DRAWN_SHUNT = True; f.FAMILIES.update(f.FAMILIES_V4)
    f.FAMILIES[fam] = dict(f.FAMILIES[fam], model=model.resolve())
    text, cell, ports = f.model_text(fam)
    res = dict(family=fam, model=str(model), f_hz=F, results={})
    for c in corners:
        pr, t = c.split(':'); r = {}
        for k, v in variants(text).items():
            r[k] = cap(fam, v, cell, ports, pr, int(t), f'cb_{fam}_{k}_{pr}_{t}')
        if 'TERM_ENABLE' in ports:   # terminated state (the RL-relevant one for a terminated receiver/driver)
            r['term_on'] = cap(fam, text, cell, ports, pr, int(t), f'cb_{fam}_termon_{pr}_{t}', on=('TERM_ENABLE',))
        full = r['full']
        res['results'][c] = dict(C_pF={k: round(v * 1e12, 4) for k, v in r.items()},
                                 contribution_pF={k: round((full - v) * 1e12, 4) for k, v in r.items() if k not in ('full', 'term_on')})
        print(c, json.dumps(res['results'][c]), flush=True)
        out.write_text(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
