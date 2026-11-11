"""Timing-family driver: layout + DRC + LVS + extracted simulation + corners
+ evidence JSON for every block.  Usage:
    python3 run_timing.py [--blocks a,b] [--skip-layout] [--skip-corners]
Raw simulation output goes to <repo>/scratch/timing/<block>/; committed
artifacts go to analog/timing/generated/.
"""
import argparse
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import timing_flow as tf

VDD = 3.3
CORNERS = [(c, t, v) for c in ('tt', 'ss', 'ff') for t in (22, 32) for v in (3.15, 3.35)]


def sup(v=VDD):
    return f'VDD vdd 0 {v}\n'


def period_meas(node, td, n=4, name='per'):
    return (f'.measure tran {name} trig v({node}) val={{vth}} td={td} rise=1 '
            f'targ v({node}) val={{vth}} td={td} rise={n + 1}\n')


def freq(m, n=4, name='per'):
    p = m.get(name)
    return n / p if p else None


# ----------------------------------------------------------------- testbenches
# Each tb(inc, v) returns (deck_body, analyse(meas) -> dict with 'pass').

def tb_diff_clk_rx(inc, v=VDD, f=2.5e9, amp=0.25, kind='diff', **data):
    if kind == 'data':
        return tb_diff_clk_rx_data(inc, v=v, **data)
    # AC coupling as on the board; low-frequency cases use a larger capacitor
    # and a longer run so the self-bias settles after EN rises at 5 ns.
    T = 60e-9 if f >= 5e8 else max(300e-9, 10 / f)
    cc = '1p' if f >= 5e8 else '100p'
    step = '2p' if f >= 5e8 else '20p'
    if kind == 'diff':
        src = f'VS sp 0 sin(0 {amp} {f})\nVSN sn 0 sin(0 {-amp} {f})\n'
    elif kind == 'se':
        src = f'VS sp 0 sin(0 {amp} {f})\nVSN sn 0 0\n'
    else:
        src = (f'VS sp 0 pulse(0 {v} 0 50p 50p {0.5 / f - 50e-12} {1 / f})\n'
               f'VSN sn 0 pulse({v} 0 0 50p 50p {0.5 / f - 50e-12} {1 / f})\n')
    body = f""".param vth={v / 2}
.include {inc}
{sup(v)}VEN en 0 {v}
{src}CCP sp inp {cc}
CCN sn inn {cc}
X1 inp inn en {'en' if kind == 'se' else '0'} outp outn present det vdd 0 pt_diff_clk_rx
CL1 outp 0 20f
CL2 outn 0 20f
.tran {step} {T}
{period_meas('outp', T * 0.7, 2)}.measure tran thi trig v(outp) val={{vth}} td={T * 0.7} rise=1 targ v(outp) val={{vth}} td={T * 0.7} fall=1
.measure tran skew trig v(outp) val={{vth}} td={T * 0.7} rise=1 targ v(outn) val={{vth}} td={T * 0.7} fall=1
.measure tran ion avg i(VDD) from={T * 0.7} to={T}
.measure tran pres find v(present) at={T}
"""

    def analyse(m):
        fo = freq(m, 2)
        r = dict(input=(f'{kind} {f / 1e9:g} GHz, {4 * amp * 1e3:.0f} mVpp differential' if kind == 'diff' else
                        f'single-ended {f / 1e9:g} GHz, {2 * amp * 1e3:.0f} mVpp on INP, INN AC-grounded, SE=1' if kind == 'se'
                        else f'{kind} {f / 1e6:g} MHz rail-to-rail'),
                 f_out_hz=fo, duty=(m['thi'] * fo if fo and m.get('thi', -1) > 0 else None),
                 p_to_n_skew_ps=m.get('skew', 0) * 1e12 if 'skew' in m else None,
                 i_off_ua=-m.get('ioff', math.nan) * 1e6, i_on_ma=-m.get('ion', math.nan) * 1e3,
                 present=m.get('pres'))
        r.pop('i_off_ua')  # EN=1 from t=0 here (bias solved at DC); off-state current is in the safe cases
        r['pass'] = bool(fo and abs(fo / f - 1) < 0.005 and (m.get('pres') or 0) > v * 0.8)
        return r
    return body, analyse


def tb_diff_clk_rx_data(inc, v=VDD, rate=1e9, vpp=0.5, cc='10p', nper=3, first=False, pre=0, idle=0):
    """Data mode (WTX_EXT fallback): PRBS7 NRZ, differential, vpp = differential
    peak-to-peak (each side vpp/2), 50 ohm per side, AC-coupled through cc into
    INP/INN, EN=1 from t=0.  Runs nper PRBS periods; the last period is checked:
    every input transition must give exactly one OUTP and one OUTN crossing
    (no missing/extra edges = no bit errors), and the crossing-time spread
    (after removing the mean latency) is reported as jitter."""
    ui = 1 / rate
    st, bits = 0x7f, []
    for _ in range(127):
        nb = ((st >> 6) ^ (st >> 5)) & 1
        st = ((st << 1) | nb) & 0x7f
        bits.append(nb)
    # optional electrical idle (both legs at the common mode, `idle` UI), then an optional
    # DC-balanced 1010 preamble, then the PRBS.  Without idle the source starts parked at the
    # first bit's level (the coupling caps charged to it at t=0).
    seq = [None] * idle + [k % 2 for k in range(pre)] + bits * nper
    pre = pre + idle
    tr = min(0.2 * ui, 100e-12)
    a = vpp / 4
    lvl = lambda b: 0.0 if b is None else (a if b else -a)
    def pwl(sign):
        pts, last = [f'0 {sign * lvl(seq[0])}'], seq[0]
        for i, b in enumerate(seq[1:], 1):
            if b != last:
                t = i * ui
                pts += [f'{t:.6e} {sign * lvl(last)}', f'{t + tr:.6e} {sign * lvl(b)}']
                last = b
        return ' '.join(pts)
    T = len(seq) * ui
    t_start = pre * ui if first else (pre + (nper - 1) * 127) * ui   # first: check from the first PRBS bit
    # an edge out of electrical idle is not counted (the latched output may already be at
    # that level); every data edge after it is
    if first and idle:
        t_start += 0.5 * ui
    trans = [i * ui + tr / 2 for i in range(1, len(seq)) if seq[i] != seq[i - 1] and seq[i - 1] is not None
             and i * ui >= t_start - 2 * ui]
    nmeas = sum(1 for t in trans if t >= t_start) + 6
    body = f""".param vth={v / 2}
.include {inc}
{sup(v)}VEN en 0 {v}
VSP sp0 0 pwl({pwl(1)})
VSN sn0 0 pwl({pwl(-1)})
RSP sp0 sp 50
RSN sn0 sn 50
CCP sp inp {cc}
CCN sn inn {cc}
X1 inp inn en 0 outp outn present det vdd 0 pt_diff_clk_rx
CL1 outp 0 20f
CL2 outn 0 20f
.tran {min(10e-12, ui / 100):.3e} {T}
.measure tran ion avg i(VDD) from={t_start} to={T}
""" + ''.join(f'.measure tran cp{j} when v(outp)={v / 2} cross={j} td={t_start}\n.measure tran cn{j} when v(outn)={v / 2} cross={j} td={t_start}\n'
              for j in range(1, nmeas + 1))

    def analyse(m):
        win = [t for t in trans if t >= t_start]
        out = {}
        for nm in ('cp', 'cn'):
            xs = [m[f'{nm}{j}'] for j in range(1, nmeas + 1) if f'{nm}{j}' in m]
            # latency: from the first crossing to the nearest input transition before it
            if not xs:
                out[nm] = dict(crossings=0, errors=len(win))
                continue
            offs = []
            for x in xs:
                d = [x - t for t in trans if 0 <= x - t < 3 * ui + 2e-9]
                if d:
                    offs.append(min(d))
            offs.sort()
            got0 = [x for x in xs if x <= T - 0.1e-9]

            def score(lat):
                exp = [t + lat for t in win if t + lat <= T - 0.1e-9]
                # after electrical idle, the output's own move to the first bit's level is not an edge
                got = [x for x in got0 if not (idle and first and exp and x < exp[0] - 0.5 * ui)]
                # pair crossings to expected edges within half a UI
                errs, dev, used = 0, [], set()
                for e in exp:
                    cand = [k for k, x in enumerate(got) if abs(x - e) < 0.5 * ui and k not in used]
                    if not cand:
                        errs += 1
                        continue
                    k = min(cand, key=lambda k: abs(got[k] - e))
                    used.add(k)
                    dev.append(got[k] - e)
                return errs + len(got) - len(used), exp, dev, got     # + extra crossings
            # latency: the median nearest-edge offset, or (when the latency exceeds a UI and
            # the nearest edge is ambiguous) the whole-UI shift of it that gives the fewest errors
            lat0 = offs[len(offs) // 2] if offs else 0.0
            lat = min((lat0 + k * ui for k in range(0, int((2e-9 + 3 * ui) / ui) + 1)), key=lambda L: score(L)[0])
            errs, exp, dev, got = score(lat)
            out[nm] = dict(crossings=len(got), expected=len(exp), errors=errs,
                           latency_ns=lat * 1e9 if lat is not None else None,
                           jitter_pp_ui=((max(dev) - min(dev)) / ui) if dev else None)
        r = dict(input=f'PRBS7 NRZ {rate / 1e9:g} Gb/s, {vpp * 1e3:.0f} mVpp differential, 50 ohm, AC-coupled {cc}F per side'
                       + (f', {pre}-bit 1010 preamble' if pre else '')
                       + (', checked from the first PRBS bit (start-up)' if first else ', last of %d PRBS periods checked' % nper),
                 rate_bps=rate, vpp_diff_v=vpp, bits_checked=127, outp=out['cp'], outn=out['cn'],
                 i_on_ma=-m.get('ion', math.nan) * 1e3)
        ok = all(out[k].get('errors', 1) == 0 and (out[k].get('jitter_pp_ui') or 9) < 0.5 for k in ('cp', 'cn'))
        r['pass'] = bool(ok)
        return r
    return body, analyse


def tb_clk_obs(inc, v=VDD, f=0.5e9):
    T = 30e-9 + 48 / f
    body = f""".param vth={v / 2}
.include {inc}
{sup(v)}VEN en 0 pwl(0 0 5n 0 5.1n {v})
VIN in0 0 pulse(0 {v} 0 50p 50p {0.5 / f - 50e-12} {1 / f})
VN0 n0 0 {v}
VN1 n1 0 {v}
X1 in0 0 0 0 0 0 0 0 0 0 0 n0 n1 0 en out vdd 0 pt_clk_obs
CL out 0 10p
RL out 0 1meg
.tran 5p {T}
.measure tran ioff avg i(VDD) from=2n to=4.9n
.measure tran vout_off find v(out) at=4.9n
{period_meas('out', 30e-9, 2)}.measure tran thi trig v(out) val={{vth}} td=30n rise=1 targ v(out) val={{vth}} td=30n fall=1
.measure tran vmax max v(out) from=30n to={T}
.measure tran vmin min v(out) from=30n to={T}
.measure tran ion avg i(VDD) from=30n to={T}
"""

    def analyse(m):
        fo = freq(m, 2)
        r = dict(input=f'IN0 {f / 1e9:g} GHz, N=3 (/8), 10 pF pad load', expected_hz=f / 8, f_out_hz=fo,
                 duty=(m['thi'] * fo if fo and 'thi' in m else None),
                 out_swing_v=[m.get('vmin'), m.get('vmax')], i_off_ua=-m.get('ioff', math.nan) * 1e6,
                 out_while_disabled_v=m.get('vout_off'), i_on_ma=-m.get('ion', math.nan) * 1e3)
        r['pass'] = bool(fo and abs(fo / (f / 8) - 1) < 0.01 and m.get('vmax', 0) > 0.9 * v and m.get('vmin', 9) < 0.1 * v)
        return r
    return body, analyse


def tb_ring_osc(inc, v=VDD):
    T = 70e-9
    body = f""".param vth={v / 2}
.include {inc}
{sup(v)}VEN en 0 pwl(0 0 5n 0 5.1n {v})
X1 en out vdd 0 pt_ring_osc
CL out 0 20f
.tran 2p {T}
.measure tran ioff avg i(VDD) from=2n to=4.9n
{period_meas('out', 20e-9, 4)}.measure tran ion avg i(VDD) from=20n to={T}
"""

    def analyse(m):
        fo = freq(m)
        r = dict(f_out_hz=fo, i_off_ua=-m.get('ioff', math.nan) * 1e6, i_on_ma=-m.get('ion', math.nan) * 1e3,
                 stage_delay_ps=(1e12 / fo / 42 if fo else None))
        r['pass'] = bool(fo and fo > 50e6 and r['i_off_ua'] < 1)
        return r
    return body, analyse


def tb_aosc(inc, v=VDD):
    T = 300e-9
    body = f""".param vth={v / 2}
.include {inc}
{sup(v)}VEN en 0 pwl(0 0 5n 0 5.1n {v})
X1 en clk x vdd 0 pt_aosc
CL clk 0 20f
.tran 10p {T}
.measure tran ioff avg i(VDD) from=2n to=4.9n
{period_meas('clk', 100e-9, 6)}.measure tran thi trig v(clk) val={{vth}} td=100n rise=1 targ v(clk) val={{vth}} td=100n fall=1
.measure tran ion avg i(VDD) from=100n to={T}
"""

    def analyse(m):
        fo = freq(m, 6)
        r = dict(f_out_hz=fo, target_hz=[40e6, 60e6], duty=(m['thi'] * fo if fo and 'thi' in m else None),
                 i_off_ua=-m.get('ioff', math.nan) * 1e6, i_on_ma=-m.get('ion', math.nan) * 1e3)
        r['in_target_window'] = bool(fo and 40e6 <= fo <= 60e6)
        # pass requires the 40-60 MHz window (r1 passed ss at 35-37 MHz on fo > 10 MHz alone)
        r['pass'] = bool(r['in_target_window'] and r['i_off_ua'] < 1)
        return r
    return body, analyse


def pair_src(name, f, v, td=0):
    return (f'V{name}P {name}_p 0 pulse(0 {v} {td} 30p 30p {0.5 / f - 30e-12} {1 / f})\n'
            f'V{name}N {name}_n 0 pulse({v} 0 {td} 30p 30p {0.5 / f - 30e-12} {1 / f})\n')


def tb_clockmux(inc, v=VDD, mode='switch'):
    """Revision 5 clockmux (single-ended, <= 1 GHz, host_follow).
    switch: WIRE goes PLLW 810 MHz -> stop -> REF 1 GHz -> stop -> WCK 400 MHz;
            PREF=H2D 125 MHz, WSMP=REF 1 GHz, CONV=HF 200 MHz, HOST=HF.
    rf:     passive-LO RF mode (REF/AUX carry 1 GHz LO-rate edges): PREF=H2D,
            CONV=HF, HOST=HF; WIRE and WSMP stopped.  Current per mode.
    wired:  WIRE=PLLW 810 MHz, WSMP=WSI 810 MHz, PREF=REF 50.625 MHz,
            CONV=CONV_INT 202.5 MHz, HOST=HOST_INT 101.25 MHz."""
    T = 60e-9
    def src(n, f):
        return f'V{n} {n} 0 pulse(0 {v} 0 30p 30p {0.5 / f - 30e-12} {1 / f})\n'
    def on(n, t0=5e-9, t1=None):
        if t1 is None:
            return f'V{n} {n} 0 pwl(0 0 {t0} 0 {t0 + 1e-10} {v})\n'
        return f'V{n} {n} 0 pwl(0 0 {t0} 0 {t0 + 1e-10} {v} {t1} {v} {t1 + 1e-10} 0)\n'
    sels = 'ps_ref ps_aux ps_h2d ws_pll ws_ref ws_aux ws_wck ss_int ss_ref ss_wck cs_int cs_ref cs_aux cs_hf hs_int hs_hf'.split()
    if mode == 'switch':
        fr = dict(pllw=810e6, ref=1e9, aux=0.5e9, wck=0.4e9, h2d=125e6, wsi=810e6, conv_int=202.5e6, host_int=101.25e6, hf=200e6)
        act = {'ws_pll': (5e-9, 20e-9), 'ws_ref': (25e-9, 40e-9), 'ws_wck': (45e-9, None), 'ps_h2d': (5e-9, None),
               'ss_ref': (5e-9, None), 'cs_hf': (5e-9, None), 'hs_hf': (5e-9, None)}
        want = dict(wire_pllw_hz=810e6, wire_ref_hz=1e9, wire_wck_hz=0.4e9, pref_hz=125e6, wsmp_hz=1e9, conv_hz=200e6, host_hz=200e6)
    elif mode == 'rf':
        fr = dict(pllw=810e6, ref=1e9, aux=1e9, wck=0.4e9, h2d=125e6, wsi=810e6, conv_int=202.5e6, host_int=101.25e6, hf=200e6)
        act = {'ps_h2d': (5e-9, None), 'cs_hf': (5e-9, None), 'hs_hf': (5e-9, None)}
        want = dict(pref_hz=125e6, conv_hz=200e6, host_hz=200e6)
    else:
        fr = dict(pllw=810e6, ref=50.625e6, aux=0.5e9, wck=0.4e9, h2d=125e6, wsi=810e6, conv_int=202.5e6, host_int=101.25e6, hf=200e6)
        act = {'ws_pll': (5e-9, None), 'ss_int': (5e-9, None), 'ps_ref': (5e-9, None), 'cs_int': (5e-9, None), 'hs_int': (5e-9, None)}
        want = dict(wire_pllw_hz=810e6, wsmp_hz=810e6, pref_hz=50.625e6, conv_hz=202.5e6, host_hz=101.25e6)
    body = f""".param vth={v / 2}
.include {inc}
{sup(v)}""" + ''.join(src(n, f) for n, f in fr.items()) + ''.join(
        on(n, *act[n]) if n in act else f'V{n} {n} 0 0\n' for n in sels) + f"""X1 pllw ref aux wck h2d wsi conv_int host_int hf
+ {' '.join(sels)}
+ pref wire wsmp conv host vdd 0 pt_clockmux
CL1 pref 0 20f
CL2 wire 0 20f
CL3 wsmp 0 20f
CL4 conv 0 20f
CL5 host 0 20f
.tran 2p {T}
.measure tran ioff avg i(VDD) from=1n to=4.9n
.measure tran stop_max max v(wire) from=1n to=4.9n
.measure tran ion avg i(VDD) from=10n to={40e-9 if mode == 'switch' else T}
{period_meas('wire', 8e-9, 8, 'per_pllw')}{period_meas('wire', 28e-9, 8, 'per_ref')}{period_meas('wire', 47e-9, 4, 'per_wck')}{period_meas('pref', 10e-9, 2, 'per_pref')}{period_meas('wsmp', 10e-9, 8, 'per_wsmp')}{period_meas('conv', 10e-9, 4, 'per_conv')}{period_meas('host', 10e-9, 4, 'per_host')}.measure tran gap_max max v(wire) from=21.5n to=24.5n
.measure tran wsmp_stop max v(wsmp) from=10n to={T}
"""

    def analyse(m):
        r = dict(mode=mode, wire_pllw_hz=freq(m, 8, 'per_pllw'), wire_ref_hz=freq(m, 8, 'per_ref'), wire_wck_hz=freq(m, 4, 'per_wck'),
                 pref_hz=freq(m, 2, 'per_pref'), wsmp_hz=freq(m, 8, 'per_wsmp'), conv_hz=freq(m, 4, 'per_conv'),
                 host_hz=freq(m, 4, 'per_host'), stopped_wire_max_v=m.get('stop_max'),
                 wire_max_during_stop_gap_v=m.get('gap_max') if mode == 'switch' else None,
                 i_off_ua=-m.get('ioff', math.nan) * 1e6, i_on_ma=-m.get('ion', math.nan) * 1e3)
        ok = all(r[k] and abs(r[k] / f - 1) < 0.01 for k, f in want.items()) and m.get('stop_max', 9) < v / 3
        if mode == 'switch':
            ok = ok and m.get('gap_max', 9) < v / 3
        if mode == 'rf':
            r['wsmp_max_while_stopped_v'] = m.get('wsmp_stop')
            ok = ok and m.get('wsmp_stop', 9) < v / 3
        r['pass'] = bool(ok)
        return r
    return body, analyse


def tb_vco_replica(inc, v=VDD, vctrl=2.0):
    T = 400e-9
    body = f""".param vth={v / 2}
.include {inc}
{sup(v)}VEN en 0 pwl(0 0 2n 0 2.1n {v})
VC vc 0 {vctrl}
X1 en vc out vt vdd 0 pt_vco_replica
CL out 0 20f
.tran 4p {T}
{period_meas('out', 60e-9, 4)}.measure tran ion avg i(VDD) from=60n to={T}
.measure tran vtail avg v(vt) from=60n to={T}
"""

    def analyse(m):
        fo = freq(m)
        r = dict(vctrl_v=vctrl, f_out_hz=fo, f_vco_hz=(fo * 16 if fo else None), i_on_ma=-m.get('ion', math.nan) * 1e3,
                 vtail_v=m.get('vtail'))
        r['pass'] = bool(fo)
        return r
    return body, analyse


# Explicit gate resistance for the CML LO driver pair (the PDK models have
# rgatemod=0 and Magic extraction is C-only): mandate 60-150 ohm per 10 um
# device, upper end, 120 um per side -> 12.5 ohm in series with GA / GB.
LOCML_RG = 12.5


def rg_wrap_locml(text, rg=LOCML_RG):
    """Rename `ct_locml` (schematic or extracted) to ct_locml_core and add a
    wrapper with series gate resistors on GA/GB."""
    import re as _re
    m = _re.search(r'^\.subckt ct_locml (.*)$', text, _re.M)
    if not m or 'ct_locml_core' in text:
        return text
    ports = m.group(1).split()
    text = text.replace(m.group(0), '.subckt ct_locml_core ' + m.group(1))
    text = _re.sub(r'^\.ends ct_locml\b', '.ends ct_locml_core', text, flags=_re.M)
    inner = ' '.join({'GA': 'GAI', 'GB': 'GBI'}.get(p, p) for p in ports)
    return text + (f'\n.subckt ct_locml {" ".join(ports)}\nRGA GA GAI {rg}\nRGB GB GBI {rg}\n'
                   f'XC {inner} ct_locml_core\n.ends ct_locml\n')


def stage_rg(work):
    """Apply rg_wrap_locml to the staged schematic macro and extracted block."""
    work = Path(work)
    for f in (work / 'generated' / 'fast' / 'ct_locml.spice', work / 'lo_ext.ext.spice'):
        if f.exists():
            f.write_text(rg_wrap_locml(f.read_text()))


def tb_lo_ext(inc, v=VDD, mode='ext', f=2.45e9, vpp=2.0, kind='sin', amp=0.58, cm=1.7, T=None):
    """Mixer LO nodes loaded with the RX (12x5u) and TX (2x20u) switch gates
    per line plus 22 fF wiring.  External sources: 50 ohm, board AC coupling
    100 pF, ~1 pF pad capacitance; I on EXT_I*, Q on EXT_Q* (90 deg later).
    Internal mode (r-cml): LOI_* are the QVCO tank nodes, a DC-coupled sine
    (cm, amp per side; kind='sin') or a rail-to-rail square (kind='sq');
    100 ns so the CM loop and VB are settled (steady state)."""
    stage_rg(tf.SCRATCH / 'lo_ext' / 'sim')
    if T is None:
        T = 12e-9 if mode.startswith('ext') else 100e-9
    a = vpp / 2
    q = 0.25 / f
    src = ''
    for leg, (ph, sgn) in dict(ip=(0, 1), in_=(0, -1), qp=(q, 1), qn=(q, -1)).items():
        n = leg.rstrip('_')
        if mode.startswith('ext'):
            if kind == 'sin':
                src += f'VS{n} s{n} 0 sin(0 {sgn * a} {f} {ph})\n'
            else:
                lo, hi = (-a, a) if sgn > 0 else (a, -a)
                src += f'VS{n} s{n} 0 pulse({lo} {hi} {ph} 40p 40p {0.5 / f - 40e-12} {1 / f})\n'
            src += f'RS{n} s{n} b{n} 50\nCB{n} b{n} pad{n} 100p\nCP{n} pad{n} 0 1p\n'
            src += f'VLI{n} loi{n} 0 0\n'
        else:
            if kind == 'sin':
                src += f'VLI{n} loi{n} 0 sin({cm} {sgn * amp} {f} 0 0 {-ph * f * 360})\n'
            else:
                lo, hi = (0, v) if sgn > 0 else (v, 0)
                src += f'VLI{n} loi{n} 0 pulse({lo} {hi} {ph} 30p 30p {0.5 / f - 30e-12} {1 / f})\n'
            src += f'RP{n} pad{n} 0 50\nCP{n} pad{n} 0 1p\n'
    loads = ''
    for n in ('ip', 'in', 'qp', 'qn'):
        loads += (f'XRX{n} rxd lo{n} rxs 0 nfet_03v3 w=5u l=0.28u m=12\n'
                  f'XTX{n} txd lo{n} txs 0 nfet_03v3 w=10u l=0.28u m=4\nCW{n} lo{n} 0 22f\n')
    ext = v if mode.startswith('ext') else 0
    inn = v if mode == 'int' else 0
    body = f""".param vth={v / 2}
.include {inc}
{sup(v)}VRXD rxd 0 {v / 2}
VRXS rxs 0 {v / 2}
VTXD txd 0 2.5
VTXS txs 0 1.0
VEXT ext 0 {ext}
VINT int 0 {inn}
{src}{loads}X1 padip padin padqp padqn loiip loiin loiqp loiqn ext int 0 loip loin loqp loqn vb vdd 0 pt_lo_ext
.tran 1p {T}
.measure tran lomax max v(loip) from={T - 4e-9} to={T}
.measure tran lomin min v(loip) from={T - 4e-9} to={T}
.measure tran loavg avg v(loip) from={T - 4e-9} to={T}
.measure tran qmax max v(loqp) from={T - 4e-9} to={T}
.measure tran qmin min v(loqp) from={T - 4e-9} to={T}
.measure tran vbavg avg v(vb) from={T - 4e-9} to={T}
.measure tran vb0 find v(vb) at=0
.measure tran qavg avg v(loqp) from={T - 4e-9} to={T}
.measure tran tiq trig v(loip) val={{vth2}} td={T - 4e-9} rise=1 targ v(loqp) val={{vth2}} td={T - 4e-9} rise=1
.measure tran tqi trig v(loqp) val={{vth2}} td={T - 4e-9} rise=1 targ v(loip) val={{vth2}} td={T - 4e-9} rise=1
.measure tran tdiff trig v(loip) val={{vth2}} td={T - 4e-9} rise=1 targ v(loin) val={{vth2}} td={T - 4e-9} fall=1
{period_meas('loip', T - 4e-9, 4).replace('{vth}', '{vth2}')}.measure tran ion avg i(VDD) from={T - 4e-9} to={T}
.measure tran thi trig v(loip) val={{vth2}} td={T - 4e-9} rise=1 targ v(loip) val={{vth2}} td={T - 4e-9} fall=1
.measure tran vbearly avg v(vb) from={T - 24e-9} to={T - 20e-9}
.param vth2={{(2.33 if mode.startswith('ext') else v / 2)}}
"""
    # crossing threshold = the LO centre VB = 0.739 VDD in both modes (r-cml: the
    # CML swings about VB too; the old rail-to-rail driver used VDD/2)
    body = body.replace("{(2.33 if mode.startswith('ext') else v / 2)}", str(0.739 * v))

    def analyse(m):
        fo = freq(m)
        d = None
        for k, sg in (('tiq', 1), ('tqi', -1)):
            if k in m and m[k] > 0 and (d is None or m[k] < abs(d)):
                d = sg * m[k]
        ph = ((d * f * 360 + 180) % 360 - 180) if d is not None else None
        r = dict(mode=mode, input=(f'{kind} {f / 1e9:g} GHz {vpp:g} Vpp per leg open-circuit behind 50 ohm (+1 pF pad)' if mode.startswith('ext')
                                    else (f'internal LOI tank-node sine {f / 1e9:g} GHz, {cm:g} V +- {amp:g} V per side' if kind == 'sin'
                                          else f'internal LOI rail-to-rail square {f / 1e9:g} GHz')),
                 duty_at_vb=((m['thi'] * f) % 1 if 'thi' in m else None),
                 vb_drift_last20ns_mv=((m['vbavg'] - m['vbearly']) * 1e3 if 'vbavg' in m and 'vbearly' in m and not mode.startswith('ext') else None),
                 f_lo_hz=fo, lo_i_max_v=m.get('lomax'), lo_i_min_v=m.get('lomin'), lo_i_avg_v=m.get('loavg'),
                 lo_q_max_v=m.get('qmax'), lo_q_min_v=m.get('qmin'), vb_v=m.get('vbavg'), q_minus_i_deg=ph,
                 ip_in_skew_ps=m.get('tdiff', 0) * 1e12 if 'tdiff' in m else None,
                 i_on_ma=-m.get('ion', math.nan) * 1e3,
                 rx_switch_source_v=v / 2,
                 rx_switch_vgs_on_v=(m['lomax'] - v / 2) if 'lomax' in m else None,
                 rx_switch_vgs_off_v=(m['lomin'] - v / 2) if 'lomin' in m else None)
        # External (AC-coupled) mode: the 12 ns window is inside the 20-200 ns
        # bias time constants, so the LO DC is still moving.  The LO node's only
        # DC path is 20 k to VB, so in steady state avg(LO) = VB(t=0); the
        # steady-state levels keep the measured waveform about that average.
        # Both I and Q must meet the limits.  (Internal mode is driven, not
        # AC-coupled: judged on the measured levels.)
        if mode.startswith('ext') and all(k in m for k in ('lomax', 'lomin', 'loavg', 'qmax', 'qmin', 'qavg', 'vb0')):
            r['steady_state_projection'] = dict(
                vb_dc_v=m['vb0'],
                on_i_v=m['lomax'] - m['loavg'] + m['vb0'] - v / 2, off_i_v=m['vb0'] - (m['loavg'] - m['lomin']) - v / 2,
                on_q_v=m['qmax'] - m['qavg'] + m['vb0'] - v / 2, off_q_v=m['vb0'] - (m['qavg'] - m['qmin']) - v / 2)
            ss_ = r['steady_state_projection']
            levels_ok = min(ss_['on_i_v'], ss_['on_q_v']) >= 0.9 and max(ss_['off_i_v'], ss_['off_q_v']) <= 0.5
        else:
            # r-cml: I and Q both, plus duty at VB (the CML centre) 40-60 %
            levels_ok = (all(k in m for k in ('lomax', 'lomin', 'qmax', 'qmin'))
                         and min(m['lomax'], m['qmax']) - v / 2 >= 0.9 and max(m['lomin'], m['qmin']) - v / 2 <= 0.5
                         and r['duty_at_vb'] is not None and 0.4 <= r['duty_at_vb'] <= 0.6)
        r['pass'] = bool(fo and abs(fo / f - 1) < 0.01 and levels_ok and ph is not None and 80 < abs(ph) < 100)
        return r
    return body, analyse


def tb_polyphase(inc, v=VDD, f=2.45e9, amp=0.5):
    T = 12e-9
    body = f""".param vth={v / 2}
.include {inc}
{sup(v)}VEN en 0 {v}
VSP sp 0 sin(0 {amp} {f})
VSN sn 0 sin(0 {-amp} {f})
RSP sp bp 50
RSN sn bn 50
CBP bp inp 10p
CBN bn inn 10p
X1 inp inn en loiip loiqp loiin loiqn n0 vdd 0 pt_polyphase
CL1 loiip 0 40f
CL2 loiqp 0 40f
CL3 loiin 0 40f
CL4 loiqn 0 40f
.tran 1p {T}
{period_meas('loiip', T - 4e-9, 4)}.measure tran tiq trig v(loiip) val={{vth}} td={T - 4e-9} rise=1 targ v(loiqp) val={{vth}} td={T - 4e-9} rise=1
.measure tran tqi trig v(loiqp) val={{vth}} td={T - 4e-9} rise=1 targ v(loiip) val={{vth}} td={T - 4e-9} rise=1
.measure tran tin trig v(loiip) val={{vth}} td={T - 4e-9} rise=1 targ v(loiin) val={{vth}} td={T - 4e-9} rise=1
.measure tran tqn trig v(loiqp) val={{vth}} td={T - 4e-9} rise=1 targ v(loiqn) val={{vth}} td={T - 4e-9} rise=1
.measure tran thi trig v(loiip) val={{vth}} td={T - 4e-9} rise=1 targ v(loiip) val={{vth}} td={T - 4e-9} fall=1
.measure tran n0pp pp v(n0) from={T - 4e-9} to={T}
.measure tran inpp pp v(inp) from={T - 4e-9} to={T}
.measure tran ion avg i(VDD) from={T - 4e-9} to={T}
"""

    def analyse(m):
        fo = freq(m)
        d = None
        for k, sg in (('tiq', 1), ('tqi', -1)):
            if k in m and m[k] > 0 and (d is None or m[k] < abs(d)):
                d = sg * m[k]
        ph = ((d * f * 360 + 180) % 360 - 180) if d is not None else None
        r = dict(input=f'differential sine {f / 1e9:g} GHz, {2 * amp:g} V peak-to-peak per leg open-circuit behind 50 ohm',
                 f_hz=fo, q_minus_i_deg=ph, iq_phase_error_deg=(abs(ph) - 90 if ph is not None else None),
                 ip_to_in_deg=((m['tin'] * f * 360) % 360 if 'tin' in m else None),
                 qp_to_qn_deg=((m['tqn'] * f * 360) % 360 if 'tqn' in m else None),
                 duty_i=(m['thi'] * f if m.get('thi', -1) > 0 else None),
                 network_node_pp_v=m.get('n0pp'), input_pp_v=m.get('inpp'), i_on_ma=-m.get('ion', math.nan) * 1e3)
        r['pass'] = bool(fo and abs(fo / f - 1) < 0.01 and ph is not None and abs(abs(ph) - 90) < 10)
        return r
    return body, analyse


def hold_block(hold_at, T, n, fref, v):
    """HOLD benches: VCO frequency averaged over 4 reference periods (4N VCO
    cycles) just before HOLD, 200 ns after it (C2/C1 charge sharing settled)
    and at the end; VCTRL at the same times.  hold_at=0: HOLD from t=0 (pure
    drift bench after the precharge is released)."""
    nc = 4 * n
    wv = 4 / fref + 5e-9
    ts = ([('pre', hold_at - wv)] if hold_at > 0 else []) + [('post', (hold_at if hold_at > 0 else 0.85e-6) + 0.2e-6), ('end', T - wv)]
    out = ''
    for tag, td in ts:
        out += f'.measure tran ph_{tag} trig v(ph0) val={v / 2} td={td} rise=1 targ v(ph0) val={v / 2} td={td} rise={nc + 1}\n'
        out += f'.measure tran vh_{tag} find v(vctrl) at={td}\n'
    return out


def hold_analyse(m, hold_at, T, n, fref):
    nc = 4 * n
    f = {k: (nc / m[f'ph_{k}'] if f'ph_{k}' in m else None) for k in ('pre', 'post', 'end')}
    r = dict(hold_at_s=hold_at, f_pre_hold_hz=f['pre'], f_post_hold_hz=f['post'], f_end_hz=f['end'],
             vctrl_pre_hold_v=m.get('vh_pre'), vctrl_post_hold_v=m.get('vh_post'), vctrl_end_v=m.get('vh_end'))
    if f['pre'] and f['post']:
        r['hold_step_ppm'] = (f['post'] / f['pre'] - 1) * 1e6
    if f['post'] and f['end']:
        t0 = (hold_at if hold_at > 0 else 0.85e-6) + 0.2e-6
        dt = (T - 4 / fref - 5e-9) - t0
        r['hold_drift_ppm'] = (f['end'] / f['post'] - 1) * 1e6
        r['hold_drift_window_s'] = dt
        r['hold_drift_ppm_per_10us'] = r['hold_drift_ppm'] * 10e-6 / dt
    return r


def tb_pll_ring(inc, v=VDD, mode='open', vctrl=1.5, fref=62.5e6, vc0=1.5, T=0.6e-6, tpre=150e-9, n=16, hold_at=None):
    """mode 'open': VCTRL forced (switch never opens), REF low.  mode 'closed':
    VCTRL pre-charged to vc0 until tpre, then the loop runs to T (reduced-
    duration lock test; not a cold-start acquisition claim)."""
    phl = ''.join(f'CP{k} ph{k} 0 20f\n' for k in range(8))
    fpfd = fref / 2 if n == 4 else fref             # N=4 runs as REF/2 with feedback /8
    nfb = 10 if fpfd > 20e6 else 4
    wf = (nfb + 1.5) / fpfd
    nv = 8 if mode == 'open' else 2 * n            # closed: two whole reference periods
    wv = 150e-9 if mode == 'open' else ((2 * n + 6) / (n * fref) + 5e-9)
    NE = 8 if mode == 'open' else 2 * n             # phase edges averaged (closed: two reference periods)
    if mode == 'open':
        drv = f'VREF ref 0 0\nVPRE pre 0 {vctrl}\nVPC pc 0 {v}\n'
        T = 200e-9
    else:
        drv = (f'VREF ref 0 pulse(0 {v} 0 100p 100p {0.5 / fref - 100e-12} {1 / fref})\nVPRE pre 0 {vc0}\n'
               f'VPC pc 0 pwl(0 {v} {tpre} {v} {tpre + 1e-9} 0)\n')
    body = f""".param vth={v / 2}
.include {inc}
{sup(v)}VEN en 0 pwl(0 0 2n 0 2.1n {v})
IB vdd ibias 10u
{drv}SPRE vctrl pre pc 0 swpre
.model swpre sw vt={v / 2} vh=0.1 ron=50 roff=1e12
VN4 n4 0 {v if n == 4 else 0}
VN8 n8 0 {v if n == 8 else 0}
VHOLD hold 0 {('0' if hold_at is None else (str(v) if hold_at == 0 else f'pwl(0 0 {hold_at} 0 {hold_at + 1e-10} {v})'))}
* r9 ports: N5/N10 off, CDR fast-tune KP/FU/FD idle (TX/host use)
VN5 n5 0 0
VN10 n10 0 0
VFT kp0 0 0
X1 ref en n4 n8 hold ibias ph0 ph1 ph2 ph3 ph4 ph5 ph6 ph7 lock fbck refo vctrl n5 n10 kp0 kp0 kp0 kp0 kp0 kp0 kp0 kp0 kp0 kp0 kp0 vdd vdd 0 pt_pll_ring
CRO refo 0 20f
{phl}.tran 2p {T}
{period_meas('ph0', T - wv, nv, 'per_vco')}{period_meas('fbck', T - (150e-9 if mode == 'open' else wf), (2 if mode == 'open' else nfb), 'per_fb')}""" + ''.join(f'.measure tran t{k}_{j} when v(ph{k})={v / 2} rise={j} td={T - wv}\n' for k in range(8) for j in range(1, NE + 1)) + f""".measure tran ion avg i(VDD) from={T - 30e-9} to={T}
.measure tran vc_end avg v(vctrl) from={T - 100e-9} to={T}
.measure tran vc_pp pp v(vctrl) from={T - 100e-9} to={T}
.measure tran lock_end find v(lock) at={T}
""" + (hold_block(hold_at, T, n, fref, v) if hold_at is not None else '') + f"""""" + (''.join(f'.measure tran vct{k} find v(vctrl) at={T * k / 10}\n' for k in range(1, 11)) if mode == 'closed' else '') + f""""""
    if mode == 'open':
        pass

    def analyse(m):
        fv = freq(m, nv, 'per_vco')
        ffb = freq(m, 2 if mode == 'open' else nfb, 'per_fb')
        # port phases: PHk - PH0 over NE consecutive PH0 edges, each wrapped
        # with the average period, then averaged (static skew, FM averaged out)
        phs = {}
        if fv:
            tv = 1 / fv
            for k in range(1, 8):
                ds = []
                for j in range(1, NE + 1):
                    t0, tk = m.get(f't0_{j}'), m.get(f't{k}_{j}')
                    if t0 is not None and tk is not None:
                        ds.append(((tk - t0) / tv * 360 - k * 45 + 180) % 360 - 180 + k * 45)
                if ds:
                    phs[k] = (sum(ds) / len(ds), max(ds) - min(ds))
        err = [abs(phs[k][0] - 45 * k) for k in phs]
        r = dict(mode=mode, vctrl_v=(vctrl if mode == 'open' else m.get('vc_end')), f_vco_hz=fv, f_fb_hz=ffb,
                 n_measured=(fv / ffb if fv and ffb else None),
                 port_phase_deg={f'PH{k}': round(phs[k][0], 2) for k in phs},
                 port_phase_spread_pp_deg={f'PH{k}': round(phs[k][1], 2) for k in phs},
                 port_phase_error_max_deg=(max(err) if err else None),
                 ph1_minus_ph0_deg=(phs[1][0] if 1 in phs else None), ph2_minus_ph0_deg=(phs[2][0] if 2 in phs else None),
                 phase_within_5deg=(bool(err) and max(err) <= 5.0),
                 i_on_ma=-m.get('ion', math.nan) * 1e3)
        if mode == 'closed':
            r.update(fref_hz=fref, pfd_hz=fpfd, target_vco_hz=n * fref, n_selected=n, vctrl_precharge_v=vc0, vctrl_ripple_pp_v=m.get('vc_pp'),
                     lock_end_v=m.get('lock_end'))
            locked = bool(fv and abs(fv / (n * fref) - 1) < 0.003 and ffb and abs(ffb / fpfd - 1) < 0.003)
            r['vco_measured_over_ref_periods'] = 2
            r['vctrl_trajectory_v'] = {f'{T * k / 10 * 1e9:.0f}ns': m.get(f'vct{k}') for k in range(1, 11)}
            if hold_at is not None:
                r.update(hold_analyse(m, hold_at, T, n, fref))
                if hold_at == 0:
                    r['pass'] = bool(r.get('hold_drift_ppm_per_10us') is not None and abs(r['hold_drift_ppm_per_10us']) < 100)
                else:
                    r['pass'] = bool(locked and r.get('hold_step_ppm') is not None and abs(r['hold_step_ppm']) < 200
                                     and abs(r.get('hold_drift_ppm_per_10us') or 1e9) < 100)
            r['frequency_locked'] = locked
            r['lock_flag_correct'] = bool(((m.get('lock_end') or 0) > v / 2) == locked)
            if hold_at is None:   # HOLD benches keep their own criterion (was overwritten by `locked`)
                r['pass'] = locked
        else:
            r['pass'] = bool(fv and ffb and abs(fv / ffb / n - 1) < 0.02)
        return r
    return body, analyse


def tb_prescale(inc, v=VDD, f=2.5e9, sel='D16'):
    div = int(sel[1:])
    T = 20e-9 + 3 * div / f
    ctl = ' '.join('en' if k == sel else '0' for k in ('D2', 'D4', 'D8', 'D16'))
    body = f""".param vth={v / 2}
.include {inc}
{sup(v)}VEN en 0 pwl(0 0 2n 0 2.1n {v})
VCK ck 0 pulse(0 {v} 0 30p 30p {0.5 / f - 30e-12} {1 / f})
X1 ck en {ctl} out vdd 0 pt_prescale
CL out 0 50f
.tran 2p {T}
{period_meas('out', 15e-9, 2)}.measure tran ion avg i(VDD) from=15n to={T}
"""

    def analyse(m):
        fo = freq(m, 2)
        r = dict(f_in_hz=f, ratio=div, f_out_hz=fo, expected_hz=f / div, i_on_ma=-m.get('ion', math.nan) * 1e3)
        r['pass'] = bool(fo and abs(fo * div / f - 1) < 0.01)
        return r
    return body, analyse


def tb_wordclk(inc, v=VDD, f=810e6, div=5):
    """Word divider: CK at f, mode /5, /10 or /20.  Measures WORD_CLK and LD
    periods, LD width (must be one CK period), CK-rise -> LD-rise delay and
    current; 0-10 ns EN=0 (stopped, outputs 0)."""
    n = 6
    tm = 14e-9 + div / f            # skip the first word after EN
    T = tm + (n + 1.5) * div / f
    body = f""".param vth={v / 2}
.include {inc}
{sup(v)}VEN en 0 pwl(0 0 10n 0 10.1n {v})
VCK ck 0 pulse(0 {v} 0 40p 40p {0.5 / f - 40e-12} {1 / f})
VD10 d10 0 {v if div == 10 else 0}
VD20 d20 0 {v if div == 20 else 0}
X1 ck en d10 d20 wk lde ld ldb vdd 0 pt_wordclk
CL0 lde 0 30f
CL1 wk 0 30f
CL2 ld 0 60f
CL3 ldb 0 60f
.tran 2p {T}
.measure tran ioff avg i(VDD) from=2n to=9.9n
.measure tran offmax max v(wk) from=2n to=9.9n
.measure tran ldoffmax max v(ld) from=2n to=9.9n
.measure tran ldeoffmax max v(lde) from=2n to=9.9n
.measure tran ion avg i(VDD) from={tm} to={T}
{period_meas('wk', tm, n, 'per_wk')}{period_meas('ld', tm, n, 'per_ld')}.measure tran ldw trig v(ld) val={{vth}} td={tm} rise=1 targ v(ld) val={{vth}} td={tm} fall=1
.measure tran ldbw trig v(ldb) val={{vth}} td={tm} fall=1 targ v(ldb) val={{vth}} td={tm} rise=1
.measure tran tld trig v(ck) val={{vth}} td={tm} rise=1 targ v(ld) val={{vth}} td={tm} rise=1
.measure tran twk trig v(wk) val={{vth}} td={tm} rise=1 targ v(ld) val={{vth}} td={tm} rise=1
.measure tran ldew trig v(lde) val={{vth}} td={tm} rise=1 targ v(lde) val={{vth}} td={tm} fall=1
.measure tran tldel trig v(lde) val={{vth}} td={tm} rise=1 targ v(ld) val={{vth}} td={tm} rise=1
"""

    def analyse(m):
        fw = freq(m, n, 'per_wk')
        fl = freq(m, n, 'per_ld')
        tck = 1 / f
        tld = m.get('tld')
        r = dict(f_ck_hz=f, div=div, word_clk_hz=fw, ld_rate_hz=fl, ld_width_ck=(m['ldw'] / tck if 'ldw' in m else None),
                 ldb_width_ck=(m['ldbw'] / tck if 'ldbw' in m else None),
                 ck_to_ld_ns=(((tld % tck) if tld is not None else None) and (tld % tck) * 1e9),
                 word_clk_rise_to_ld_rise_ck=(m['twk'] / tck if 'twk' in m else None),
                 off_word_clk_max_v=m.get('offmax'), off_ld_max_v=m.get('ldoffmax'),
                 i_off_ua=-m.get('ioff', math.nan) * 1e6, i_on_ma=-m.get('ion', math.nan) * 1e3)
        want = f / div
        r['pass'] = bool(fw and fl and abs(fw / want - 1) < 0.01 and abs(fl / want - 1) < 0.01
                         and r['ld_width_ck'] and abs(r['ld_width_ck'] - 1) < 0.15
                         and r['ldb_width_ck'] and abs(r['ldb_width_ck'] - 1) < 0.15
                         and m.get('offmax', 9) < v / 3 and m.get('ldoffmax', 9) < v / 3 and m.get('ldeoffmax', 9) < v / 3
                         and m.get('ldew') and abs(m['ldew'] * f - 1) < 0.15 and m.get('tldel') and abs(m['tldel'] * f - 1) < 0.1)
        r.update(lde_width_ck=(m['ldew'] * f if 'ldew' in m else None), lde_to_ld_ck=(m['tldel'] * f if 'tldel' in m else None))
        return r
    return body, analyse



def tb_clk_obs16(inc, v=VDD, f=0.5e9, sel=14):
    """pt_clk_obs16: source `sel` (S3..S0 = sel) toggling, every other input held at 0."""
    T = 30e-9 + 48 / f
    ins = ' '.join('insel' if i == sel else '0' for i in range(15))
    ins += ' insel 0 0' if sel == 15 else ' 0 0 0'   # r2: code 15 = OR(IN15A, IN15B, IN15C); IN15A driven
    sb = ' '.join('vdd' if (sel >> k) & 1 else '0' for k in range(4))
    body = f""".param vth={v / 2}
.include {inc}
{sup(v)}VEN en 0 pwl(0 0 5n 0 5.1n {v})
VIN insel 0 pulse(0 {v} 0 50p 50p {0.5 / f - 50e-12} {1 / f})
VN0 n0 0 {v}
VN1 n1 0 {v}
X1 {ins} {sb} n0 n1 0 en out vdd 0 pt_clk_obs16
CL out 0 10p
RL out 0 1meg
.tran 5p {T}
.measure tran ioff avg i(VDD) from=2n to=4.9n
.measure tran vout_off find v(out) at=4.9n
{period_meas('out', 30e-9, 2)}.measure tran thi trig v(out) val={{vth}} td=30n rise=1 targ v(out) val={{vth}} td=30n fall=1
.measure tran vmax max v(out) from=30n to={T}
.measure tran vmin min v(out) from=30n to={T}
.measure tran ion avg i(VDD) from=30n to={T}
"""

    def analyse(m):
        fo = freq(m, 2)
        r = dict(input=f'IN{sel} {f / 1e9:g} GHz, N=3 (/8), 10 pF pad load', expected_hz=f / 8, f_out_hz=fo,
                 duty=(m['thi'] * fo if fo and 'thi' in m else None),
                 out_swing_v=[m.get('vmin'), m.get('vmax')], i_off_ua=-m.get('ioff', math.nan) * 1e6,
                 out_while_disabled_v=m.get('vout_off'), i_on_ma=-m.get('ion', math.nan) * 1e3)
        r['pass'] = bool(fo and abs(fo / (f / 8) - 1) < 0.01 and m.get('vmax', 0) > 0.9 * v and m.get('vmin', 9) < 0.1 * v)
        return r
    return body, analyse


def tb_obs_pre4(inc, v=VDD, f=1.0e9):
    """pt_obs_pre4: CK toggling (CMOS, 40 ps edges); OUT = CK/4 into a 2 pF
    route load (a ~2 mm route to pt_clk_obs16).  EN rises at 5 ns."""
    T = 20e-9 + 40 / f
    body = f""".param vth={v / 2}
.include {inc}
{sup(v)}VEN en 0 pwl(0 0 5n 0 5.1n {v})
VCK ck 0 pulse(0 {v} 0 40p 40p {0.5 / f - 40e-12} {1 / f})
X1 ck en out vdd 0 pt_obs_pre4
CL out 0 2p
.tran 2p {T}
.measure tran ioff avg i(VDD) from=1n to=4.9n
.measure tran vout_off max v(out) from=1n to=4.9n
{period_meas('out', 20e-9, 2)}.measure tran thi trig v(out) val={{vth}} td=20n rise=1 targ v(out) val={{vth}} td=20n fall=1
.measure tran vmax max v(out) from=20n to={T}
.measure tran vmin min v(out) from=20n to={T}
.measure tran ion avg i(VDD) from=20n to={T}
"""

    def analyse(m):
        fo = freq(m, 2)
        r = dict(input=f'CK {f / 1e9:g} GHz CMOS', expected_hz=f / 4, f_out_hz=fo,
                 duty=(m['thi'] * fo if fo and 'thi' in m else None), out_swing_v=[m.get('vmin'), m.get('vmax')],
                 out_while_disabled_max_v=m.get('vout_off'), i_off_ua=-m.get('ioff', math.nan) * 1e6, i_on_ma=-m.get('ion', math.nan) * 1e3)
        r['pass'] = bool(fo and abs(fo / (f / 4) - 1) < 0.01 and m.get('vmax', 0) > 0.9 * v and m.get('vmin', 9) < 0.1 * v
                         and r['duty'] is not None and 0.4 < r['duty'] < 0.6)
        return r
    return body, analyse


def tb_lo_obs(inc, v=VDD, f=2.45e9, amp=0.45, cm=1.7):
    """pt_lo_obs: LP/LN = QVCO I tank pair (DC-coupled sine, cm +- amp per
    side; ss tank: ~1.66 V +- 0.6 V); OBS = LO/8 into a 2 pF route load.
    EN rises at 2 ns.  The extracted latch starts from its layout asymmetry
    (no .ic)."""
    T = 40e-9
    body = f""".param vth={v / 2}
.include {inc}
{sup(v)}VEN en 0 pwl(0 0 2n 0 2.1n {v})
VP lp 0 sin({cm} {amp} {f})
VN ln 0 sin({cm} {-amp} {f})
X1 lp ln en obs vdd 0 pt_lo_obs
CL obs 0 2p
.tran 1p {T}
.measure tran ioff avg i(VDD) from=0.5n to=1.9n
{period_meas('obs', 20e-9, 4)}.measure tran thi trig v(obs) val={{vth}} td=20n rise=1 targ v(obs) val={{vth}} td=20n fall=1
.measure tran vmax max v(obs) from=20n to={T}
.measure tran vmin min v(obs) from=20n to={T}
.measure tran ion avg i(VDD) from=20n to={T}
"""

    def analyse(m):
        fo = freq(m, 4)
        r = dict(input=f'tank sine {f / 1e9:g} GHz, {cm:g} V +- {amp:g} V per side', expected_hz=f / 8, f_out_hz=fo,
                 duty=((m['thi'] * fo) % 1 if fo and 'thi' in m else None), out_swing_v=[m.get('vmin'), m.get('vmax')],
                 i_off_ua=-m.get('ioff', math.nan) * 1e6, i_on_ma=-m.get('ion', math.nan) * 1e3)
        r['pass'] = bool(fo and abs(fo / (f / 8) - 1) < 0.01 and m.get('vmax', 0) > 0.9 * v and m.get('vmin', 9) < 0.1 * v)
        return r
    return body, analyse

TB = dict(wordclk=tb_wordclk, prescale=tb_prescale, pll_ring=tb_pll_ring, polyphase=tb_polyphase, lo_ext=tb_lo_ext, diff_clk_rx=tb_diff_clk_rx, clk_obs=tb_clk_obs, clk_obs16=tb_clk_obs16, ring_osc=tb_ring_osc, aosc=tb_aosc,
          clockmux=tb_clockmux, vco_replica=tb_vco_replica, obs_pre4=tb_obs_pre4, lo_obs=tb_lo_obs)
WIDTH = dict()


def simulate(block, name, tbfun, kwargs, extracted=True, corner='tt', temp=27, v=VDD):
    work = tf.SCRATCH / block / 'sim'
    tf.stage_sources(work, block)
    inc = f'{block}.ext.spice' if extracted else f'{block}.spice'
    body, analyse = tbfun(inc, v=v, **kwargs)
    deck = _hdr(corner, temp) + body + '.end\n'
    m = tf.ngspice(work, name, deck)
    r = analyse(m)
    r.update(netlist='extracted' if extracted else 'schematic', corner=corner, temp_c=temp, vdd_v=v,
             deck=f'scratch/timing/{block}/sim/{name}.spice')
    if m['_errors']:
        r['sim_messages'] = m['_errors']
    return r


def quick(blocks, extracted=False, tag='sch'):
    jobs = []
    for b in blocks:
        if b == 'vco_replica':
            jobs += [(b, f'{tag}_vc{vc}', dict(vctrl=vc)) for vc in (1.0, 1.5, 2.0, 2.5, 3.3)]
        else:
            jobs.append((b, tag, dict()))
    def one(j):
        b, name, kw = j
        try:
            return b, name, simulate(b, name, TB[b], kw, extracted=extracted)
        except Exception as e:  # keep going; record
            return b, name, dict(error=repr(e), **{'pass': False})
    out = {}
    with ThreadPoolExecutor(int(os.environ.get("TIMING_JOBS", "3"))) as ex:
        for b, name, r in ex.map(one, jobs):
            out.setdefault(b, {})[name] = r
            print(b, name, json.dumps(r, default=str)[:900], flush=True)
    return out


OUTPUTS = dict(
    diff_clk_rx=['OUTP', 'OUTN', 'PRESENT', 'ATB_DET'],
    clk_obs=['OUT'], clk_obs16=['OUT'], obs_pre4=['OUT'], lo_obs=['OBS'], ring_osc=['OUT'], aosc=['CLK', 'ATB_X'],
    clockmux=['PREF', 'WIRE', 'WSMP', 'CONV_CLK', 'HOST_CLK'],
    vco_replica=['OUT', 'ATB_VTAIL'],
    prescale=['CK_OUT'],
    wordclk=['WORD_CLK', 'LDE', 'LD', 'LDB'],
    pll_ring=['PH0', 'PH1', 'PH2', 'PH3', 'PH4', 'PH5', 'PH6', 'PH7', 'LOCK', 'FBCK', 'REFO', 'ATB_VCTRL'],
    polyphase=['LOI_IP', 'LOI_QP', 'LOI_IN', 'LOI_QN', 'ATB_N0'],
    lo_ext=['LO_IP', 'LO_IN', 'LO_QP', 'LO_QN', 'ATB_VB'])
# inputs that are clocks/pads in the safe test are driven (toggling) to show
# that a running source cannot wake a disabled block.
SAFE_TOGGLE = dict(lo_obs=['LP'], obs_pre4=['CK'], wordclk=['CK'], prescale=['CK_IN'], pll_ring=['REF'], polyphase=['INP'], lo_ext=['EXT_IP', 'EXT_QP', 'LOI_IP'], diff_clk_rx=['INP'], clk_obs=['IN0'], clk_obs16=['IN0', 'IN8', 'IN15A'], clockmux=['PLLW', 'REF', 'AUX', 'H2D', 'HF'])


def tb_safe(block, inc, v=3.63, island_off=False):
    """Reset-default state: every control input 0 (enables, selects), clocks
    toggling, outputs loaded.  Measures island supply current and output levels.
    island_off: VDD=0 with the pad inputs driven to 3.3 V (diff_clk_rx)."""
    import netlist
    ports, _ = netlist.load(tf.HERE / f'{block}.spice', f'pt_{block}')
    outs = OUTPUTS[block]
    lines = [f'.include {inc}', f'VDD vdd 0 {0 if island_off else v}']
    conn = []
    for p in ports:
        n = p.lower()
        if p == 'VDD':
            conn.append('vdd')
        elif p == 'VSS':
            conn.append('0')
        elif p in outs:
            conn.append(n)
            lines.append(f'R{n} {n} 0 1G')
        elif p == 'IBIAS':
            conn.append('ibias')
            lines.append('IIB vdd ibias 10u' if not island_off else 'IIB 0 ibias 0')
        elif p in SAFE_TOGGLE.get(block, []):
            conn.append(n)
            lines.append(f'V{n} {n} 0 pulse(0 3.3 0 100p 100p 0.9n 2n)' if not island_off
                         else f'V{n} {n} 0 3.3')
        elif island_off and block == 'lo_ext' and p.startswith('EXT_'):
            conn.append(n)
            lines.append(f'V{n} {n} 0 3.3')
        elif island_off and block == 'diff_clk_rx' and p == 'INN':
            conn.append(n)
            lines.append(f'V{n} {n} 0 3.3')
        else:
            conn.append('0')
    lines.append(f'X1 {" ".join(conn)} pt_{block}')
    lines.append('.tran 10p 20n')
    lines.append('.measure tran idd avg i(VDD) from=10n to=20n')
    lines.append('.measure tran iddmax max i(VDD) from=10n to=20n')
    lines.append('.measure tran iddmin min i(VDD) from=10n to=20n')
    for o in outs:
        if not o.startswith('ATB'):
            lines.append(f'.measure tran max_{o.lower()} max v({o.lower()}) from=10n to=20n')
    if island_off:
        for p in (('inp', 'inn') if block == 'diff_clk_rx' else ('ext_ip', 'ext_qn')):
            lines.append(f'.measure tran ipad_{p} avg i(V{p}) from=10n to=20n')
    return '\n'.join(lines) + '\n'


def _hdr(corner, temp):
    """tf.header plus the MIM-cap model section (diff_clk_rx r4 series MIM; harmless for blocks without MIMs)."""
    c = {'tt': 'typical', 'typical': 'typical', 'ss': 'ss', 'ff': 'ff'}.get(corner, 'typical')
    return tf.header(corner, temp) + f'.lib {tf.MODELS}/sm141064.ngspice mimcap_{c}\n'


def safe_cases(block, extracted=True):
    work = tf.SCRATCH / block / 'sim'
    tf.stage_sources(work, block)
    inc = f'{block}.ext.spice' if extracted else f'{block}.spice'
    cases = []
    for corner, temp, v in (('tt', 27, 3.3), ('ff', 85, 3.63), ('ss', 0, 3.63)):
        name = f'safe_{corner}_{temp}_{v}'
        m = tf.ngspice(work, name, _hdr(corner, temp) + tb_safe(block, inc, v) + '.end\n')
        outs = {k[4:]: val for k, val in m.items() if k.startswith('max_')}
        cases.append(dict(case='reset-default controls (all 0), sources toggling', corner=corner, temp_c=temp, vdd_v=v,
                          netlist='extracted' if extracted else 'schematic',
                          i_vdd_avg_ua=-m.get('idd', math.nan) * 1e6,
                          i_vdd_peak_ua=-m.get('iddmin', math.nan) * 1e6,
                          output_max_v=outs, deck=f'scratch/timing/{block}/sim/{name}.spice',
                          errors=m['_errors']))
    if block in ('diff_clk_rx', 'lo_ext'):
        name = 'safe_island_off'
        m = tf.ngspice(work, name, _hdr('tt', 27) + tb_safe(block, inc, island_off=True) + '.end\n')
        cases.append(dict(case='island rail at 0 V, both pads held at 3.3 V', corner='tt', temp_c=27, vdd_v=0,
                          netlist='extracted' if extracted else 'schematic',
                          i_pad_inp_na=-m.get('ipad_inp', m.get('ipad_ext_ip', math.nan)) * 1e9,
                          i_pad_inn_na=-m.get('ipad_inn', m.get('ipad_ext_qn', math.nan)) * 1e9,
                          i_rail_na=-m.get('idd', math.nan) * 1e9, deck=f'scratch/timing/{block}/sim/{name}.spice',
                          errors=m['_errors']))
    return cases


# ----------------------------------------------------------------- per-block plan
NOMINAL = dict(
    wordclk=[(f'nom_{int(f / 1e6)}m_d{d}', dict(f=f, div=d)) for f in (480e6, 810e6) for d in (5, 10, 20)],
    diff_clk_rx=[('nom_diff_1g_500mv', dict(f=1e9, amp=0.125)), ('nom_diff_100m_500mv', dict(f=1e8, amp=0.125)),
                 ('nom_diff_2g5_500mv', dict(f=2.5e9, amp=0.125)), ('nom_diff_2g5_1v', dict(f=2.5e9, amp=0.25)),
                 ('nom_diff_1g_200mv', dict(f=1e9, amp=0.05)), ('nom_diff_1g_1v2', dict(f=1e9, amp=0.3)),
                 ('nom_square_10m', dict(f=1e7, kind='square')),
                 ('nom_se_1g_600mv', dict(f=1e9, amp=0.3, kind='se')), ('nom_diff_3g3_1v', dict(f=3.3e9, amp=0.25)),
                 # data mode (WTX_EXT fallback): PRBS7 NRZ, 10 pF AC coupling, 50 ohm
                 ('data_0g5_500mv', dict(kind='data', rate=0.5e9, vpp=0.5)), ('data_1g_500mv', dict(kind='data', rate=1e9, vpp=0.5)),
                 ('data_1g6_500mv', dict(kind='data', rate=1.6e9, vpp=0.5)), ('data_1g6_300mv', dict(kind='data', rate=1.6e9, vpp=0.3)),
                 ('data_1g6_800mv', dict(kind='data', rate=1.6e9, vpp=0.8)), ('data_2g_500mv', dict(kind='data', rate=2e9, vpp=0.5)),
                 ('data_start_0g5_500mv', dict(kind='data', rate=0.5e9, vpp=0.5, nper=1, first=True)),
                 ('data_pre128_0g5_300mv', dict(kind='data', rate=0.5e9, vpp=0.3, nper=1, first=True, pre=128)),
                 # r4 (TIM-08): 2 Gb/s at 300 mV, and start from electrical idle with no preamble
                 ('data_2g_300mv', dict(kind='data', rate=2e9, vpp=0.3)),
                 ('data_idle_2g_300mv', dict(kind='data', rate=2e9, vpp=0.3, nper=1, first=True, idle=40)),
                 ('data_idle_0g5_300mv', dict(kind='data', rate=0.5e9, vpp=0.3, nper=1, first=True, idle=20))],
    clk_obs=[('nom', dict(f=0.5e9)), ('nom_in1g', dict(f=1e9))], ring_osc=[('nom', {})],
    lo_obs=[('nom_2g45', dict(f=2.45e9)), ('nom_2g5_a0p3', dict(f=2.5e9, amp=0.3)), ('nom_2g4_a1p1', dict(f=2.4e9, amp=1.1, cm=1.95))],
    obs_pre4=[('nom_1g', dict(f=1e9)), ('nom_810m', dict(f=0.81e9)), ('nom_1g25', dict(f=1.25e9)), ('nom_50m', dict(f=50e6))],
    clk_obs16=[('nom', dict(f=0.5e9, sel=14)), ('nom_sel1', dict(f=0.5e9, sel=1)), ('nom_sel8', dict(f=0.5e9, sel=8)),
               ('nom_sel15', dict(f=0.5e9, sel=15)), ('nom_313m_sel1', dict(f=0.3125e9, sel=1))], aosc=[('nom', {})],
    clockmux=[('nom', dict(mode='switch')), ('nom_mode_rf', dict(mode='rf')), ('nom_mode_wired', dict(mode='wired'))],
    vco_replica=[(f'nom_vc{vc}', dict(vctrl=vc)) for vc in (0.9, 1.0, 1.1, 1.2, 1.5, 1.8, 2.1, 2.5, 3.3)],
    prescale=[('nom_2g5_d16', dict(f=2.5e9, sel='D16')), ('nom_240m_d2', dict(f=0.24e9, sel='D2')),
              ('nom_1g5_d16', dict(f=1.5e9, sel='D16'))],
    # closed loop: VCTRL pre-charged for 0.8 us (> 4 R*C1, so C1 is charged
    # too) to the lock voltage measured in an earlier extracted run, then the
    # loop runs for 1.2 us (N=16) / 1.0 us (N=4)
    pll_ring=[('closed_480m', dict(mode='closed', fref=30e6, vc0=1.05, T=2.0e-6, tpre=0.8e-6)),
              ('closed_625m', dict(mode='closed', fref=625e6 / 16, vc0=1.16, T=2.0e-6, tpre=0.8e-6)),
              ('closed_810m', dict(mode='closed', fref=810e6 / 16, vc0=1.33, T=2.0e-6, tpre=0.8e-6)),
              ('closed_hf125m_n4', dict(mode='closed', fref=125e6, n=4, vc0=1.08, T=1.8e-6, tpre=0.8e-6)),
              ('closed_hf156m_n4', dict(mode='closed', fref=156.25e6, n=4, vc0=1.16, T=1.8e-6, tpre=0.8e-6)),
              # cold start: VCTRL held at 0 V for 5 ns, then the loop acquires on its own
              ('cold_480m', dict(mode='closed', fref=30e6, vc0=0.0, T=4.0e-6, tpre=5e-9)),
              ('cold_810m', dict(mode='closed', fref=810e6 / 16, vc0=0.0, T=3.0e-6, tpre=5e-9)),
              # HOLD (r6): lock, assert HOLD at 2.0 us, observe the step and drift to 3.2 us
              ('hold_625m', dict(mode='closed', fref=625e6 / 16, vc0=1.16, T=3.2e-6, tpre=0.8e-6, hold_at=2.0e-6)),
              # same with HOLD at 4.0 us: 3.2 us of loop settling before HOLD (the 2.0 us case still
              # contains the loop's own settling tail; in use HOLD follows the lock counter)
              ('hold_625m_late', dict(mode='closed', fref=625e6 / 16, vc0=1.16, T=5.2e-6, tpre=0.8e-6, hold_at=4.0e-6)),
              # drift bench: HOLD from t=0, VCTRL pre-charged for 0.8 us then floating
              ('holddrift_625m', dict(mode='closed', fref=625e6 / 16, vc0=1.16, T=2.6e-6, tpre=0.8e-6, hold_at=0))] +
             [(f'open_vc{vc}', dict(mode='open', vctrl=vc)) for vc in (0.8, 3.3)],
    polyphase=[('nom_2g45_1vpp', dict(f=2.45e9, amp=0.5)), ('nom_2g4_1vpp', dict(f=2.4e9, amp=0.5)),
               ('nom_2g5_1vpp', dict(f=2.5e9, amp=0.5)), ('nom_2g45_0v4pp', dict(f=2.45e9, amp=0.2))],
    lo_ext=[('nom_ext_sin_2vpp_pad', dict(mode='ext', vpp=4.0)), ('nom_ext_sin_2vpp', dict(mode='ext', vpp=2.0)), ('nom_ext_sin_1vpp', dict(mode='ext', vpp=1.0)),
            ('nom_ext_sq_2vpp', dict(mode='ext', vpp=2.0, kind='sq')), ('nom_int', dict(mode='int')),
            ('nom_int_sq', dict(mode='int', kind='sq')), ('nom_int_2g4', dict(mode='int', f=2.4e9)), ('nom_int_2g5', dict(mode='int', f=2.5e9))])
CORNER_CASES = dict(
    lo_obs=[('c_2g5', dict(f=2.5e9, amp=0.45)), ('c_2g4_a0p3', dict(f=2.4e9, amp=0.3))],
    obs_pre4=[('c_1g', dict(f=1e9)), ('c_1g25', dict(f=1.25e9))],
    wordclk=[('c_810m_d5', dict(f=810e6, div=5)), ('c_810m_d20', dict(f=810e6, div=20)), ('c_625m_d5', dict(f=625e6, div=5)), ('c_625m_d20', dict(f=625e6, div=20))],
    diff_clk_rx=[('c', dict(f=1e8, amp=0.125))], clk_obs=[('c', dict(f=0.5e9))], ring_osc=[('c', {})], aosc=[('c', {})],
    clk_obs16=[('c', dict(f=0.5e9, sel=14)), ('c_sel15', dict(f=0.5e9, sel=15))],
    clockmux=[('c', dict(mode='switch'))],
    vco_replica=[('c_vc3.3', dict(vctrl=3.3)), ('c_vc0.9', dict(vctrl=0.9)), ('c_vc0.8', dict(vctrl=0.8)), ('c_vc1.2', dict(vctrl=1.2))], lo_ext=[('c', dict(mode='ext', vpp=4.0)), ('c_int', dict(mode='int', f=2.5e9))], pll_ring=[('c_vc3.3', dict(mode='open', vctrl=3.3)), ('c_vc0.8', dict(mode='open', vctrl=0.8))], prescale=[('c', dict(f=2.5e9, sel='D16'))], polyphase=[('c', dict(f=2.45e9, amp=0.5))])


def run_sims(block, cases, extracted=True, corners=False):
    jobs = []
    for name, kw in cases:
        if corners:
            for c, t, v in CORNERS:
                jobs.append((f'{name}_{c}_{t}_{v}', kw, c, t, v))
        else:
            jobs.append((name, kw, 'tt', 27, VDD))

    def one(j):
        name, kw, c, t, v = j
        try:
            tb = TB[block]
            return simulate(block, name, tb, kw, extracted=extracted, corner=c, temp=t, v=v)
        except Exception as e:
            return dict(case=name, error=repr(e), **{'pass': False})
    with ThreadPoolExecutor(int(os.environ.get("TIMING_JOBS", "3"))) as ex:
        return list(ex.map(one, jobs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blocks', default=','.join(TB))
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--extracted', action='store_true')
    ap.add_argument('--skip-layout', action='store_true')
    ap.add_argument('--skip-corners', action='store_true')
    ap.add_argument('--nominal-only', action='store_true', help='rerun nominal cases only, merging by case name')
    ap.add_argument('--cases', default='', help='with --nominal-only: comma list of case names (default all)')
    ap.add_argument('--corners-only', action='store_true')
    a = ap.parse_args()
    blocks = a.blocks.split(',')
    if a.quick:
        quick(blocks, extracted=a.extracted, tag='ext' if a.extracted else 'sch')
        return
    for b in blocks:
        rec_path = tf.SCRATCH / b / 'results.json'
        rec = json.loads(rec_path.read_text()) if rec_path.exists() else {}
        if a.corners_only:
            rec['corners'] = run_sims(b, CORNER_CASES[b], corners=True)
            rec_path.write_text(json.dumps(rec, indent=1, default=str))
            print(b, 'corners done', flush=True)
            continue
        if a.nominal_only:
            want = [c for c in NOMINAL[b] if not a.cases or c[0] in a.cases.split(',')]
            new = run_sims(b, want)
            rec = json.loads(rec_path.read_text()) if rec_path.exists() else {}
            keep = [r for r in rec.get('nominal', []) if Path(r.get('deck', '')).stem not in {c[0] for c in want}]
            rec['nominal'] = keep + new
            rec_path.write_text(json.dumps(rec, indent=1, default=str))
            print(b, 'nominal merged', flush=True)
            continue
        if not a.skip_layout:
            lay = tf.build_layout(b, max_row_width=WIDTH.get(b, 200))
            rec['layout'] = dict(drc_errors=lay['drc_errors'], lvs=lay['lvs'], devices=lay['devices'],
                                 size_um=lay['layout']['size_um'], area_um2=lay['layout']['area_um2'],
                                 image=lay['layout']['image'], klayout=lay.get('klayout'))
            rec_path.parent.mkdir(parents=True, exist_ok=True)
            rec_path.write_text(json.dumps(rec, indent=1, default=str))
        if 'layout' not in rec and (tf.SCRATCH / b / 'layout' / 'layout-report.json').exists():
            import layout_engine as le
            lr = json.loads((tf.SCRATCH / b / 'layout' / 'layout-report.json').read_text())
            txt = (tf.SCRATCH / b / 'layout' / 'lvs.txt').read_text()
            fin = txt[txt.rfind('Final result'):]
            rec['layout'] = dict(drc_errors=le.drc_errors(lr['drc_count_raw']),
                                 lvs=dict(unique_match='Circuits match uniquely' in fin, summary=fin.strip()[:300]),
                                 devices=lr['devices'], size_um=lr['size_um'], area_um2=lr['area_um2'], image=lr['image'])
        rec['nominal'] = run_sims(b, NOMINAL[b])
        rec['safe'] = safe_cases(b)
        rec_path.write_text(json.dumps(rec, indent=1, default=str))
        if not a.skip_corners and CORNER_CASES[b]:
            rec['corners'] = run_sims(b, CORNER_CASES[b], corners=True)
            rec_path.write_text(json.dumps(rec, indent=1, default=str))
        print(b, 'done', flush=True)


if __name__ == '__main__':
    main()
