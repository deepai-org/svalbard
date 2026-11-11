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

NB = int(__import__('os').environ.get('TRIM_BITS', '5'))   # r4: 5-bit magnitude (+ sign) per LO12

TRIM_CELL = (f"""
* pt_lo_iqtrim: {NB}-bit binary varactor bank on one LO node. Bk=1 -> low C.
.subckt pt_lo_iqtrim LO {' '.join(f'B{k}' for k in range(NB))} VSS
""" + ''.join(f'XV{k} LO B{k} pt_var_nwell AREA={(1 << k) * A_UNIT:.4e}\n' for k in range(NB)) + '.ends\n')


def bits(code, v):
    """code 0..2^NB-1 = added C steps; bit set (high C) -> well at 0 V."""
    return [0.0 if (code >> k) & 1 else v for k in range(NB)]


def tb_trim(v=3.3, vt=1.65, code=8, variant='pt_spiral', trim=0, T=60e-9):
    body, an = rl.tb_chain(v=v, vt=vt, code=code, variant=variant, T=T)
    ci, cq = (trim, 0) if trim >= 0 else (0, -trim)
    add = TRIM_CELL
    for pair, c in (('i', ci), ('q', cq)):
        bv = bits(c, v)
        add += ''.join(f'VT{pair}{k} t{pair}{k} 0 {bv[k]}\n' for k in range(NB))
        tb_ = ' '.join(f't{pair}{k}' for k in range(NB))
        for n in ('p', 'n'):
            add += f'XTR{pair}{n} lo{pair}{n} {tb_} 0 pt_lo_iqtrim\n'
    body = body.replace('.tran ', add + '.tran ', 1)

    def an2(m):
        r = an(m)
        r.update(trim_code=trim, a_unit_m2=A_UNIT)
        return r
    return body, an2


# ---- I/Q amplitude trim (LO r4): per-pair trim of the CML load-supply resistor XRC ----
# The CM loop forces avg(LO) = VB, so the tail current is I = (VDD - VB)/(Rc + R'/2) and the
# swing ~ I*R': a tail-current trim alone is undone by the loop; trimming Rc moves I (and the swing)
# with the CM held.  Rc = base 14u/1u poly (~71 ohm) || 4-bit binary segments (unit = 1u/1.5u poly
# ~1.5 k in series with a 4u PMOS switch, bit k = 2^k units); reset code 6 ~ the present 55 ohm.
AT_BITS = 4


def atrim_lo_ext(ci, cq):
    import re as _re
    src = (rl.WORK / 'lo_ext.ext.spice').read_text()
    out = []
    for line in src.splitlines():
        m = _re.match(r'^XXD([IQ])_RC (\S+) VSS VDD p_ppolyf_u_1k_w18_l1$', line)
        if not m:
            out.append(line)
            continue
        pr, vs = m.group(1), m.group(2)
        c = ci if pr == 'I' else cq
        out.append(f'XATB{pr} VDD {vs} VSS ppolyf_u_1k r_width=14u r_length=1u')
        for k in range(AT_BITS):
            g = 'VSS' if (c >> k) & 1 else 'VDD'     # PMOS on when the bit is 1
            for u in range(1 << k):      # explicit units (no m= on the PDK resistor subckt)
                out.append(f'XATR{pr}{k}_{u} VDD at{pr}{k}_{u} VSS ppolyf_u_1k r_width=1u r_length=1.5u')
                out.append(f'XATS{pr}{k}_{u} at{pr}{k}_{u} {g} {vs} VDD pfet_03v3 w=4u l=0.28u')
    name = f'lo_ext_at{ci}_{cq}.ext.spice'
    (rl.WORK / name).write_text('\n'.join(out) + '\n')
    return name


def tb_atrim(v=3.3, at_i=6, at_q=6, **kw):
    body, an = rl.tb_chain(v=v, **kw)
    body = body.replace('.include lo_ext.ext.spice', '.include ' + atrim_lo_ext(at_i, at_q), 1)
    body = body.replace('.tran ', '.measure tran qamp pp v(loqp) from=%g to=%g\n.measure tran iamp pp v(loip) from=%g to=%g\n'
                        '.measure tran iamn pp v(loin) from=%g to=%g\n.tran ' % ((kw.get('T', 60e-9) - 6e-9, kw.get('T', 60e-9)) * 3), 1)

    def an2(m):
        r = an(m)
        r.update(at_i=at_i, at_q=at_q, i_pp_v=m.get('iamp'), q_pp_v=m.get('qamp'), in_pp_v=m.get('iamn'))
        if m.get('iamp') and m.get('qamp'):
            r['i_over_q_db'] = 20 * __import__('math').log10(m['iamp'] / m['qamp'])
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
    elif what == 'sweep5':      # r4: 5-bit sign-magnitude, tt; argv[2] = comma list of codes
        for t in (int(x) for x in sys.argv[2].split(',')):
            jobs.append((f'trim5_tt27_b6_c{t}', tb_trim, dict(trim=t, code=6, vt=1.65)))
    elif what == 'corners5':
        for t in (int(x) for x in sys.argv[2].split(',')):
            jobs.append((f'trim5_ss32_lhi_lowq_b0_c{t}', tb_trim, dict(trim=t, code=0, vt=1.65, variant='pt_spiral_lhi_lowq'), 'ss', 32, 3.15))
            jobs.append((f'trim5_ff22_llo_b15_c{t}', tb_trim, dict(trim=t, code=15, vt=3.0, variant='pt_spiral_llo'), 'ff', 22, 3.35))
    elif what == 'atrim':       # amplitude trim: I code sweep, Q at reset (6)
        for c in (int(x) for x in sys.argv[2].split(',')):
            jobs.append((f'atrim_tt27_b6_i{c}', tb_atrim, dict(at_i=c, code=6, vt=1.65)))
    elif what == 'atrim_corners':
        for c in (int(x) for x in sys.argv[2].split(',')):
            jobs.append((f'atrim_ss32_lhi_lowq_b0_i{c}', tb_atrim, dict(at_i=c, code=0, vt=1.65, variant='pt_spiral_lhi_lowq'), 'ss', 32, 3.15))
            jobs.append((f'atrim_ff22_llo_b15_i{c}', tb_atrim, dict(at_i=c, code=15, vt=3.0, variant='pt_spiral_llo'), 'ff', 22, 3.35))
    out = rl.go(jobs)
    if what.startswith('atrim'):
        rl.save('amptrim', out)
        return
    rl.save('iqtrim5' if what.endswith('5') else 'iqtrim', out)


if __name__ == '__main__':
    main()
