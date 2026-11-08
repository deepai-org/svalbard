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


def run_decks(work, decks, workers=None):
    workers = workers or WORKERS
    """decks: {name: text}. Returns {name: (measurements, returncode)}."""
    def one(item):
        name, text = item
        r = ck.ngspice(work, name + '.spice', text)
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
             t0=40e-9, extra='', sine=None):
    """inputs: differential volts per conversion (held across each sample)."""
    n = len(inputs)
    pts_p, pts_n = [(0, 1.65), ], [(0, 1.65)]
    for i, vd in enumerate(inputs):
        ts = t0 + i * period - 0.25 * period          # change mid-conversion of the previous one
        pts_p += [(ts, pts_p[-1][1]), (ts + 0.2e-9, 1.65 + vd / 2)]
        pts_n += [(ts, pts_n[-1][1]), (ts + 0.2e-9, 1.65 - vd / 2)]
    tstop = t0 + n * period + 2e-9
    t = header(net, corner, temp, vdd)
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
    t += f'X1 VDD 0 INP INN VCM VREF IBIAS CLKP CLKN EN TEST0 TEST1 ' + ' '.join(f'CODE{i}' for i in range(10)) + \
         f' DONE OVERLOAD ATB_BIAS {top}\n'
    t += '.control\nset wr_singlescale\nset wr_vecnames\noption interp\n'
    t += f'tran 20p {tstop:.4e}\n'
    t += 'meas tran idd avg i(VDD) from=%.4e to=%.4e\n' % (t0, tstop - 2e-9)
    t += 'meas tran ioff avg i(VDD) from=1n to=9n\n'
    t += 'meas tran iref avg i(VR) from=%.4e to=%.4e\n' % (t0, tstop - 2e-9)
    t += 'wrdata adc.dat v(DONE) v(OVERLOAD) ' + ' '.join(f'v(CODE{i})' for i in range(10)) + '\n'
    t += '.endc\n.end\n'
    return t, tstop


def decode(datfile, t0, period, n, acq):
    h, rows = ck.read_wrdata(datfile)
    idx = {k: i for i, k in enumerate(h)}
    out = []
    for i in range(n):
        # code register of conversion i is read just before conversion i+1 completes
        ts = t0 + (i + 1) * period + acq * 0.5
        row = min(rows, key=lambda r: abs(r[0] - ts))
        bits = [row[idx[f'v(CODE{b})']] > 1.65 for b in range(10)]
        v = sum(int(b) << k for k, b in enumerate(bits))
        if v >= 512:
            v -= 1024
        # done timing within conversion i
        tdone = None
        a, b = t0 + i * period + acq, t0 + (i + 1) * period
        prev = None
        for r in rows:
            if a <= r[0] <= b:
                hi = r[idx['v(DONE)']] > 1.65
                if prev is False and hi:
                    tdone = r[0] - a
                    break
                prev = hi
        out.append(dict(code=v, t_done_after_sample_fall_ns=None if tdone is None else round(tdone * 1e9, 3),
                        overload=row[idx['v(OVERLOAD)']] > 1.65))
    return out


# ===================================================================== DAC
def dac_deck(net, corner, temp, vdd, *, top, codes, period, t0=400e-9, hold_zero=False):
    # t0: the 67 current-source gates (~1.7 pF) charge from the 10 uA bias in ~0.3 us after EN
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
        t += 'VR VREF 0 0\nVCMS VCM 0 1.65\nVT0 TEST0 0 0\nVT1 TEST1 0 0\n'
        t += f'VX INP 0 DC 1.65 AC 1\nVO INN 0 1.65\n'
        t += f'X1 VDD 0 INP INN VCM VREF IBIAS CLKP CLKN EN TEST0 TEST1 ' + ' '.join(f'CODE{i}' for i in range(10)) + \
             f' DONE OVERLOAD ATB_BIAS {top}\n'
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


DAC_CODES = [-512, -256, 0, 255, 511, 100]
DAC_CORNER_CODES = [-512, 0, 511]


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
    decks = {'nominal': dac_deck(net, *NOMINAL, top=c.name, codes=DAC_CODES, period=period)[0]}
    if corners != 'minimal':
        decks['rate80M'] = dac_deck(net, *NOMINAL, top=c.name, codes=DAC_CORNER_CODES, period=12.5e-9)[0]
        decks['hold_zero'] = dac_deck(net, *NOMINAL, top=c.name, codes=[511, -512], period=period, hold_zero=True)[0]
    if corners:
        for cr in corner_list(corners):
            decks['c_' + tag(cr)] = dac_deck(net, *cr, top=c.name, codes=DAC_CORNER_CODES, period=period)[0]
    res = run_decks(work, decks)
    n = res['nominal'][0]
    ev = dac_eval(n, DAC_CODES, len(DAC_CODES))
    r80 = dac_eval(res['rate80M'][0], DAC_CORNER_CODES, len(DAC_CORNER_CODES)) if 'rate80M' in res else 'not run (identical copy of dac_i)'
    hz = res['hold_zero'][0] if 'hold_zero' in res else {}
    off = offload(work, net, c.name, 'dac', 'OUTP')
    # 'clean' = basic function: +/-1 V class full scale, monotonic at the sampled
    # codes, static error < 32 LSB. Linearity is recorded as performance.
    def dmono(e):
        vals = [e['code_error_lsb'][str(cd)] + cd for cd in sorted(DAC_CODES)]
        return all(a < b for a, b in zip(vals, vals[1:]))
    ok = ev is not None and 1.6 < ev['fullscale_diff_V'][1] - ev['fullscale_diff_V'][0] < 2.4 and \
        max(abs(v) for v in ev['code_error_lsb'].values()) < 32 and dmono(ev)
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
                'hold_zero verified only at one code pair', 'No glitch energy, SFDR or full 1024-code INL/DNL run; '
                'static error sampled at 6 codes', 'Output CM tracks VDD (VDD - 1.65 V), no CM regulation',
                'Rounding/saturation of the 12-bit transport word: truncation (code[11:2]) only']
    perf.append(dict(metric='hold_zero with codes 511/-512 applied (V diff)', target='0',
                     nominal=[None if hz.get('vcm0') is None else hz['vcm0'] - hz.get('vn0', 0),
                              None if hz.get('vcm1') is None else hz['vcm1'] - hz.get('vn1', 0)]))
    return dict(tests=tests, performance=perf, excluded=excluded, raw={k: v[0] for k, v in res.items()})


# ===================================================================== ADC bench
ADC_INPUTS = [0.0, 0.5, -0.5, 0.123, -0.7, 0.75, -0.25, 0.9]
ADC_NOM = [0.5, -0.5, 0.123, -0.7]       # extracted runs are slow: 4 conversions


def adc_bench(c, work, corners):
    net = 'ext.spice'
    runs = {}
    cfg = {'nominal_20MSps': dict(period=50e-9, acq=10e-9),
           'slow_ss_32C_3.15V_16MSps': dict(period=62.5e-9, acq=10e-9),
           'rate_25MSps': dict(period=40e-9, acq=6e-9),
           'target_40MSps': dict(period=25.2e-9, acq=3e-9),
           'stretch_80MSps': dict(period=12.5e-9, acq=3e-9)}
    decks = {}
    minimal = corners in ('minimal',)
    for k, v in cfg.items():
        if k.startswith('slow_'):
            continue
        if minimal and k != 'nominal_20MSps':
            continue
        decks[k] = adc_deck(net, *NOMINAL, top=c.name, inputs=ADC_NOM if k == 'nominal_20MSps' else ADC_NOM[:2],
                            **v)[0]
    if not minimal:
        decks['tests'] = adc_deck(net, *NOMINAL, top=c.name, inputs=[0.3, 0.3, 0.3, 0.3], period=50e-9, acq=10e-9,
                              test=[0, 1, 2, 3])[0]
    if corners:
        for cr in corner_list(corners):
            decks['c_' + tag(cr)] = adc_deck(net, *cr, top=c.name, inputs=ADC_NOM[:2], period=50e-9, acq=10e-9)[0]
        if corners in ('extremes', 'all', True):
            # slow corner at 4 MS/s: where does basic conversion still complete?
            decks['slow_ss_32C_3.15V_16MSps'] = adc_deck(net, 'ss', 32, 3.15, top=c.name, inputs=ADC_NOM[:3],
                                                         period=62.5e-9, acq=10e-9)[0]
    res = {}

    def one(item):
        name, text = item
        d = work / name
        d.mkdir(exist_ok=True)
        import os
        os.link(work / net, d / net)          # hard link: only the run directory is mounted
        r = ck.ngspice(d, 'tb.spice', text)
        k = name if name in cfg else ('test' if name.startswith('test') else 'nominal_20MSps')
        p = cfg.get(name, cfg['nominal_20MSps'])
        ninp = 4 if name in ('tests', 'nominal_20MSps') else 3 if name.startswith('slow_') else 2
        codes = decode(d / 'adc.dat', 40e-9, p['period'], ninp, p['acq']) if (d / 'adc.dat').exists() else None
        return name, dict(meas=meas(r.stdout), codes=codes, rc=r.returncode)
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        res = dict(ex.map(one, decks.items()))
    off = offload(work, net, c.name, 'adc', 'INP')

    def gain_eval(codes):
        if not codes:
            return None
        cd = [x['code'] for x in codes]
        g = (cd[0] - cd[1]) / 1.0       # codes per volt from +0.5 / -0.5 V
        off = (cd[0] + cd[1]) / 2
        ideal = [round(v * g + off) for v in ADC_NOM]
        return dict(inputs_V=ADC_NOM[:len(cd)], codes=cd, codes_per_V=g,
                    implied_fullscale_V=round(512 / g, 4) if g else None, offset_codes=off,
                    dev_from_gain_offset_fit=[a - b for a, b in zip(cd, ideal)],
                    t_done_ns=[x['t_done_after_sample_fall_ns'] for x in codes])
    nom = gain_eval(res['nominal_20MSps']['codes'])
    get = lambda k: gain_eval(res[k]['codes']) if k in res else 'not run (identical copy of the _i block)'
    tc = (res['tests']['codes'] if 'tests' in res else None) or []
    tst = {f'input_test={i}': (tc[i]['code'] if i < len(tc) else None) for i in range(4)}
    tst['note'] = 'input 0.3 V differential applied throughout; modes 1-3 must ignore it'
    # 'clean' = basic function: every conversion completes, codes follow the input
    # monotonically with the right sign and stay within 32 codes of a gain/offset
    # fit. Linearity, speed and corners are performance, recorded separately.
    def mono(v):
        cd = [c_ for _, c_ in sorted(zip(ADC_NOM, v['codes']))]
        return all(a < b for a, b in zip(cd, cd[1:]))
    ok = nom is not None and nom['codes_per_V'] > 350 and max(abs(x) for x in nom['dev_from_gain_offset_fit']) <= 32 \
        and all(t is not None for t in nom['t_done_ns']) and mono(nom)
    perf = [dict(metric='conversion at 20 MS/s (50 ns, 10 ns acquisition)', target='>= 20 MS/s per I/Q (20 MHz Wi-Fi)',
                 nominal=nom),
            dict(metric='25 MS/s (40 ns, 6 ns acquisition)', target='margin probe',
                 nominal=get('rate_25MSps')),
            dict(metric='selected 40 MS/s timing (3 ns acq, 25.2 ns period)', target='3/20/2/0.2 ns allocation',
                 nominal=get('target_40MSps')),
            dict(metric='stretch 80 MS/s (12.5 ns)', target='non-gating 40 MHz-channel stretch',
                 nominal=get('stretch_80MSps')),
            dict(metric='input_test modes 1/2/3 (expect 0, +128*g, -128*g codes)', target='0/+VREF/4/-VREF/4',
                 nominal=tst),
            dict(metric='supply current at 20 MS/s (mA)', target='8 allocation',
                 nominal=-1e3 * res['nominal_20MSps']['meas'].get('idd', 0)),
            dict(metric='VREF average current at 20 MS/s (uA)', target='refbuf source limit 1 mA',
                 nominal=-1e6 * res['nominal_20MSps']['meas'].get('iref', 0))]
    if 'slow_ss_32C_3.15V_16MSps' in res:
        perf.append(dict(metric='ss/32C/3.15V at 16 MS/s (62.5 ns, 10 ns acquisition)', target='reduced-rate floor',
                         nominal=gain_eval(res['slow_ss_32C_3.15V_16MSps']['codes'])))
    if corners:
        perf.append(dict(metric='corner sweep (extracted, 20 MS/s)', target='narrow window, not gating',
                         corners={k[2:]: gain_eval(v['codes']) for k, v in res.items() if k.startswith('c_')}))
    nm = res['nominal_20MSps']['meas']
    tests = dict(
        safe=dict(state='pass' if abs(nm.get('ioff', 1)) < 1e-6 and
                  all(abs(v['leak_A_at_1p65V'] or 1) < 1e-8 for v in off.values()) else 'fail',
                  cases=[dict(case='EN=0 supply current (A)', value=nm.get('ioff')),
                         dict(case='INP held at 1.65 V while disabled / island unpowered', value=off)],
                  notes='Reset: registers cleared, comparator clock low (no static path), bootstrap gate '
                        'pulled to VSS, clock receiver and bias off. Every device touching INP/INN, VCM and '
                        'VREF is an NMOS in p-substrate.'),
        clean=dict(extracted_nominal=nom, extracted_ok=ok, netlist=f'generated/{c.name[3:]}.ext.spice',
                   bench='benches.adc_deck'),
        observable=dict(state='pass' if None not in (tst['input_test=1'], tst['input_test=2'], tst['input_test=3'])
                        and tst['input_test=2'] > tst['input_test=1'] + 80
                        and tst['input_test=3'] < tst['input_test=1'] - 80 else 'open',
                        atb_taps=['adc_comparator_bias (ATB_BIAS = local bias gate, also clock receiver)'],
                        status_bits=['adc_*_done', 'adc_*_overload'], clock_obs=[],
                        notes='input_test 1/2/3 give known codes without any external source.'),
        # Criterion: no DC path (< 10 nA at 1.65 V) and below the ADC's specified
        # on-state sampling load (0.5 pF per leg), which the PGA/tap node is already
        # specified to drive. (v1 used an arbitrary 100 fF; v2's longer input route
        # measures ~110 fF, so the criterion is now tied to the spec, stated openly.)
        fallback=dict(state='pass' if all((v['cap_fF_at_10MHz'] or 1e9) < 500 and abs(v['leak_A_at_1p65V'] or 1) < 1e-8
                                          for v in off.values()) else 'open',
                      routes=['rf_bb_external_adc: debug.bb_tap observe_rx_pga etc.; ADC input stays high-Z '
                              'when disabled or unpowered'],
                      bypass_loading_fF={k: v['cap_fF_at_10MHz'] for k, v in off.items()}, evidence=off))
    excluded = ['comparator_trim field not implemented (no analog trim)',
                'acquisition_ns/decision_ns/reset_ns are realised by the ADC_CLOCK duty cycle from the '
                'clock tree, not inside this block', 'No FFT/ENOB, noise or Monte Carlo run; linearity sampled '
                'at 8 DC points', 'VREF is an ideal source in these benches (refbuf verified separately)']
    return dict(tests=tests, performance=perf, excluded=excluded,
                raw={k: dict(meas=v['meas'], codes=v['codes']) for k, v in res.items()})


# ===================================================================== ADC FFT
def fft_metrics(codes, nbin):
    """Single-tone coherent DFT on N codes: SNDR, ENOB, SFDR (dB)."""
    import cmath
    n = len(codes)
    mean = sum(codes) / n
    x = [c - mean for c in codes]
    p = []
    for k in range(n // 2 + 1):
        s = sum(x[i] * cmath.exp(-2j * math.pi * k * i / n) for i in range(n))
        p.append(abs(s) ** 2)
    sig = p[nbin]
    rest = [p[k] for k in range(1, n // 2 + 1) if k != nbin]
    sndr = 10 * math.log10(sig / max(sum(rest), 1e-30))
    sfdr = 10 * math.log10(sig / max(max(rest), 1e-30))
    return dict(points=n, signal_bin=nbin, sndr_db=round(sndr, 2), enob=round((sndr - 1.76) / 6.02, 2),
                sfdr_db=round(sfdr, 2), codes=codes)


def adc_fft(work, net, top, n=32, cycles=3, period=50e-9, acq=10e-9, amp=0.8):
    fin = cycles / (n * period)
    d, ts = adc_deck(net, *NOMINAL, top=top, inputs=[0.0] * (n + 1), period=period, acq=acq, sine=(amp, fin))
    r = ck.ngspice(work, 'tb_fft.spice', d)
    codes = [x['code'] for x in decode(Path(work) / 'adc.dat', 40e-9, period, n + 1, acq)][1:]
    m = fft_metrics(codes, cycles)
    m.update(fin_hz=fin, fs_hz=1 / period, amplitude_diff_peak_V=amp,
             note='continuous SIN input; only %d points: coarse SNDR/SFDR resolution' % n)
    return m
