#!/usr/bin/env python3
"""IX-3 / S7: die-level differential return loss of the wired pads, 0.1-3 GHz, from the extracted pad models.
Termination on (TERM_ENABLE = VDD, TERM_VCM 1.65 V; wirepad RX path; txpad driver idle/off), VDD 3.3 V, all other
controls off. Differential AC drive (PAD_P +0.5, PAD_N -0.5 around 1.65 V): Zdiff = V/I, RL vs 100 ohm.
Also reports the equivalent shunt C (Im(Ydiff)/w, per leg = 2x) and the C-only bound RL(C) for 50 ohm per leg.
No package/COB chain (die only).    python3 rlsweep.py <family> <model> <out.json> [corner:temp ...]"""
import json
import sys
from pathlib import Path

import numpy as np

PADS = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
sys.path.insert(0, str(PADS))
import stress_safe_clamp as s  # noqa: E402
import stress_safe_family_sims as f  # noqa: E402

W = Path(__file__).resolve().parent / 'rlwork'


def run(fam, text, cell, ports, pr, t):
    name = f'rl_{fam}_{pr}_{t}'
    d = f.header() + text + 'VSS VSS 0 0\nVDD VDD 0 3.3\nRATB ATB 0 10meg\n'
    for p in ports:
        if p in ('PAD_P', 'PAD_N', 'VSS', 'VDD', 'ATB_ESD_RAIL'):
            continue
        if p in ('RX_P', 'RX_N'):
            d += f'CCORE_{p} {p} 0 50f\nRCORE_{p} {p} 0 1g\n'; continue
        if p in ('VCM', 'TERM_VCM'):
            d += f'V{p} {p} 0 1.65\n'; continue
        on = p in f.HIGH_DEFAULT or p == 'TERM_ENABLE'
        d += f'V{p} {p} ' + ('VDD 0' if on else '0 0') + '\n'
    d += 'Xpad ' + ' '.join('ATB' if p == 'ATB_ESD_RAIL' else p for p in ports) + f' {cell}\n'
    d += 'VACP PAD_P 0 DC 1.65 AC 0.5\nVACN PAD_N 0 DC 1.65 AC -0.5\n'
    d = s.corner(d, pr, t) + s.control(W, name, 'ac lin 59 0.1e9 3e9', 'i(VACP) i(VACN)')
    x = np.atleast_2d(s.run(W, name, d, timeout_s=1200))
    fr = x[:, 0]; ip = -(x[:, 1] + 1j * x[:, 2]); inn = -(x[:, 3] + 1j * x[:, 4])
    idiff = (ip - inn) / 2
    z = 1.0 / idiff
    g = (z - 100) / (z + 100)
    rl = -20 * np.log10(np.abs(g))
    cdiff = (1 / z).imag / (2 * np.pi * fr)
    pick = lambda arr, q: float(np.interp(q, fr, arr))
    return dict(process=pr, temp_c=t, f_ghz=(fr / 1e9).round(3).tolist(), rl_db=rl.round(2).tolist(),
                rdiff_ohm_100MHz=float(z[0].real), c_per_leg_pF={f'{q/1e9:g}GHz': round(2 * pick(cdiff, q) * 1e12, 3) for q in (0.5e9, 1.25e9, 2.4e9)},
                rl_db_at={f'{q/1e9:g}GHz': round(pick(rl, q), 2) for q in (0.625e9, 1.25e9, 1.5e9, 2.4e9, 3e9)},
                rl_min_1p2_2p4GHz=float(rl[(fr >= 1.2e9) & (fr <= 2.4e9)].min()))


def main():
    fam, model, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    f.DRAWN_SHUNT = True; f.FAMILIES.update(f.FAMILIES_V4)
    f.FAMILIES[fam] = dict(f.FAMILIES[fam], model=model.resolve())
    text, cell, ports = f.model_text(fam)
    res = dict(scope=__doc__.strip(), family=fam, model=str(model), results=[])
    for c in (sys.argv[4:] or ['typical:27']):
        pr, t = c.split(':')
        r = run(fam, text, cell, ports, pr, int(t)); res['results'].append(r)
        print(fam, c, r['rdiff_ohm_100MHz'], r['c_per_leg_pF'], r['rl_db_at'], r['rl_min_1p2_2p4GHz'], flush=True)
        out.write_text(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
