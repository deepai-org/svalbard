"""Transient bench for the wtx_serq4 core macro alone (schematic or extracted).

Same stimulus conventions as sim_wiredtx (tanh-edge sources, 150 ohm phase drivers, 1 kohm logic
drivers, 20-bit words launched T_word/4 after WCKQ rises); the serial output Y is decoded.  Used for
fast extracted iterations on the hand-placed macro before the full-block runs; the block-level
envelope still runs on the extracted pt_wiredtx (sim_wiredtx / run_all).

    python3 sim_core.py --dut ext|sch --rate 3.24e9 --bpc 4 --corner ss --temp 22 --vdd 3.15
"""
import argparse
import json
from pathlib import Path

import numpy as np

import sim_wiredtx as S
import tools

FAST = tools.GENERATED / 'fast'
DUTS = dict(sch=FAST / 'wtx_serq4.spice', ext=FAST / 'wtx_serq4.ext.spice')
PROBES = ['PH0', 'WCKQ', 'Y', 'YB', 'DP', 'DPB']
import os
EXTRA = [x for x in os.environ.get('CORE_PROBES', '').split(',') if x]   # debug: internal nets


def deck(dut, *, rate, bpc, words, word_t0, tstop, corner, temp, vdd, ser_on=2e-9, load_f=20e-15, rg=0.0):
    tw = 20 / rate
    tq = bpc / rate
    tr = min(50e-12, tq / 16)
    L = ['* wtx_serq4 core bench', tools.model_header(corner, temp), f'.include {Path(dut).name}',
         f'VDD VDD 0 {vdd}', 'VSS VSS 0 0']
    for k, ph in enumerate(('0', '90', '180', '270')):
        kk = 2.197 / tr
        p_ = f'(time-{k * tq / 4 + tr / 2:.6e})'
        L.append(f'BPH{ph} PH{ph}_drv 0 V={vdd}*(0.5+0.5*tanh({kk * tq / (2 * np.pi):.6e}'
                 f'*sin(2*3.141592653589793*{p_}/{tq:.6e})))')
        L.append(f'RPH{ph} PH{ph}_drv PH{ph} {S.R_PHASE:g}')
    for n, on in (('MQ', bpc == 4), ('MH', bpc == 2), ('MF', bpc == 1)):
        L.append(f'V{n} {n}_drv 0 {vdd if on else 0}')
        L.append(f'R{n} {n}_drv {n} {S.R_LOGIC:g}')
    L.append(S.pwl_bits('SER', 'SERQ_drv', [(0.0, 0), (ser_on, 1)], vdd))
    L.append(f'RSER SERQ_drv SERQ {S.R_LOGIC:g}')
    for i in range(20):
        tv = [(0.0, words[0][i])] + [(word_t0 + k * tw + tw / 4, w[i]) for k, w in enumerate(words)]
        L.append(S.pwl_bits(f'D{i}', f'D{i}_drv', tv, vdd))
        L.append(f'RD{i} D{i}_drv D{i} {S.R_LOGIC:g}')
    for o in ('Y', 'YB', 'DP', 'DPB'):
        L.append(f'C{o} {o} 0 {load_f}')
    L.append('CWCK WCKQ 0 30f')
    text = Path(dut).read_text()
    ports = S.ports_of(text, 'wtx_serq4')
    L.append('X0 ' + ' '.join(ports) + ' wtx_serq4')
    vecs = ' '.join(f'v({p})' for p in PROBES) + ' i(VDD)'
    if EXTRA:
        vecs = ' '.join(f'v({p})' for p in PROBES + EXTRA) + ' i(VDD)'
    tstep = 10e-12 * max(1.0, 2.5e9 / rate)
    L += ['.options reltol=1e-3 method=gear interp', f'.tran {tstep:.3e} {tstop:.6e} 0 4e-12', '.control',
          f'save {vecs}', 'set wr_singlescale', 'run', 'wrdata wave.txt ' + vecs, '.endc', '.end']
    names = PROBES + (EXTRA or [])
    return '\n'.join(L) + '\n', names + ['I_VDD']


def run(work, dut, *, rate, bpc=4, corner='typical', temp=27, vdd=3.3, nwords=10, tag='core'):
    work = Path(work)
    tw = 20 / rate
    ser_on = 2e-9
    pdir = work / f'{tag}_phase'
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / Path(dut).name).write_text(Path(dut).read_text().replace('/', '__'))
    d, names = deck(dut, rate=rate, bpc=bpc, words=[[0] * 20], word_t0=1, tstop=ser_on + 3 * tw, corner=corner,
                    temp=temp, vdd=vdd)
    (pdir / 'tb.sp').write_text(d)
    _, log = tools.ngspice(pdir, 'tb.sp')
    ab = S.sim_abort(log)
    if ab:
        return dict(ok=False, reason='abort (phase pass): ' + ab)
    w = tools.read_wrdata(pdir / 'wave.txt', names)
    rises = S.crossings(w['time'], w['WCKQ'], rising=True)
    rises = rises[rises > ser_on]
    if len(rises) < 2:
        return dict(ok=False, reason='WCKQ not running', log_tail=log[-800:])
    t0w = float(rises[0])
    bits = S.prbs7_bits(20 * nwords)
    words = [bits[20 * k:20 * k + 20] for k in range(nwords)]
    ddir = work / f'{tag}_data'
    ddir.mkdir(parents=True, exist_ok=True)
    (ddir / Path(dut).name).write_text(Path(dut).read_text().replace('/', '__'))
    tstop = t0w + (nwords + 3) * tw
    d, names = deck(dut, rate=rate, bpc=bpc, words=words, word_t0=t0w, tstop=tstop, corner=corner, temp=temp,
                    vdd=vdd)
    (ddir / 'tb.sp').write_text(d)
    _, log = tools.ngspice(ddir, 'tb.sp')
    ab = S.sim_abort(log)
    if ab:
        return dict(ok=False, reason='abort: ' + ab)
    w = tools.read_wrdata(ddir / 'wave.txt', names)
    expected = [b for wd in words for b in wd]
    ta, tb_ = t0w + 2 * tw, t0w + (nwords - 1) * tw
    res = dict(dut=str(dut.name), dut_sha256=tools.sha(dut), rate=rate, bpc=bpc, corner=corner, temp=temp, vdd=vdd,
               word_clk_period_s=float(np.mean(np.diff(rises))))
    for node, inv in (('Y', False), ('YB', True)):
        dd = S.decode(w, node, rate, ta, tb_)
        if dd is None:
            res[node] = dict(ok=False, reason='no transitions')
            continue
        b = 1 - dd['bits'] if inv else dd['bits']
        lat, err = S.align(b, expected)
        res[node] = dict(bits=int(len(b)), errors=int(err), latency=int(lat), jitter_pp_ps=round(dd['jitter_pp'] * 1e12, 1),
                         eye_width_ps=round(dd['eye_width_est'] * 1e12, 1), vmargin_v=round(dd['vertical_margin'], 3))
    # postcursor: DP must equal Y delayed by one UI
    dy = S.decode(w, 'Y', rate, ta, tb_)
    if dy is not None:
        ui = 1 / rate
        ts = np.arange(ta - (ta % ui) + (dy['cross_phase'] + ui / 2) % ui, tb_, ui)
        y = (np.interp(ts, w['time'], w['Y']) > S.VTH).astype(int)
        dp = (np.interp(ts, w['time'], w['DP']) > S.VTH).astype(int)
        res['DP_vs_Y_delayed_1ui_mismatch'] = int(np.sum(dp[1:] != y[:-1]))
    sel = w['time'] > ta
    res['idd_avg_a'] = float(-np.mean(w['I_VDD'][sel]))
    m = res.get('Y', {})
    res['ok'] = bool(m.get('errors', 1) == 0 and m.get('bits', 0) >= 20 * (nwords - 4)
                     and res.get('YB', {}).get('errors', 1) == 0)
    return res


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--dut', default='ext')
    ap.add_argument('--rate', type=float, default=3.24e9)
    ap.add_argument('--bpc', type=int, default=4)
    ap.add_argument('--corner', default='typical')
    ap.add_argument('--temp', type=float, default=27)
    ap.add_argument('--vdd', type=float, default=3.3)
    ap.add_argument('--nwords', type=int, default=10)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    tag = f'{a.dut}_{a.bpc}_{a.rate / 1e9:g}_{a.corner}_{a.temp:g}_{a.vdd:g}'
    r = run(tools.SCRATCH / 'core', DUTS[a.dut], rate=a.rate, bpc=a.bpc, corner=a.corner, temp=a.temp, vdd=a.vdd,
            nwords=a.nwords, tag=tag)
    print(json.dumps(r))
    out = Path(a.out) if a.out else tools.SCRATCH / 'core' / f'{tag}.json'
    out.write_text(json.dumps(r, indent=1))
