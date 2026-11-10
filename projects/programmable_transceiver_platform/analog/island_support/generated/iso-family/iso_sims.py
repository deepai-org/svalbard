#!/usr/bin/env python3
"""LU-02 isolation-clamp family: extracted (Magic PEX, C) function/loading checks.
iso_pd (LO/analog): (a) loading of a 2.45 GHz LO leg (ideal 0.45+-0.45 V source behind 100 ohm into a 30 fF
mixer gate) with vs without the cell, ISO=0: amplitude/phase delta; (b) ISO=1 with the driver unpowered
(source replaced by 1 Gohm to a 1.0 V 'stale' level): Y released to VSS, time to < 50 mV.
iso_clamp / iso_clamp_x4: (c) A->Y propagation (ISO=0) into 200 fF (~1 mm route + receiver) and the 50 MHz
clock duty; (d) ISO=1 with A held at 0/1.65/3.63 V (floating/back-powered island): Y <= 50 mV.
Narrow functional window (tt/ss/ff x 22/32 C x 3.15/3.35 V); (d) also at 0/85 C, 3.63 V (safety)."""
import sys, json, math, re
from pathlib import Path
import numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
import stress_safe_clamp as s
W = Path(__file__).resolve().parent
PEX = W.parent / 'pex'
PDK = s.SCRATCH / 'transceiver-pad-pdk/ngspice'
F = 2.45e9
def hdr(c, t):
    return s.corner(f'.include {PDK}/design.ngspice\n.lib {PDK}/sm141064.ngspice typical\n.lib {PDK}/sm141064.ngspice res_typical\n'
                    f'.lib {PDK}/sm141064.ngspice diode_typical\n.lib {PDK}/sm141064.ngspice mimcap_typical\n.temp 27\n', c, t)
def inc(cell): return f'.include {PEX}/{cell}/{cell}.pex.spice\n'
def lo_load(c, t, with_cell):
    n = f'lo_{c}_{t}_{int(with_cell)}'
    d = hdr(c, t) + inc('iso_pd') + 'VSS VSS 0 0\nVS S 0 sin(0.45 0.45 2.45e9)\nRS S Y 100\nCG Y 0 30f\nVISO ISO 0 0\n'
    if with_cell: d += 'X1 Y ISO VSS iso_pd_pex\n'
    x = s.run(W, n, d + '.option method=gear reltol=1e-4\n' + s.control(W, n, 'tran 0.5p 4n', 'v(Y)'))
    tt = 2e-9 + np.arange(4 * 400) / (400 * F); y = np.interp(tt, x[:, 0], x[:, 1])
    ph = np.mean(y * np.exp(-2j * np.pi * F * tt)) * 2
    return abs(ph), math.degrees(np.angle(ph))
def lo_release(c, t):
    n = f'lorel_{c}_{t}'
    d = hdr(c, t) + inc('iso_pd') + 'VSS VSS 0 0\nVST ST 0 1.0\nRS ST Y 1g\nCG Y 0 30f\n.ic v(Y)=1.0\nVISO ISO 0 PWL(0 0 1n 0 1.1n 3.3)\nX1 Y ISO VSS iso_pd_pex\n'
    x = s.run(W, n, d + s.control(W, n, 'tran 1p 3n uic', 'v(Y)'))
    k = np.argmax((x[:, 0] > 1.1e-9) & (x[:, 1] < 0.05))
    return dict(t_to_50mV_ps=float((x[k, 0] - 1.1e-9) * 1e12), y_end_mV=float(x[-1, 1] * 1e3))
def clamp_delay(cell, c, t, vdd):
    n = f'cd_{cell}_{c}_{t}_{vdd}'
    d = hdr(c, t) + inc(cell) + f'VSS VSS 0 0\nVDD VDD 0 {vdd}\nVISO ISO 0 0\nVA A 0 PULSE(0 {vdd} 2n 0.1n 0.1n 9.9n 20n)\nX1 A ISO Y VDD VSS {cell}_pex\nCL Y 0 200f\n'
    x = s.run(W, n, d + s.control(W, n, 'tran 2p 45n', 'v(A) v(Y)'))
    t_, a, y = x[:, 0], x[:, 1], x[:, 2]; h = vdd / 2
    def cross(v, rising, after):
        m = (t_ > after) & ((v > h) if rising else (v < h)); return t_[np.argmax(m)]
    tr = cross(y, True, 22e-9) - cross(a, True, 22e-9); tf = cross(y, False, 32e-9) - cross(a, False, 32e-9)
    return dict(tpd_rise_ps=float(tr * 1e12), tpd_fall_ps=float(tf * 1e12), y_high_V=float(y[(t_ > 28e-9) & (t_ < 31e-9)].mean()))
def clamp_hold(cell, c, t, vdd, va):
    n = f'ch_{cell}_{c}_{t}_{vdd}_{va}'
    d = hdr(c, t) + inc(cell) + f'VSS VSS 0 0\nVDD VDD 0 {vdd}\nVISO ISO 0 {vdd}\nVA AS 0 {va}\nRA AS A 1meg\nX1 A ISO Y VDD VSS {cell}_pex\nCL Y 0 200f\n'
    x = s.run(W, n, d + s.control(W, n, 'tran 10p 20n', 'v(Y) i(VDD)'))
    return dict(y_max_mV=float(np.abs(x[x[:, 0] > 5e-9, 1]).max() * 1e3), idd_uA=float(-x[-1, 2] * 1e6))
res = dict(cells={k: str(PEX / k / f'{k}.pex.spice') for k in ('iso_pd', 'iso_clamp', 'iso_clamp_x4')}, lo={}, lo_release={}, delay={}, hold={})
FUN = [(c, t, v) for c in ('typical', 'ss', 'ff') for t in (22, 32) for v in (3.15, 3.35)]
for c in ('typical', 'ss', 'ff'):
    for t in (22, 32):
        a0, p0 = lo_load(c, t, False); a1, p1 = lo_load(c, t, True)
        res['lo'][f'{c}_{t}'] = dict(amp_ratio_dB=20 * math.log10(a1 / a0), phase_delta_deg=p1 - p0)
        res['lo_release'][f'{c}_{t}'] = lo_release(c, t)
for cell in ('iso_clamp', 'iso_clamp_x4'):
    for c, t, v in FUN:
        res['delay'][f'{cell}_{c}_{t}_{v}'] = clamp_delay(cell, c, t, v)
    for c, t, v in [('typical', 27, 3.3), ('ss', 0, 3.63), ('ff', 85, 3.63), ('ss', 85, 3.15)]:
        for va in (0, 1.65, 3.63):
            res['hold'][f'{cell}_{c}_{t}_{v}_A{va}'] = clamp_hold(cell, c, t, v, va)
(W / 'iso-sims.json').write_text(json.dumps(res, indent=1))
lo = res['lo'].values(); dl = res['delay'].values(); hd = res['hold'].values()
print('LO worst amp dB', min(r['amp_ratio_dB'] for r in lo), 'phase', max(abs(r['phase_delta_deg']) for r in lo))
print('release worst ps', max(r['t_to_50mV_ps'] for r in res['lo_release'].values()))
print('delay worst ps', max(max(r['tpd_rise_ps'], r['tpd_fall_ps']) for r in dl), 'hold worst mV', max(r['y_max_mV'] for r in hd))
