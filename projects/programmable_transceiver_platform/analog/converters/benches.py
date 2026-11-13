"""ngspice testbenches for the converter family (run on extracted netlists).

Every bench returns raw measurements; the four-test interpretation lives in
run(). Corner grid per spec/tapeout-plan.md operating envelope: tt/ss/ff x
22/32 C x 3.15/3.35 V (not gating; recorded under performance_vs_target).
Off-state safety is also checked at 3.63 V and 85 C.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import math
import re
from pathlib import Path

import convkit as ck

CORNERS = [(p, t, v) for p in ('typical', 'ss', 'ff') for t in (22, 32) for v in (3.15, 3.35)]
NOMINAL = ('typical', 27, 3.3)
EXTREMES = [('ss', 32, 3.15), ('ff', 22, 3.35)]


def corner_list(corners):
    return CORNERS if corners is True or corners == 'all' else EXTREMES if corners == 'extremes' else []


def header(netlist, corner, temp, vdd):
    return (f'* converter bench corner={corner} temp={temp} vdd={vdd}\n' + ck.models(corner) +
            f'.include {netlist}\n.temp {temp}\n.param vdd={vdd}\n'
            '.option method=gear reltol=1e-3\n.model dclamp d is=1e-14\n')


def meas(stdout):
    out = {}
    for line in stdout.splitlines():
        m = re.match(r'^(\w+)\s+=\s+([-+0-9.eE]+)', line)
        if m:
            out[m.group(1)] = float(m.group(2))
    return out


WORKERS = int(__import__('os').environ.get('CONV_WORKERS', '3'))   # host policy: <= 3 sim containers


def run_decks(work, decks, workers=None, timeout=7200):
    workers = workers or WORKERS
    """decks: {name: text}. Returns {name: (measurements, returncode)}."""
    def one(item):
        name, text = item
        try:
            r = ck.ngspice(work, name + '.spice', text, timeout=timeout)
        except __import__('subprocess').TimeoutExpired:
            return name, ({}, 'timeout')
        return name, (meas(r.stdout), r.returncode)
    with cf.ThreadPoolExecutor(workers) as ex:
        return dict(ex.map(one, decks.items()))


def tag(c):
    return f'{c[0]}_{c[1]}C_{c[2]}V'


# ===================================================================== refbuf
def refbuf_deck(net, corner, temp, vdd, *, top='pt_refbuf'):
    return header(net, corner, temp, vdd) + f'''
VDD VDD 0 {{vdd}}
VR0 VREF0 0 1.0
IB VDD IBIAS 10u
D1 IBIAS VDD dclamp
VEN EN 0 PWL(0 0 0.5u 0 0.501u {{vdd}})
VOVR OVR 0 PWL(0 0 12u 0 12.001u {{vdd}})
* ADC-like load: 0.3 mA DC + 1 mA x 3 ns every 25 ns (6..11 us)
ILD VREF 0 PWL(0 0 6u 0 6.01u 0.3m 11u 0.3m 11.01u 0)
ILP VREF 0 PULSE(0 1m 6u 0.2n 0.2n 3n 25n 200)
* ATB0 force through a 500 ohm switch model once overridden
VF VF 0 1.05
SF VF VREF OVR 0 swmod
.model swmod sw vt=1.6 vh=0.1 ron=500 roff=1e12
X1 VDD 0 VREF0 VREF IBIAS EN OVR READY {top}
.control
tran 2n 14u
meas tran vref_settled find v(VREF) at=5.9u
meas tran vref_load_avg avg v(VREF) from=8u to=10u
meas tran vref_load_min min v(VREF) from=8u to=10u
meas tran vref_load_max max v(VREF) from=8u to=10u
meas tran t_settle when v(VREF)=0.99 rise=1
meas tran t_ready when v(READY)=1.6 rise=1
meas tran ready_pre max v(READY) from=0.5u to=1.5u
meas tran iq avg i(VDD) from=5u to=5.9u
meas tran ioff avg i(VDD) from=0.1u to=0.45u
meas tran iovr avg i(VDD) from=13u to=14u
meas tran vref_forced find v(VREF) at=13.9u
meas tran ready_ovr find v(READY) at=13.9u
.endc
.end
'''


def refbuf_unpowered_deck(net, corner, temp, vdd, top='pt_refbuf'):
    """Island off (VDD=0) while VREF is held at 1.0 V by ATB and VREF0/IBIAS live."""
    return header(net, corner, temp, vdd) + f'''
VDD VDD 0 0
VR0 VREF0 0 1.0
VB VB 0 3.3
IB VB IBIAS 10u
D1 IBIAS VB dclamp
VF VREF 0 1.0
VEN EN 0 0
VOVR OVR 0 0
X1 VDD 0 VREF0 VREF IBIAS EN OVR READY {top}
.control
op
print i(VF) i(VDD) v(IBIAS) v(READY)
.endc
.end
'''


def refbuf_bench(c, work, corners):
    net = 'ext.spice'
    decks = {'nominal': refbuf_deck(net, *NOMINAL, top=c.name)}
    if corners:
        for cr in corner_list(corners):
            decks['c_' + tag(cr)] = refbuf_deck(net, *cr, top=c.name)
    decks['off_3v63_85C'] = refbuf_deck(net, 'ff', 85, 3.63, top=c.name).replace('tran 2n 14u', 'tran 2n 0.45u')
    res = run_decks(work, decks)
    # Unpowered-island case: plain op point.
    up = ck.ngspice(work, 'unpowered.spice', refbuf_unpowered_deck(net, 'typical', 27, 3.3, c.name))
    vals = re.findall(r'(i\(\w+\)|v\(\w+\))\s*=\s*([-+0-9.eE]+)', up.stdout)
    unpowered = {k: float(v) for k, v in vals}
    n = res['nominal'][0]
    ok = (abs(n.get('vref_settled', 0) - 1.0) < 0.02 and n.get('vref_forced', 0) > 1.04
          and n.get('t_ready', 1) < 5e-6 and n.get('ready_pre', 1) < 0.5)
    perf = [dict(metric='VREF settled (V)', target='1.0 (0.98..1.02)', nominal=n.get('vref_settled')),
            dict(metric='VREF under 0.42 mA ADC-like load, avg (V)', target='0.98..1.02',
                 nominal=n.get('vref_load_avg')),
            dict(metric='VREF ripple p-p under 1 mA x 3 ns pulses (mV)', target='not specified',
                 nominal=None if 'vref_load_max' not in n else round(1e3 * (n['vref_load_max'] - n['vref_load_min']), 2)),
            dict(metric='quiescent current (mA)', target='2 (allocation 3)', nominal=-1e3 * n.get('iq', 0)),
            dict(metric='enable to VREF within 1% (us)', target='not specified',
                 nominal=None if 't_settle' not in n else round(1e6 * (n['t_settle'] - 0.5e-6), 3)),
            dict(metric='enable to READY (us)', target='after VREF valid',
                 nominal=None if 't_ready' not in n else round(1e6 * (n['t_ready'] - 0.5e-6), 3))]
    corner_rows = {k[2:]: v[0] for k, v in res.items() if k.startswith('c_')}
    if corner_rows:
        perf.append(dict(metric='corner sweep (extracted)', target='narrow window, not gating',
                         corners={k: {m: v.get(m) for m in ('vref_settled', 'vref_load_avg', 'iq', 't_ready')}
                                  for k, v in corner_rows.items()}))
    off = res['off_3v63_85C'][0]
    tests = dict(
        safe=dict(state='pass' if (abs(n.get('ioff', 1)) < 1e-6 and abs(n.get('iovr', 1)) < 1e-6
                                   and abs(off.get('ioff', 1)) < 1e-5) else 'fail',
                  cases=[dict(case='EN=0, tt 27C 3.3V: VDD current (A)', value=n.get('ioff')),
                         dict(case='EN=0, ff 85C 3.63V: VDD current (A)', value=off.get('ioff')),
                         dict(case='OVR=1 (ATB force 1.05 V via 500 ohm): VDD current (A)', value=n.get('iovr')),
                         dict(case='OVR=1: forced VREF (V) -> buffer does not fight ATB', value=n.get('vref_forced')),
                         dict(case='island unpowered, VREF held 1.0 V, VREF0 1.0 V: op point', value=unpowered)],
                  notes='Reset state EN=0: IBIAS switch open, NB/X pulled to VSS, PMOS mirrors on an '
                        'opened header; VREF sees only NMOS junctions and gates.'),
        clean=dict(extracted_nominal={k: n.get(k) for k in ('vref_settled', 'vref_load_avg', 'iq', 't_ready',
                                                             't_settle')},
                   extracted_ok=ok, netlist='generated/refbuf.ext.spice', bench='benches.refbuf_deck'),
        observable=dict(state='pass' if n.get('t_ready', 1) < 5e-6 else 'fail',
                        atb_taps=['conv_vref (= VREF output net; ATB0 force with OVR, ATB1 sense)'],
                        status_bits=['refbuf_ready (READY): rises when VREF > VREF0 - ~30 mV'],
                        clock_obs=[]),
        fallback=dict(state='waived_core', routes=['ATB0 force / ATB1 sense on conv_vref with '
                                                     'debug.bias_override.refbuf=1 (OVR) -> buffer high-Z'],
                      bypass_loading_fF=None,
                      evidence={'vref_forced_V': n.get('vref_forced'), 'supply_A_while_forced': n.get('iovr')}))
    excluded = ['READY upper window bound (1.02) not implemented: lower bound only',
                'No noise, PSRR or Monte Carlo analysis', 'Load model is a current pulse train, not the ADC']
    return dict(tests=tests, performance=perf, excluded=excluded, raw={k: v[0] for k, v in res.items()})


# ===================================================================== dispatch
def run(block, c, work, corners=True):
    if block == 'refbuf':
        out = refbuf_bench(c, work, corners)
    elif block.startswith('dac'):
        out = dac_bench(c, work, corners)
    elif block.startswith('adc'):
        out = adc_bench(c, work, corners)
    else:
        raise ValueError(block)
    (work / 'bench-results.json').write_text(json.dumps(out, indent=2, default=str) + '\n')
    return out




# ===================================================================== ADC
def clock_sources(name_p, name_n, period, high, delay=0.0, vdd='{vdd}'):
    """Low-swing differential clock, CM 1.65 V, 0.2 V per leg; 'high' = P above N."""
    tr = 0.3e-9
    return (f'V{name_p} {name_p} 0 PULSE(1.45 1.85 {delay:.4e} {tr} {tr} {high - tr:.4e} {period:.4e})\n'
            f'V{name_n} {name_n} 0 PULSE(1.85 1.45 {delay:.4e} {tr} {tr} {high - tr:.4e} {period:.4e})\n')


def pwl(points):
    return 'PWL(' + ' '.join(f'{t:.5e} {v:.5g}' for t, v in points) + ')'


def adc_deck(net, corner, temp, vdd, *, top, inputs, period, acq, test=0, vref='VREF 0 1.0',
             t0=40e-9, extra='', sine=None, ilen=1):
    """inputs: differential volts per conversion (held across each sample).
    v3 block: ILEN=ilen; with ILEN=1 conversion i goes to core A (even i) or B (odd i)."""
    n = len(inputs)
    pts_p, pts_n = [(0, 1.65), ], [(0, 1.65)]
    for i, vd in enumerate(inputs):
        ts = t0 + i * period - 0.25 * period          # change mid-conversion of the previous one
        pts_p += [(ts, pts_p[-1][1]), (ts + 0.2e-9, 1.65 + vd / 2)]
        pts_n += [(ts, pts_n[-1][1]), (ts + 0.2e-9, 1.65 - vd / 2)]
    # interleaved: the last core needs two clock periods to deliver its code
    tstop = t0 + (n + (1 if ilen else 0)) * period + (acq if ilen else 0) + 2e-9
    t = header(net, corner, temp, vdd) + '.option klu\n'
    t += f'VDD VDD 0 {{vdd}}\nVR {vref}\nVCMS VCM 0 1.65\nIB VDD IBIAS 10u\nD1 IBIAS VDD dclamp\n'
    t += clock_sources('CLKP', 'CLKN', period, acq, delay=t0)
    t += f'VEN EN 0 PWL(0 0 10n 0 10.2n {{vdd}})\n'
    if isinstance(test, list):        # per-conversion input_test (changed while the previous converts)
        for bit, nm in ((1, 'TEST0'), (2, 'TEST1')):
            pts = [(0, 0.0)]
            for i, tv in enumerate(test):
                ts = t0 + i * period - 0.25 * period
                pts += [(ts, pts[-1][1]), (ts + 0.2e-9, 3.3 if tv & bit else 0.0)]
            t += f'V{nm} {nm} 0 {pwl(pts)}\n'
    else:
        t += f'VT0 TEST0 0 {3.3 if test & 1 else 0}\nVT1 TEST1 0 {3.3 if test & 2 else 0}\n'
    if sine:            # continuous differential tone (amplitude_diff_peak, freq)
        a, f = sine
        t += f'VIP INP 0 SIN(1.65 {a / 2:.5g} {f:.6g})\nVIN INN 0 SIN(1.65 {-a / 2:.5g} {f:.6g})\n'
    else:
        t += f'VIP INP 0 {pwl(pts_p)}\nVIN INN 0 {pwl(pts_n)}\n'
    t += extra
    t += f'VIL ILEN 0 {3.3 if ilen else 0}\n'
    t += f'X1 VDD 0 INP INN VCM VREF IBIAS CLKP CLKN EN ILEN TEST0 TEST1 ' + ' '.join(f'CODE{i}' for i in range(10)) + \
         ' DONE OVERLOAD ' + ' '.join(f'CODEB{i}' for i in range(10)) + f' DONEB OVERLOADB ATB_BIAS {top}\n'
    t += '.control\nset wr_singlescale\nset wr_vecnames\noption interp\n'
    t += f'tran 20p {tstop:.4e}\n'
    # (KLU direct solver only, same tolerances: identical codes and DONE times to
    # the default solver on the v2 extracted deck, 1.7x faster; see README.)
    t += 'meas tran idd avg i(VDD) from=%.4e to=%.4e\n' % (t0, tstop - 2e-9)
    t += 'meas tran ioff avg i(VDD) from=1n to=9n\n'
    t += 'meas tran iref avg i(VR) from=%.4e to=%.4e\n' % (t0, tstop - 2e-9)
    t += 'wrdata adc.dat v(DONE) v(OVERLOAD) ' + ' '.join(f'v(CODE{i})' for i in range(10)) + \
        ' v(DONEB) v(OVERLOADB) ' + ' '.join(f'v(CODEB{i})' for i in range(10)) + '\n'
    t += '.endc\n.end\n'
    return t, tstop


def decode(datfile, t0, period, n, acq, ilen=0):
    """ilen=0: single core (CODE*, DONE). ilen=1: conversion i on core A (even) /
    B (odd); each core's register is read just before that core's next conversion
    could complete (2 periods later)."""
    h, rows = ck.read_wrdata(datfile)
    idx = {k: i for i, k in enumerate(h)}
    out = []
    import bisect
    times = [r[0] for r in rows]
    first_b = False
    if ilen:
        # The core that receives the first SAMPLE pulse is not fixed: the clock
        # receiver can emit a short pulse when EN rises, which toggles the A/B
        # flip-flop once. The core order is taken from whichever DONE rises first
        # (the digital side orders the two code streams the same way).
        def first_rise(col):
            j = idx[col]
            for r0, r1 in zip(rows, rows[1:]):
                if r1[0] > t0 and r0[j] <= 1.65 < r1[j]:
                    return r1[0]
            return 1.0
        first_b = first_rise('v(DONEB)') < first_rise('v(DONE)')
    for i in range(n):
        b_ = 'B' if (ilen and (i % 2) != first_b) else ''
        done = 'v(DONEB)' if b_ else 'v(DONE)'
        step = 2 if ilen else 1
        ts = t0 + (i + step) * period + acq * 0.5
        k = min(max(bisect.bisect_left(times, ts), 0), len(rows) - 1)
        row = rows[k]
        bits = [row[idx[f'v(CODE{b_}{b})']] > 1.65 for b in range(10)]
        v = sum(int(b) << k for k, b in enumerate(bits))
        if v >= 512:
            v -= 1024
        # done timing within conversion i
        tdone = None
        a, b = t0 + i * period + acq, t0 + (i + step) * period
        prev = None
        for r in rows[bisect.bisect_left(times, a):bisect.bisect_right(times, b)]:
            if a <= r[0] <= b:
                hi = r[idx[done]] > 1.65
                if prev is False and hi:
                    tdone = r[0] - a
                    break
                prev = hi
        out.append(dict(code=v, t_done_after_sample_fall_ns=None if tdone is None else round(tdone * 1e9, 3),
                        overload=row[idx[f'v(OVERLOAD{b_})']] > 1.65, core='B' if b_ else 'A'))
    return out


# ===================================================================== DAC
DAC_T0 = 900e-9   # v4: + 1 pF ATB_BIAS decap (CNV-03): bias+CM loop settle ~0.9 us at ss 22-32C 3.10V (sch); v3 was 400 ns


def dac_deck(net, corner, temp, vdd, *, top, codes, period, t0=DAC_T0, hold_zero=False):
    # t0: the 67 current-source gates (~1.7 pF) + 1 pF decap charge from the 10 uA bias after EN
    """codes: signed 10-bit values, each presented for two clock periods."""
    n = len(codes)

    def bitpwl(bit):
        pts = [(0, 0.0)]
        for i, cd in enumerate(codes):
            v = 3.3 if ((cd & 0x3ff) >> bit) & 1 else 0.0
            ts = t0 + i * 2 * period + period / 2
            pts += [(ts, pts[-1][1]), (ts + 0.2e-9, v)]
        return pwl(pts)
    tstop = t0 + (n + 1) * 2 * period
    t = header(net, corner, temp, vdd)
    t += 'VDD VDD 0 {vdd}\nIB VDD IBIAS 10u\nD1 IBIAS VDD dclamp\n'
    t += clock_sources('CLKP', 'CLKN', period, period / 2)
    t += 'VEN EN 0 PWL(0 0 30n 0 30.2n {vdd})\n'
    t += f'VHZ HOLD_ZERO 0 {3.3 if hold_zero else 0}\n'
    for b in range(10):
        t += f'VC{b} CODE{b} 0 {bitpwl(b)}\n'
    t += 'CLP OUTP 0 100f\nCLN OUTN 0 100f\n'
    t += f'X1 VDD 0 OUTP OUTN IBIAS CLKP CLKN EN HOLD_ZERO ' + ' '.join(f'CODE{i}' for i in range(10)) + \
         f' ATB_BIAS {top}\n'
    t += '.control\nset wr_singlescale\nset wr_vecnames\n'
    # v4: save only what is measured (all-node saves of the 4 MB extracted netlist hit
    # ngspice's 'memory required > available' abort on the shared host)
    t += 'save v(OUTP) v(OUTN) vdd#branch\n'
    t += f'tran 50p {tstop:.4e}\n'
    for i in range(n):
        # output of code i is registered at the 2nd rising edge after it is applied
        ts = t0 + i * 2 * period + 2 * period
        tm = ts + 1.9 * period
        t += f'meas tran vcm{i} find v(OUTP) at={tm:.4e}\n'
        t += f'meas tran vn{i} find v(OUTN) at={tm:.4e}\n'
    t += f'meas tran idd avg i(VDD) from={t0:.4e} to={tstop:.4e}\nmeas tran ioff avg i(VDD) from=5n to=25n\n'
    t += 'wrdata dac.dat v(OUTP) v(OUTN)\n.endc\n.end\n'
    return t, tstop


def offload_deck(net, corner, temp, vdd, *, top, kind, node, powered):
    """AC loading (and DC leakage at 1.65 V) of an output/input node while the block is off."""
    t = header(net, corner, temp, vdd)
    t += f'VDD VDD 0 {vdd if powered else 0}\nVB VB 0 3.3\nIB VB IBIAS 10u\nD1 IBIAS VB dclamp\n'
    t += 'VEN EN 0 0\nVCLKP CLKP 0 1.65\nVCLKN CLKN 0 1.65\n'
    if kind == 'dac':
        t += 'VHZ HOLD_ZERO 0 0\n' + ''.join(f'VC{b} CODE{b} 0 0\n' for b in range(10))
        t += f'VX {node} 0 DC 1.65 AC 1\nVO OUTN 0 1.65\n' if node == 'OUTP' else ''
        t += f'X1 VDD 0 OUTP OUTN IBIAS CLKP CLKN EN HOLD_ZERO ' + ' '.join(f'CODE{i}' for i in range(10)) + \
             f' ATB_BIAS {top}\n'
    else:
        t += 'VR VREF 0 0\nVCMS VCM 0 1.65\nVT0 TEST0 0 0\nVT1 TEST1 0 0\nVIL ILEN 0 0\n'
        t += f'VX INP 0 DC 1.65 AC 1\nVO INN 0 1.65\n'
        t += f'X1 VDD 0 INP INN VCM VREF IBIAS CLKP CLKN EN ILEN TEST0 TEST1 ' + ' '.join(f'CODE{i}' for i in range(10)) + \
             ' DONE OVERLOAD ' + ' '.join(f'CODEB{i}' for i in range(10)) + f' DONEB OVERLOADB ATB_BIAS {top}\n'
    t += '.control\nop\nlet ileak = -i(VX)\nprint ileak\nac lin 1 10e6 10e6\n' \
         'let cpf = imag(-i(VX))/(2*3.14159265*10e6)*1e15\nprint cpf\nlet gin = real(-i(VX))\nprint gin\n.endc\n.end\n'
    return t


def scalar(stdout, name):
    m = re.search(rf'^{name}\s*=\s*([-+0-9.eE]+)', stdout, re.M)
    return float(m.group(1)) if m else None


def offload(work, net, top, kind, node):
    res = {}
    for powered in (True, False):
        r = ck.ngspice(work, f'off_{kind}_{int(powered)}.spice',
                       offload_deck(net, 'typical', 27, 3.3, top=top, kind=kind, node=node, powered=powered))
        res['powered_disabled' if powered else 'island_unpowered'] = dict(
            leak_A_at_1p65V=scalar(r.stdout, 'ileak'), cap_fF_at_10MHz=scalar(r.stdout, 'cpf'),
            conductance_S=scalar(r.stdout, 'gin'))
    return res


CLEAN_LSB = 4          # 1 LSB at 8 bit, in 10-bit codes (ADC and DAC 'clean')
ADC_OFF_CAP_FF = 100   # ADC input loading when disabled/unpowered (fallback)

DAC_CODES = [-512, -384, -256, -128, -1, 0, 1, 127, 255, 383, 511, 100, -100]
DAC_CORNER_CODES = [-512, -256, 0, 255, 511]
DAC_NOMINAL_CHUNKS = [[-512, 511, -384, -256, -128], [-512, 511, -1, 0, 1], [-512, 511, 127, 255, 383],
                      [-512, 511, 100, -100]]
DAC_SINE_BIN = 7
DAC_SINE = [round(480 * math.sin(2 * math.pi * DAC_SINE_BIN * k / 64)) for k in range(64)]


def dac_eval(m, codes, n):
    if any(m.get(f'vcm{i}') is None or m.get(f'vn{i}') is None for i in range(n)):
        return None
    vd = [m[f'vcm{i}'] - m[f'vn{i}'] for i in range(n)]
    lo, hi = vd[codes.index(-512)], vd[codes.index(511)]
    lsb = (hi - lo) / 1023
    err = [round((v - lo) / lsb - (cd + 512), 3) for v, cd in zip(vd, codes)]
    return dict(fullscale_diff_V=[round(lo, 4), round(hi, 4)], lsb_mV=round(lsb * 1e3, 4),
                code_error_lsb=dict(zip(map(str, codes), err)),
                cm_V=round(sum(m[f'vcm{i}'] + m[f'vn{i}'] for i in range(n)) / (2 * n), 4))


def dac_bench(c, work, corners):
    net = 'ext.spice'
    period = 25e-9
    # The extracted 13-code nominal deck exceeds the 7200 s sim timeout (RC-21); run it as
    # chunks that each carry both endpoint codes (same length as the corner decks) and merge.
    decks = {f'nominal_{k}': dac_deck(net, *NOMINAL, top=c.name, codes=ch, period=period)[0]
             for k, ch in enumerate(DAC_NOMINAL_CHUNKS)}
    if corners != 'minimal':
        decks['rate80M'] = dac_deck(net, *NOMINAL, top=c.name, codes=DAC_CORNER_CODES, period=12.5e-9)[0]
        decks['hold_zero'] = dac_deck(net, *NOMINAL, top=c.name, codes=[511, -512], period=period, hold_zero=True)[0]
    if corners:
        for cr in corner_list(corners):
            decks['c_' + tag(cr)] = dac_deck(net, *cr, top=c.name, codes=DAC_CORNER_CODES, period=period)[0]
    if corners != 'minimal':
        import math as _m
        decks['sine'] = dac_deck(net, *NOMINAL, top=c.name, codes=DAC_SINE, period=period)[0]
    decks = {k: v.replace('wrdata dac.dat', f'wrdata {k}.dat') for k, v in decks.items()}   # no shared file
    # Extracted chunks take ~3 h each at t0 = 600 ns (a 1.2 us run timed out at 4 h): 8 h per deck.
    res = run_decks(work, decks, timeout=8 * 3600)
    # Each chunk is evaluated against ITS OWN -512/511 endpoints (a startup/drift difference
    # between runs must not appear as INL), then the per-code errors are merged.
    n, rc, chunks = {}, 0, {}
    for k, ch in enumerate(DAC_NOMINAL_CHUNKS):
        m, r = res.pop(f'nominal_{k}')
        rc = rc or r
        chunks[k] = dac_eval(m, ch, len(ch))
        for key in ('idd', 'ioff'):
            if m.get(key) is not None and key not in n:
                n[key] = m[key]
        if k == 0:
            n.update(m)
    res['nominal'] = (n, rc)
    ev = None
    if all(chunks.values()):
        err = {}
        for ch in chunks.values():
            for cd, e in ch['code_error_lsb'].items():
                err.setdefault(cd, e)
        ev = dict(chunks[0], code_error_lsb={str(cd): err[str(cd)] for cd in DAC_CODES},
                  cm_V=round(sum(ch['cm_V'] for ch in chunks.values()) / len(chunks), 4),
                  endpoint_spread_lsb=round(max(abs(ch['fullscale_diff_V'][j] - chunks[0]['fullscale_diff_V'][j])
                                                for ch in chunks.values() for j in (0, 1)) / (chunks[0]['lsb_mV'] * 1e-3), 3))
    r80 = dac_eval(res['rate80M'][0], DAC_CORNER_CODES, len(DAC_CORNER_CODES)) if 'rate80M' in res else 'not run (identical copy of dac_i)'
    hz = res['hold_zero'][0] if 'hold_zero' in res else {}
    off = offload(work, net, c.name, 'dac', 'OUTP')
    # 'clean' = basic function: +/-1 V class full scale, monotonic at the sampled
    # codes, static error <= 4 LSB (10-bit) = 1 LSB at the 8-bit class the spec
    # asks for. (The 32-LSB limit used earlier was set after the first runs; the
    # 2026-11 performance review flagged it as relaxed. The pre-relaxation value
    # is not recorded in git, so the limit is tied to the 8-bit spec.)
    def dmono(e):
        vals = [e['code_error_lsb'][str(cd)] + cd for cd in sorted(DAC_CODES)]
        return all(a < b for a, b in zip(vals, vals[1:]))
    # v4: every chunk must exit 0 and the chunks' own endpoints must agree within 0.5 LSB
    # (limit fixed before the extracted results), so per-chunk endpoints cannot hide drift.
    ok = ev is not None and not rc and ev['endpoint_spread_lsb'] <= 0.5 and \
        1.6 < ev['fullscale_diff_V'][1] - ev['fullscale_diff_V'][0] < 2.4 and \
        max(abs(v) for v in ev['code_error_lsb'].values()) <= CLEAN_LSB and dmono(ev)
    perf = [dict(metric='differential full scale (V)', target='+/-1.0', nominal=ev and ev['fullscale_diff_V']),
            dict(metric='static code error at sampled codes (LSB, endpoint fit)', target='8-bit-class',
                 nominal=ev and ev['code_error_lsb']),
            dict(metric='output common mode (V)', target='1.65', nominal=ev and ev['cm_V']),
            dict(metric='supply current, active (mA)', target='2.0 allocation', nominal=-1e3 * n.get('idd', 0)),
            dict(metric='stretch: 80 MS/s (12.5 ns) update, same codes', target='non-gating 40 MHz-channel stretch',
                 nominal=r80)]
    if corners:
        perf.append(dict(metric='corner sweep (extracted)', target='narrow window, not gating',
                         corners={k[2:]: dac_eval(v[0], DAC_CORNER_CODES, len(DAC_CORNER_CODES)) for k, v in res.items()
                                  if k.startswith('c_')}))
    tests = dict(
        safe=dict(state='pass' if abs(n.get('ioff', 1)) < 1e-6 and
                  all(abs(v['leak_A_at_1p65V'] or 1) < 1e-8 for v in off.values()) else 'fail',
                  cases=[dict(case='EN=0 supply current (A), tt 27C 3.3V', value=n.get('ioff')),
                         dict(case='OUTP held at 1.65 V while disabled / island unpowered', value=off)],
                  notes='Reset: registers cleared, load header open, IBIAS switch open, clock receiver '
                        'tail off; outputs isolated by NMOS series switches (no PMOS junction on OUTP/OUTN).'),
        clean=dict(extracted_nominal=ev, extracted_ok=ok, netlist=f'generated/{c.name[3:]}.ext.spice',
                   bench='benches.dac_deck'),
        observable=dict(state='pass', atb_taps=['dac_bias (ATB_BIAS = local NMOS bias gate)'],
                        status_bits=[], clock_obs=[],
                        notes='Function observable on the BB_I/BB_Q pads via debug.bb_tap observe_tx '
                              '(TX filter output), owned by rf_rx/bbfilter.'),
        fallback=dict(state='pass' if all((v['cap_fF_at_10MHz'] or 1e9) < 100 for v in off.values()) else 'open',
                      routes=['rf_tx_external_baseband: debug.bb_tap inject_tx_filter / inject_tx_mixer with '
                              'dac_*.config.enable=0 -> OUTP/OUTN series switches open'],
                      bypass_loading_fF={k: v['cap_fF_at_10MHz'] for k, v in off.items()},
                      evidence=off),
        )
    excluded = ['gain_trim and offset_trim register fields have no analog effect in this version',
                'hold_zero verified only at one code pair', 'No glitch energy or full 1024-code INL/DNL run; '
                f'static error sampled at {len(DAC_CODES)} codes; SFDR from settled samples only', 'Output CM regulated to VDD/2 by the on-block CM loop (v3)',
                'Random current-source mismatch NOT simulated (no MC): analytic mid-scale INL sigma ~1.0 LSB (PDK A_Vt) / '
                '~2.0 LSB (pessimistic 2x A_Vt, design-assumptions), P(max|INL| > 4 LSB) ~0.1 % / ~28 %; '
                'the 4-LSB clean gate is deterministic (extracted, tt) only',
                'Rounding/saturation of the 12-bit transport word: truncation (code[11:2]) only']
    if 'sine' in res:
        sm = res['sine'][0]
        vd = [sm.get(f'vcm{i}', float('nan')) - sm.get(f'vn{i}', float('nan')) for i in range(len(DAC_SINE))]
        try:
            perf.append(dict(metric=f'coherent sine, {len(DAC_SINE)} codes (bin {DAC_SINE_BIN}), output settled 1.9 T '
                                    'after each update (static SFDR; glitches not included)', target='8-bit class (SFDR >= 50 dB)',
                             nominal={k: v for k, v in fft_metrics([x * 1e3 for x in vd], DAC_SINE_BIN).items()
                                      if k != 'codes'}))
        except Exception as e:      # noqa: BLE001
            perf.append(dict(metric='coherent sine', nominal=f'failed: {e}'))
    perf.append(dict(metric='hold_zero with codes 511/-512 applied (V diff)', target='0',
                     nominal=[None if hz.get('vcm0') is None else hz['vcm0'] - hz.get('vn0', 0),
                              None if hz.get('vcm1') is None else hz['vcm1'] - hz.get('vn1', 0)]))
    return dict(tests=tests, performance=perf, excluded=excluded, raw={k: v[0] for k, v in res.items()})


# ===================================================================== ADC bench
ADC_INPUTS = [0.0, 0.5, -0.5, 0.123, -0.7, 0.75, -0.25, 0.9]
ADC_NOM = [0.5, -0.5, 0.123, -0.7]       # extracted runs are slow: 4 conversions
ADC_IL = [0.5, -0.5, -0.5, 0.5, 0.123, -0.7, -0.7, 0.123]   # interleaved: each core sees all four levels


def adc_bench(c, work, corners):
    """v3 (2-way interleaved). Gating rate: 40 MS/s per channel (ILEN=1, 25 ns
    clock, 6 ns acquisition) at every envelope corner. ILEN=0 single-core 20 MS/s
    is the in-block fallback. Each core sees every DC level (ADC_IL ordering)."""
    net = 'ext.spice'
    P40 = dict(period=25e-9, acq=6e-9, ilen=1)
    P20 = dict(period=50e-9, acq=10e-9, ilen=0)
    decks, cfg = {}, {}

    def add(name, crn, inputs, p, **kw):
        decks[name] = adc_deck(net, *crn, top=c.name, inputs=inputs, **p, **kw)[0]
        cfg[name] = dict(p, n=len(inputs), inputs=inputs)
    add('nominal_40MSps', NOMINAL, ADC_IL, P40)
    if corners != 'minimal':
        add('single_core_20MSps', NOMINAL, ADC_NOM, P20)
        add('tests', NOMINAL, [0.3] * 8, P40, test=[0, 0, 1, 1, 2, 2, 3, 3])
        add('margin_ss_32C_3.15V_45MSps', ('ss', 32, 3.15), ADC_IL[:4], dict(P40, period=22.2e-9))
    if corners:
        for cr in corner_list(corners):
            add('c_' + tag(cr), cr, ADC_IL[:4], P40)
            if corners in ('all', True) and cr[0] == 'ss':
                add('s_' + tag(cr), cr, ADC_NOM[:2], P20)     # single-core fallback at slow corners

    def one(item):
        name, text = item
        d = work / name
        d.mkdir(exist_ok=True)
        import os
        if not (d / net).exists():
            os.link(work / net, d / net)          # hard link: only the run directory is mounted
        r = ck.ngspice(d, 'tb.spice', text)
        p = cfg[name]
        codes = decode(d / 'adc.dat', 40e-9, p['period'], p['n'], p['acq'], ilen=p['ilen']) \
            if (d / 'adc.dat').exists() else None
        return name, dict(meas=meas(r.stdout), codes=codes, rc=r.returncode)
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        res = dict(ex.map(one, decks.items()))
    off = offload(work, net, c.name, 'adc', 'INP')

    def core_eval(cd, vin):
        """gain/offset from the +0.5/-0.5 V conversions, deviation of every point."""
        try:
            hi, lo = cd[vin.index(0.5)], cd[vin.index(-0.5)]
        except ValueError:
            return None
        g = hi - lo
        o = (hi + lo) / 2
        ideal = [round(v * g + o) for v in vin]
        mono = [c_ for _, c_ in sorted(zip(vin, cd))]
        return dict(inputs_V=vin, codes=cd, codes_per_V=g, implied_fullscale_V=round(512 / g, 4) if g else None,
                    offset_codes=o, dev_from_gain_offset_fit=[a - b for a, b in zip(cd, ideal)],
                    monotonic=all(a < b for a, b in zip(mono, mono[1:])))

    def gain_eval(name):
        r = res.get(name)
        if not r or not r['codes']:
            return None
        p, codes = cfg[name], r['codes']
        out = dict(t_done_ns_max=max((x['t_done_after_sample_fall_ns'] or 1e9) for x in codes),
                   all_done=all(x['t_done_after_sample_fall_ns'] is not None for x in codes),
                   conversion_window_ns=round(((2 if p['ilen'] else 1) * p['period'] - p['acq']) * 1e9, 2))
        for core in ('A', 'B') if p['ilen'] else ('A',):
            sel = [k for k, x in enumerate(codes) if x['core'] == core]
            out['core_' + core] = core_eval([codes[k]['code'] for k in sel], [p['inputs'][k] for k in sel])
        out['pass'] = out['all_done'] and all(
            v and v['codes_per_V'] > 350 and v['monotonic'] and max(abs(x) for x in v['dev_from_gain_offset_fit']) <= CLEAN_LSB
            for k, v in out.items() if k.startswith('core_'))
        return out
    nom = gain_eval('nominal_40MSps')
    tc = (res['tests']['codes'] if 'tests' in res else None) or []
    tst = {}
    for core in ('A', 'B'):
        for m_ in range(4):
            v = [x['code'] for k, x in enumerate(tc) if x['core'] == core and [0, 0, 1, 1, 2, 2, 3, 3][k] == m_]
            tst[f'core_{core}_input_test={m_}'] = v[0] if v else None
    tst['note'] = 'input 0.3 V differential applied throughout; modes 1-3 must ignore it'
    ok = bool(nom and nom['pass'])
    perf = [dict(metric='40 MS/s per channel, 2-way interleaved (25 ns clock, 6 ns acquisition), tt/27C/3.3V',
                 target='40 MS/s per I/Q (AA)', nominal=nom),
            dict(metric='single-core fallback ILEN=0 at 20 MS/s (50 ns, 10 ns acquisition)', target='>= 20 MS/s',
                 nominal=gain_eval('single_core_20MSps')),
            dict(metric='margin probe: ss/32C/3.15V at 45 MS/s (22.2 ns clock)', target='margin, not gating',
                 nominal=gain_eval('margin_ss_32C_3.15V_45MSps')),
            dict(metric='input_test modes 1/2/3 per core (expect 0, +128*g, -128*g codes)', target='0/+VREF/4/-VREF/4',
                 nominal=tst),
            dict(metric='supply current at 40 MS/s (mA)', target='8 allocation',
                 nominal=-1e3 * res['nominal_40MSps']['meas'].get('idd', 0)),
            dict(metric='VREF average current at 40 MS/s (uA)', target='refbuf source limit 1 mA',
                 nominal=-1e6 * res['nominal_40MSps']['meas'].get('iref', 0))]
    if corners:
        cr_res = {k[2:]: gain_eval(k) for k in res if k.startswith('c_')}
        perf.append(dict(metric='corner sweep at 40 MS/s interleaved (extracted)', target='40 MS/s at every envelope corner',
                         all_pass=all(v and v['pass'] for v in cr_res.values()), corners=cr_res))
        sl = {k[2:]: gain_eval(k) for k in res if k.startswith('s_')}
        if sl:
            perf.append(dict(metric='single-core fallback 20 MS/s at ss corners', target='>= 20 MS/s', corners=sl))
    nm = res['nominal_40MSps']['meas']
    tvals = [tst.get(f'core_{x}_input_test={m_}') for x in 'AB' for m_ in (1, 2, 3)]
    obs_ok = None not in tvals and all(
        tst[f'core_{x}_input_test=2'] > tst[f'core_{x}_input_test=1'] + 80 and
        tst[f'core_{x}_input_test=3'] < tst[f'core_{x}_input_test=1'] - 80 for x in 'AB')
    tests = dict(
        safe=dict(state='pass' if abs(nm.get('ioff', 1)) < 1e-6 and
                  all(abs(v['leak_A_at_1p65V'] or 1) < 1e-8 for v in off.values()) else 'fail',
                  cases=[dict(case='EN=0 supply current (A)', value=nm.get('ioff')),
                         dict(case='INP held at 1.65 V while disabled / island unpowered', value=off)],
                  notes='Reset: registers cleared, comparator clock low (no static path), bootstrap gate '
                        'pulled to VSS, clock receiver and bias off; ILEN=0 also holds core B in reset. Every '
                        'device touching INP/INN, VCM and VREF is an NMOS in p-substrate.'),
        clean=dict(extracted_nominal=nom, extracted_ok=ok, netlist=f'generated/{c.name[3:]}.ext.spice',
                   bench='benches.adc_deck', criterion=f'all conversions complete at 40 MS/s, both cores monotonic, '
                   f'<= {CLEAN_LSB} codes from a per-core gain/offset fit'),
        observable=dict(state='pass' if obs_ok else 'open',
                        atb_taps=['adc_comparator_bias (ATB_BIAS = local bias gate, also clock receiver)'],
                        status_bits=['adc_*_done', 'adc_*_overload', 'adc_*_doneb', 'adc_*_overloadb'], clock_obs=[],
                        notes='input_test 1/2/3 give known codes on each core without any external source; '
                              'ILEN=0 isolates core A.'),
        # Criterion: no DC path (< 10 nA at 1.65 V) and < ADC_OFF_CAP_FF per leg (the original
        # 100 fF; it had been moved to 0.5 pF after measuring ~110 fF, which the 2026-11
        # review rejected as a post-hoc relaxation).
        fallback=dict(state='pass' if all((v['cap_fF_at_10MHz'] or 1e9) < ADC_OFF_CAP_FF and
                                          abs(v['leak_A_at_1p65V'] or 1) < 1e-8 for v in off.values()) else 'open',
                      criterion=f'no DC path (<10 nA at 1.65 V) and < {ADC_OFF_CAP_FF} fF per leg disabled/unpowered',
                      routes=['rf_bb_external_adc: debug.bb_tap observe_rx_pga etc.; ADC input stays high-Z '
                              'when disabled or unpowered',
                              'in-block: ILEN=0 runs core A alone at 20 MS/s (v2 behaviour)'],
                      bypass_loading_fF={k: v['cap_fF_at_10MHz'] for k, v in off.items()}, evidence=off))
    excluded = ['comparator_trim field not implemented (no analog trim); per-core offset removed digitally',
                'acquisition_ns is realised by the ADC_CLOCK duty cycle (6 ns high at 40 MHz), not inside this block',
                'VREF is an ideal source in these DC benches; the FFT bench (adc_fft.py --refbuf) puts the '
                'extracted refbuf in the loop',
                'No Monte Carlo: interleave timing skew from mismatch is estimated, not simulated']
    return dict(tests=tests, performance=perf, excluded=excluded,
                raw={k: dict(meas=v['meas'], codes=v['codes']) for k, v in res.items()})


# ===================================================================== ADC FFT
def fft_metrics(codes, nbin, nharm=7):
    """Coherent single-tone FFT (rectangular window; nbin coprime with N).
    SNDR = signal / everything except DC; SFDR = signal / largest other bin;
    THD from harmonics 2..nharm (folded)."""
    import numpy as np
    x = np.asarray(codes, float)
    n = len(x)
    p = np.abs(np.fft.rfft(x - x.mean())) ** 2
    sig = p[nbin]
    rest = np.delete(p[1:], nbin - 1)
    sndr = 10 * np.log10(sig / max(rest.sum(), 1e-30))
    k = int(np.argmax(np.where(np.arange(len(p)) == nbin, 0, p[:] * (np.arange(len(p)) > 0))))
    sfdr = 10 * np.log10(sig / max(p[k], 1e-30))
    hb = []
    for h in range(2, nharm + 1):
        b = (h * nbin) % n
        hb.append(min(b, n - b))
    thd = 10 * np.log10(sum(p[b] for b in set(hb) if 0 < b <= n // 2) / sig)
    amp = 2 * np.sqrt(sig) / n
    return dict(points=n, signal_bin=nbin, sndr_db=round(float(sndr), 2), enob=round(float((sndr - 1.76) / 6.02), 2),
                sfdr_db=round(float(sfdr), 2), sfdr_bin=k, thd_db=round(float(thd), 2),
                amplitude_codes=round(float(amp), 1))


def il_correct(codes):
    """Per-core offset and gain correction (what the FPGA does for a 2-way
    interleaved ADC): remove each core's mean, scale core B's rms to core A's."""
    import numpy as np
    x = np.asarray(codes, float)
    a, b = x[0::2] - x[0::2].mean(), x[1::2] - x[1::2].mean()
    y = np.empty_like(x)
    y[0::2], y[1::2] = a, b * (a.std() / b.std() if b.std() else 1.0)
    return dict(offset_A=round(float(x[0::2].mean()), 2), offset_B=round(float(x[1::2].mean()), 2),
                gain_B_over_A=round(float(b.std() / a.std()), 5) if a.std() else None), y.tolist()


REFBUF_LOOP = """.include refbuf.ext.spice
VR0 VREF0 0 1.0
IBR VDD IBR 10u
D2 IBR VDD dclamp
XRB VDD 0 VREF0 VREFRB IBR VDD 0 RBREADY pt_refbuf
"""


def adc_fft(work, net, top, corner=NOMINAL, n=1024, cycles=487, period=25e-9, acq=6e-9, amp=1.6,
            ilen=1, chunk=64, warm=2, refbuf=False, workers=None):
    """Coherent N-point FFT of the extracted ADC, split into parallel chunks.
    Chunk j converts global samples j*chunk-warm .. (j+1)*chunk-1 of one
    continuous sine (SIN phase set so every chunk sits on the same global time
    grid; the first `warm` conversions of each chunk are discarded, an even
    count so the core A/B assignment is preserved). amp = differential peak V.
    refbuf=True: VREF comes from the extracted refbuf (100 pF reservoir) instead
    of an ideal source; the ADC starts after refbuf READY settles."""
    import shutil as _sh
    fs = 1 / period
    fin = cycles * fs / n
    t0 = 8e-6 if refbuf else 40e-9
    decks = {}
    for j in range(n // chunk):
        g0 = j * chunk - warm                      # global index of local sample 0
        ph = (360.0 * fin * (g0 * period - t0)) % 360.0
        extra = REFBUF_LOOP if refbuf else ''
        d, _ = adc_deck(net, *corner, top=top, inputs=[0.0] * (chunk + warm), period=period, acq=acq,
                        t0=t0, ilen=ilen, extra=extra, sine=(amp, fin),
                        vref='VREFRB VREF 0' if refbuf else 'VREF 0 1.0')
        a = amp / 2
        d = d.replace(f'VIP INP 0 SIN(1.65 {a:.5g} {fin:.6g})', f'VIP INP 0 SIN(1.65 {a:.5g} {fin:.6g} 0 0 {ph:.6f})')
        d = d.replace(f'VIN INN 0 SIN(1.65 {-a:.5g} {fin:.6g})', f'VIN INN 0 SIN(1.65 {-a:.5g} {fin:.6g} 0 0 {ph:.6f})')
        assert f'{ph:.6f}' in d
        decks[f'c{j:03d}'] = d
    work = Path(work)

    def one(item):
        name, text = item
        w = work / name
        w.mkdir(parents=True, exist_ok=True)
        _sh.copy(work / net, w / net)
        if refbuf:
            _sh.copy(work / 'refbuf.ext.spice', w / 'refbuf.ext.spice')
        if not (w / 'adc.dat').exists():
            ck.ngspice(w, 'tb.spice', text)
        dec = decode(w / 'adc.dat', t0, period, chunk + warm, acq, ilen=ilen)
        return name, dec[warm:]
    with cf.ThreadPoolExecutor(workers or WORKERS) as ex:
        parts = dict(ex.map(one, decks.items()))
    conv = [x for k in sorted(parts) for x in parts[k]]
    codes = [x['code'] for x in conv]
    late = sum(1 for x in conv if x['t_done_after_sample_fall_ns'] is None)
    raw = fft_metrics(codes, cycles)
    out = dict(corner=list(corner), fs_hz=fs, fin_hz=fin, amplitude_diff_peak_V=amp, acquisition_ns=acq * 1e9,
               interleaved=bool(ilen), refbuf_in_loop=refbuf, chunks=n // chunk, warmup_per_chunk=warm,
               missing_done=late, overload=sum(1 for x in conv if x['overload']), raw=raw)
    if ilen:
        cal, y = il_correct(codes)
        out['per_core_offset_gain_corrected'] = dict(fft_metrics(y, cycles), **cal)
    out['codes'] = codes
    out['t_done_ns_max'] = max((x['t_done_after_sample_fall_ns'] or 1e9) for x in conv)
    return out
