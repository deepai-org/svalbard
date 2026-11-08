"""Extracted checks for pt_wtx_hsbias: code transfer (tt and corners), disabled
state, and settling of a full-scale code step into the wirepad HS_PBIAS load
(28 x pfet_03v3 20/1 gates, sources at VDD, plus 0.3 pF routing)."""
from pathlib import Path
import sim_wiredtx as S
import tools

LOAD = 'XLD HSD HS_PBIAS VDD VDD pfet_03v3 w=20u l=1u m=28\nVHSD HSD 0 0\nCRT HS_PBIAS 0 0.3p'


def deck(dut, corner, temp, vdd, body):
    L = ['* hsbias', tools.model_header(corner, temp), f'.include {Path(dut).name}', f'VDD VDD 0 {vdd}', 'VSS VSS 0 0',
         'BREF 0 IBIAS I=10u*(1-exp(-max(3.3-v(IBIAS),0)/0.1))', 'VEN EN 0 {}'.format(vdd), LOAD]
    L += [f'VC{k} C{k} 0 0' for k in range(8)]
    L.append('X0 IBIAS EN ' + ' '.join(f'C{k}' for k in range(8)) + ' HS_PBIAS VDD VSS pt_wtx_hsbias')
    return '\n'.join(L + body + ['.end']) + '\n'


def sweep(work, dut, corner='typical', temp=27, vdd=3.3, codes=(0, 1, 2, 16, 64, 128, 192, 255)):
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    (work / Path(dut).name).write_text(Path(dut).read_text())
    body = ['.control']
    for c in codes:
        body += [f'alter VC{k} dc = {((c >> k) & 1) * vdd}' for k in range(8)]
        body += ['op', f'echo CODE {c} $&v(HS_PBIAS) $&i(VDD) $&i(VHSD)']
    body += ['alter VEN dc = 0', 'op', 'echo OFF $&v(HS_PBIAS) $&i(VDD) $&i(VHSD)', '.endc']
    tag = f'sw_{corner}_{temp}_{vdd}'
    (work / f'{tag}.sp').write_text(deck(dut, corner, temp, vdd, body))
    _, log = tools.ngspice(work, f'{tag}.sp')
    rows, off = [], None
    for l in log.splitlines():
        p = l.split()
        if l.startswith('CODE '):
            rows.append(dict(code=int(p[1]), v_hs_pbias=float(p[2]), i_vdd_a=-float(p[3]), i_hs_mirror_a=float(p[4])))
        if l.startswith('OFF '):
            off = dict(v_hs_pbias=float(p[1]), i_vdd_a=-float(p[2]), i_hs_mirror_a=float(p[3]))
    lsb = [(b['v_hs_pbias'] - a['v_hs_pbias']) / (b['code'] - a['code']) for a, b in zip(rows, rows[1:])]
    return dict(corner=corner, temp_c=temp, vdd=vdd, rows=rows, disabled=off,
                full_scale_v=rows[-1]['v_hs_pbias'] if rows else None,
                max_lsb_mv=round(max(lsb) * 1e3, 3) if lsb else None, monotonic=all(x > 0 for x in lsb))


def settle(work, dut, corner='typical', temp=27, vdd=3.3):
    """Code 64 -> 192 step at 1 us (bias already settled); settling to 1 LSB."""
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    (work / Path(dut).name).write_text(Path(dut).read_text())
    body = []
    d = deck(dut, corner, temp, vdd, body)
    for k in range(8):
        a, b = (64 >> k) & 1, (192 >> k) & 1
        d = d.replace(f'VC{k} C{k} 0 0', f'VC{k} C{k} 0 PWL(0 {a*vdd} 1u {a*vdd} 1.001u {b*vdd})')
    d = d.replace('.end\n', '.control\ntran 2n 3u\nmeas tran vfin find v(HS_PBIAS) at=2.99u\n'
                  'meas tran v0 find v(HS_PBIAS) at=0.99u\nwrdata st.txt v(HS_PBIAS)\n.endc\n.end\n')
    (work / 'settle.sp').write_text(d)
    _, log = tools.ngspice(work, 'settle.sp')
    import numpy as np
    w = np.loadtxt(work / 'st.txt')
    vfin = w[-1, 1]
    v0 = w[np.searchsorted(w[:, 0], 0.99e-6), 1]
    lsb = abs(vfin - v0) / 128
    out = np.nonzero(np.abs(w[:, 1] - vfin) > lsb)[0]
    t_last = w[out[-1], 0] if len(out) else 0.0
    return dict(step='code 64 -> 192 at 1.0 us', v_before=float(v0), v_after=float(vfin), lsb_v=float(lsb),
                settle_to_1lsb_s=float(t_last - 1.0e-6), spec_s=1e-6)
