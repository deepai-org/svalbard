#!/usr/bin/env python3
"""D-LO-2 LO I/Q phase-trim feasibility bench (LO owner, 2026-11-11).

Trim element (proposed cell pt_lo_iqtrim, schematic in this file): a 4-bit binary
bank of NMOS-in-n-well accumulation varactors (the PDK cap_nmos_03v3_b model,
same charge-conserving wrapper pt_var_nwell as the QVCO tank) hung on each
LO_* mixer-gate node of pt_lo_ext.  The varactor gate is the LO node; the n-well
is driven by a digital trim bit: bit = 0 -> well at 0 V (gate ~2.3 V above the
well: accumulation, high C); bit = 1 -> well at VDD (depletion, low C).  No
series switch, so no switch R and no off-state junction C beyond the well.
The LO node is the one point common to BOTH LO modes (internal CML driver and
the external pad path), so one trim covers the QVCO chain and the COB hybrid.

Sign: positive code adds C on the I pair (delays I, Q-I moves toward -90 +
code), negative on the Q pair.  The other pair stays at code 0 (all bits low-C).

    python3 run_lotrim.py sweep          # tt chain, codes -15..+15 subset
    python3 run_lotrim.py corners        # code 0 / +-15 at ss and ff extremes
Results: lcvco/results.json key 'iqtrim'.  Decks: scratch/timing/lcvco/sim.
"""
import json
import sys

import run_lcvco as rl

A_UNIT = float(__import__('os').environ.get('TRIM_AUNIT', '4e-12'))   # m^2 per LSB varactor

TRIM_CELL = f"""
* pt_lo_iqtrim: 4-bit binary varactor bank on one LO node. Bk=1 -> low C.
.subckt pt_lo_iqtrim LO B0 B1 B2 B3 VSS
XV0 LO B0 pt_var_nwell AREA={A_UNIT:.4e}
XV1 LO B1 pt_var_nwell AREA={2 * A_UNIT:.4e}
XV2 LO B2 pt_var_nwell AREA={4 * A_UNIT:.4e}
XV3 LO B3 pt_var_nwell AREA={8 * A_UNIT:.4e}
.ends
"""


def bits(code, v):
    """code 0..15 = added C steps; bit set (high C) -> well at 0 V."""
    return [0.0 if (code >> k) & 1 else v for k in range(4)]


def tb_trim(v=3.3, vt=1.65, code=8, variant='pt_spiral', trim=0, T=60e-9):
    body, an = rl.tb_chain(v=v, vt=vt, code=code, variant=variant, T=T)
    ci, cq = (trim, 0) if trim >= 0 else (0, -trim)
    add = TRIM_CELL
    for pair, c in (('i', ci), ('q', cq)):
        bv = bits(c, v)
        add += ''.join(f'VT{pair}{k} t{pair}{k} 0 {bv[k]}\n' for k in range(4))
        for n in ('p', 'n'):
            add += f'XTR{pair}{n} lo{pair}{n} t{pair}0 t{pair}1 t{pair}2 t{pair}3 0 pt_lo_iqtrim\n'
    body = body.replace('.tran ', add + '.tran ', 1)

    def an2(m):
        r = an(m)
        r.update(trim_code=trim, a_unit_m2=A_UNIT)
        return r
    return body, an2


def main():
    rl.stage()
    what = sys.argv[1]
    jobs = []
    if what == 'sweep':
        for t in (int(x) for x in (sys.argv[2].split(',') if len(sys.argv) > 2 else '0,4,15,-4,-15'.split(','))):
            jobs.append((f'trim_tt27_b6_c{t}', tb_trim, dict(trim=t, code=6, vt=1.65)))
    elif what == 'corners':
        for t in (0, 15, -15):
            jobs.append((f'trim_ss32_lhi_lowq_b0_c{t}', tb_trim, dict(trim=t, code=0, vt=1.65, variant='pt_spiral_lhi_lowq'), 'ss', 32, 3.15))
            jobs.append((f'trim_ff22_llo_b15_c{t}', tb_trim, dict(trim=t, code=15, vt=3.0, variant='pt_spiral_llo'), 'ff', 22, 3.35))
    out = rl.go(jobs)
    rl.save('iqtrim', out)


if __name__ == '__main__':
    main()
