"""Ring-run detector for wtx_mux8 (stopped-ring interlock), schematic + standalone bench.

Four charge pumps, pump j watches windows 2j and 2j+1 (window k = PH k high and PH k+1 low = the conduction window of
slice k).  A window switch is two series PMOS; charge moves VDD -> A_j in window 2j and A_j -> N_j in window 2j+1, so
N_j is only charged while BOTH windows keep opening and closing; a long-channel NMOS (gate at VDD) discharges N_j.
The four series gates of a pump include XE(2j+1) and XD(2j+1), which are complements: no static state conducts.
RUN = all four N_j high.  Inputs are private two-inverter copies of the slice clock nodes X k (X k = NOT PH k).

    python3 det.py run '{"tag":"a","corner":"ss","temp":32,"vdd":3.15,"f":300e6}'
"""
import sys, json, math
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 's12'))
import chain as CH
from chain import tools, S
import mux8
from mux8 import fet, inv

DP = dict(buf=(0.5, 1.0), sw=1.0, ca=(4.0, 2.0), cn=(4.0, 3.0), leak=(0.3, 50.0), nleak=2, sense=(2.0, 0.5), sl=0.5)


def detector(p=None, name='wtx_rundet'):
    p = dict(DP, **(p or {}))
    L = [f'.subckt {name} ' + ' '.join(f'X{k}' for k in range(8)) + ' RUN RUNB VDD VSS']
    for k in range(8):
        L += inv(f'DA{k}', f'X{k}', f'XD{k}', *p['buf']) + inv(f'DB{k}', f'XD{k}', f'XE{k}', *p['buf'])
    for j in range(4):
        a, b, c = 2 * j, 2 * j + 1, (2 * j + 2) % 8
        L += fet(f'P1{j}', 'p', f'M1{j}', f'XE{a}', 'VDD', p['sw']) + fet(f'P2{j}', 'p', f'A{j}', f'XD{b}', f'M1{j}', p['sw'])
        L += fet(f'P3{j}', 'p', f'M2{j}', f'XE{b}', f'A{j}', p['sw']) + fet(f'P4{j}', 'p', f'N{j}', f'XD{c}', f'M2{j}', p['sw'])
        L += fet(f'CA{j}', 'n', 'VSS', f'A{j}', 'VSS', p['ca'][0], l=p['ca'][1]) + fet(f'CN{j}', 'n', 'VSS', f'N{j}', 'VSS', p['cn'][0], l=p['cn'][1])
        prev = f'N{j}'
        for i in range(p['nleak']):
            nxt = 'VSS' if i == p['nleak'] - 1 else f'LK{j}_{i}'
            L += fet(f'LK{j}_{i}', 'n', prev, 'VDD', nxt, p['leak'][0], l=p['leak'][1]); prev = nxt
        # sense inverter: long weak PMOS, strong NMOS -> low threshold is NOT wanted (N must be well up): symmetric-high
        L += fet(f'SN{j}', 'n', f'RB{j}', f'N{j}', 'VSS', p['sense'][0], l=p['sl']) + fet(f'SP{j}', 'p', f'RB{j}', f'N{j}', 'VDD', p['sense'][1], l=p['sl'])
    # RUN = NOR4(RB) as NOR2-NAND2-INV
    L += mux8.nor2('R01', 'RB0', 'RB1', 'R01', 1, 4) + mux8.nor2('R23', 'RB2', 'RB3', 'R23', 1, 4)
    L += mux8.nand2('RN', 'R01', 'R23', 'RUNB', 1, 2) + inv('RI', 'RUNB', 'RUN', 1, 2)
    return '\n'.join(L + [f'.ends {name}']) + '\n'


def phase_src(k, f, vdd, t0, tstop_run, static, mid=None, tr=80e-12, jit=0.0):
    """X k source (rail to rail, X = NOT PH): running until tstop_run, then held at `static` bit k (or mid level)."""
    T = 1 / f; td = t0 + k * T / 8
    hold = (mid if (mid is not None and (static >> k & 1) == 2) else vdd * (1 - (static >> k & 1)))   # X = !PH
    run = f'{vdd}*(0.5-0.5*tanh({2.197 / tr * T / (2 * math.pi):.5e}*sin(2*3.141592653589793*(time-{td:.6e})/{T:.6e})))'
    g = f'(0.5-0.5*tanh((time-{tstop_run:.6e})/50p))'
    return f'BX{k} X{k} 0 V={run}*{g}+{hold}*(1-{g})'


def run(tag, corner='ss', temp=32, vdd=3.15, f=300e6, trun=300e-9, tstop=900e-9, static=0b00001111, par=None, kill=None,
        stuckval=0, ramp=None, **_):
    work = HERE / 'runs' / tag; work.mkdir(parents=True, exist_ok=True)
    res = {'ss': 'ss', 'ff': 'ff'}.get(corner, 'typical')
    L = ['* run detector bench', CH.pad_header(corner, temp, res), detector(par)]
    L += [f'VDD VDD 0 {vdd}' if not ramp else f'VDD VDD 0 PWL(0 0 {ramp} {vdd})', 'VSS VSS 0 0']
    for k in range(8):
        if kill == k:
            L.append(f'VX{k} X{k} 0 {vdd * (1 - stuckval)}')
        else:
            L.append(phase_src(k, f, vdd, 5e-9, trun, static))
    L += ['XD ' + ' '.join(f'X{k}' for k in range(8)) + ' RUN RUNB VDD VSS wtx_rundet', 'CR RUN 0 5f']
    pr = ['RUN', 'xd.N0', 'xd.N1', 'xd.N2', 'xd.N3', 'xd.A0', 'X0']
    vec = ' '.join(f'v({x})' for x in pr) + ' i(VDD)'
    L += ['.options reltol=1e-3 method=gear rshunt=1e12', f'.tran 20p {tstop:.4e} 0 20p', '.control', f'save {vec}', 'set wr_singlescale',
          'run', f'wrdata wave.txt {vec}', '.endc', '.end']
    (work / 'tb.sp').write_text('\n'.join(L) + '\n')
    tools.ngspice_host(work, 'tb.sp', timeout=3000)
    w = tools.read_wrdata(work / 'wave.txt', pr + ['I']); t = w['time']
    m = (t > trun - 30e-9) & (t < trun - 2e-9)
    out = dict(tag=tag, corner=corner, temp=temp, vdd=vdd, f=f, static=static, kill=kill,
               run_before=round(float(w['RUN'][m].min()), 3), n_min=[round(float(w[f'xd.N{j}'][m].min()), 3) for j in range(4)],
               n_max=[round(float(w[f'xd.N{j}'][m].max()), 3) for j in range(4)])
    up = S.crossings(t, w['RUN'], th=vdd / 2, rising=True); dn = S.crossings(t, w['RUN'], th=vdd / 2, rising=False)
    out['t_on_ns'] = round(float(up[0] - 5e-9) * 1e9, 1) if len(up) else None
    out['t_off_ns'] = round(float(dn[dn > trun][0] - trun) * 1e9, 1) if len(dn[dn > trun]) else None
    out['run_end'] = round(float(w['RUN'][-1]), 3)
    out['i_run_ua'] = round(float(-np.mean(w['I'][m])) * 1e6, 2); out['i_end_ua'] = round(float(-w['I'][-1]) * 1e6, 3)
    (work / 'result.json').write_text(json.dumps(out)); (work / 'wave.txt').unlink()
    return out


if __name__ == '__main__':
    print(json.dumps(run(**json.loads(sys.argv[2]))), flush=True)
