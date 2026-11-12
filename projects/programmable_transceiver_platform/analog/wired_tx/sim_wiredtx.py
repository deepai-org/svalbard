"""Transient testbench for pt_wiredtx (schematic or extracted netlist).

Two passes per case: (1) a short run measures the WORD_CLK phase after the
serializer enable; (2) the data run launches 20-bit word pairs on WORD_CLK rising
edges (+T_word/4, standing in for the RTL clock-to-q) and decodes the serial
stream at the pre-driver command outputs.  The decoded stream is compared with
the expected bit order (D0 first) after a latency search.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import tools

VTH = 1.65


def prbs7_bits(n, seed=0x7F):
    s = seed
    out = []
    for _ in range(n):
        b = ((s >> 6) ^ (s >> 5)) & 1
        s = ((s << 1) | b) & 0x7F
        out.append(b)
    return out


def code_bits(v):
    return [(v >> k) & 1 for k in range(8)]


def ports_of(spice_text, subckt):
    joined = spice_text.replace('\n+', ' ')
    for line in joined.splitlines():
        if line.lower().startswith('.subckt ') and line.split()[1] == subckt:
            return line.split()[2:]
    raise ValueError(subckt + ' not found')


# Stimuli are breakpoint-free behavioural sources.  PWL/PULSE corners make ngspice cut the step
# to ~delmin at every corner; with gear integration the current unknowns attached to pF of gate
# and wiring capacitance (C/h ~ 1e5 S) then cannot converge to abstol (1 pA) in floating point and
# the run aborts ("Timestep too small", reported on a source branch).  Real drivers produce
# smooth edges; tanh edges with the same 10-90 % time are used instead (no simulator options
# changed).
SMOOTH = True


def _step(t0, edge):
    # 0 -> 1 around t0 + edge/2 with 10-90 % time = edge (tanh: 10-90 % = 2.197 / k)
    k = 2.197 / edge
    return f'(0.5+0.5*tanh({k:.6e}*(time-{t0 + edge / 2:.6e})))'


def pwl_bits(name, node, times_vals, vdd, edge=100e-12):
    level = times_vals[0][1]
    if not SMOOTH:
        pts = ['0', f'{level*vdd:g}']
        for t, v in times_vals[1:]:
            if v != level:
                pts += [f'{t:.6e}', f'{level*vdd:g}', f'{t+edge:.6e}', f'{v*vdd:g}']
                level = v
        return f'V{name} {node} 0 PWL({" ".join(pts)})'
    terms = [f'{level*vdd:g}']
    for t, v in times_vals[1:]:
        if v != level:
            terms.append(f'{(v - level) * vdd:+g}*{_step(t, edge)}')
            level = v
    return f'B{name} {node} 0 V={" ".join(terms)}'


def phase_sources(rate, vdd, stopped=False, bpc=4, fallback=False):
    """Four ring phases (PH0 first, 90 deg apart), 50 % duty, ring = rate/bpc,
    plus the bits-per-cycle mode pins (bpc 4: quarter, 2: MODE_H, 1: MODE_F)."""
    tq = bpc / rate
    tr = min(50e-12, tq / 16)
    out = []
    for k, ph in enumerate(('0', '90', '180', '270')):
        if stopped:
            out.append(f'VPH{ph} WTX_PH{ph} 0 {vdd if ph in ("180", "270") else 0}')
        elif SMOOTH:
            # periodic 50 % square with tanh edges (10-90 % = tr): rises at k*tq/4 + tr/2
            kk = 2.197 / tr
            ph_ = f'(time-{k*tq/4 + tr/2:.6e})'
            out.append(f'BPH{ph} WTX_PH{ph} 0 V={vdd}*(0.5+0.5*tanh({kk*tq/(2*3.141592653589793):.6e}'
                       f'*sin(2*3.141592653589793*{ph_}/{tq:.6e})))')
        else:
            out.append(f'VPH{ph} WTX_PH{ph} 0 PULSE(0 {vdd} {k*tq/4:.6e} {tr} {tr} {tq/2-tr:.6e} {tq:.6e})')
    # rate field: 00 quarter, 10 half, 01 full (compact core); 11 = generic half-rate fallback
    if fallback:
        assert bpc == 2, 'the generic fallback serializer runs half rate'
        out += [f'VMODEH MODE_H 0 {vdd}', f'VMODEF MODE_F 0 {vdd}']
    else:
        out += [f'VMODEH MODE_H 0 {vdd if bpc == 2 else 0}', f'VMODEF MODE_F 0 {vdd if bpc == 1 else 0}']
    return out


# Output resistance of the real drivers of the DUT inputs (nothing on chip is a 0-ohm source):
# ring phases come from the clockmux ct_mux4 output stage (2 x INV 3/6 um, ~150 ohm), word bits
# and controls from standard-cell flops / register bits (~1 kohm).  Ideal 0-ohm sources made each
# source's branch current a pure C/h image of the gate nodes' Newton updates; at source
# breakpoints ngspice could not converge it and aborted ("Timestep too small ... vd19#branch").
R_PHASE, R_LOGIC = 150.0, 1000.0
# 40-bit boundary: the digital launches D0..D39 on WORD_CLK40 rising; LAUNCH_S models its clock-to-Q
# plus routing (session 7; the earlier T_word/4 launch, 1.5-2.6 ns, was later than the block's own
# W40 -> load budget allows at 3.24 Gb/s core and is not what the digital does).
LAUNCH_S = float(__import__('os').environ.get('WTX_LAUNCH_S', '1.0e-9'))


PESSIMISTIC = __import__('os').environ.get('WTX_PESSIMISTIC', '0') == '1'


def pessimize(text, rg_per_um=20.0, cdev_per_um=0.47e-15, cscale=1.15):
    """spec/design-assumptions.md pessimistic values on an extracted netlist (simulation only):
    gate R 200 ohm per 10 um device (rg_per_um * w in series with every gate), +25 % device C
    (Cgg ~ 1.9 fF/um at L = 0.28 um -> +0.47 fF/um of width from the internal gate node to the source),
    +15 % on every extracted capacitor."""
    import re
    out, k = [], 0
    for line in text.splitlines():
        t = line.split()
        if t and t[0][:1] in 'Cc' and len(t) >= 4 and not t[0].lower().startswith('cc'):
            m = re.fullmatch(r'([-+0-9.eE]+)([a-zA-Z]*)', t[3])
            if m:
                t[3] = f'{float(m.group(1)) * cscale:g}{m.group(2)}'
                line = ' '.join(t)
        elif t and t[0][:1] in 'Xx' and len(t) >= 6 and 'fet_03v3' in t[5]:
            w = next((float(x[2:].rstrip('u')) for x in t if x.startswith('w=')), 1.0)
            k += 1
            g = f'pg_{k}'
            out.append(f'RPG{k} {t[2]} {g} {rg_per_um * w:g}')
            out.append(f'CPG{k} {g} {t[3]} {cdev_per_um * w * 1e15:g}f')
            t[2] = g
            line = ' '.join(t)
        out.append(line)
    return '\n'.join(out) + '\n'


OPTIMISTIC = __import__('os').environ.get('WTX_OPTIMISTIC', '0') == '1'


def scale_c(text, k):
    import re
    out = []
    for line in text.splitlines():
        t = line.split()
        if t and t[0][:1] in 'Cc' and len(t) >= 4:
            m = re.fullmatch(r'([-+0-9.eE]+)([a-zA-Z]*)', t[3])
            if m:
                t[3] = f'{float(m.group(1)) * k:g}{m.group(2)}'
                line = ' '.join(t)
        out.append(line)
    return '\n'.join(out) + '\n'


def dut_text(path):
    """WTX_PESSIMISTIC=1: slow bound (Rg, +25 % device C, +15 % wire C).  WTX_OPTIMISTIC=1: fast bound for
    hold / race, overlap glitches and ringing (MANDATE: uncertain values bounded on both sides): extracted
    C -15 %, no gate R (the models carry none), device C as modelled (fT as modelled = the high end)."""
    t = Path(path).read_text()
    if PESSIMISTIC:
        return pessimize(t)
    if OPTIMISTIC:
        return scale_c(t, 0.85)
    return t


REP = {4: 1, 2: 2, 1: 4}   # bits per ring cycle -> repetition factor (WT12 / WT19)


# Session 8 / T26 contract (digital timing reply): D0..D19 come from FALLING-edge flops (launched at the
# WORD_CLK40 fall before the rise, valid until the next fall), D20..D39 from RISING-edge flops.  Worst-case
# (ss) clock-to-Q + buffer + route: LAUNCH_LO after the fall, LAUNCH_HI after the rise.
LAUNCH_LO = float(__import__('os').environ.get('WTX_LAUNCH_LO', '2.0e-9'))
LAUNCH_HI = float(__import__('os').environ.get('WTX_LAUNCH_HI', '3.5e-9'))


def launch_offset(tw, w40, half=0):
    """Data change time relative to the WORD_CLK40 rising edge word_t0 (period 2 tw)."""
    if not w40:
        return tw / 4
    return -tw + LAUNCH_LO if half == 0 else LAUNCH_HI


def realign_t0(t, wck, word_t0, tol=0.1e-9):
    """The /5 word counter is not reset, so its start state (hence the WORD_CLK40 phase) can differ
    between the phase pass and the data pass (seen: one register period, 1.6 ns at 2.5 Gb/s, which
    put the launch on the wrong side of the load).  Returns the data-pass WORD_CLK40 rising edge
    nearest the assumed word_t0, or None if they agree within tol."""
    r = crossings(t, wck, rising=True)
    if not len(r):
        return None
    k = int(np.argmin(abs(r - word_t0)))
    return None if abs(r[k] - word_t0) < tol else float(r[k])
_NO_R = ('VDD', 'VSS', 'VT', 'VX')   # VX*: AC-coupled receiver sources (sim_integration)


def driver_impedance(lines):
    out = []
    for l in lines:
        p = l.split()
        if p and l[:1] in 'VB' and not p[0].upper()[1:].startswith(tuple(n[1:] for n in _NO_R)) and len(p) > 3 \
                and p[2] == '0':
            node = p[1]
            r = R_PHASE if node.startswith('WTX_PH') else R_LOGIC
            out += [' '.join([p[0], node + '_drv'] + p[2:]), f'R{p[0][1:]}_drv {node}_drv {node} {r:g}']
        else:
            out.append(l)
    return out


def build(dut, subckt, *, rate, words, word_t0, tstop, vdd=3.3, corner='typical', temp=27, bpc=4,
          mode='serial', codes=(109, 32, 125), en=(1, 1, 0), wtx_ext=0, dx_pattern=None,
          load_f=20e-15, extra='', probes=None, ser_on=2e-9, fallback=False, post_pol=0):
    text = Path(dut).read_text()
    ports = ports_of(text, subckt)
    tw = 20 / (rate * REP[bpc])        # WT19: words are CORE words (digital repeats the user bits)
    nets = {p: p for p in ports}
    lines = ['* pt_wiredtx transient testbench', tools.model_header(corner, temp), f'.include {Path(dut).name}',
             f'VDD VDD 0 {vdd}', 'VSS VSS 0 0']
    lines += phase_sources(rate, vdd, bpc=bpc, fallback=fallback)
    lines.append(pwl_bits('SER', 'SER_EN', [(0.0, 0), (ser_on, 1)], vdd))
    lines.append(f'VEXT WTX_EXT 0 {wtx_ext*vdd}')
    if dx_pattern is None:
        lines.append('VDX DX 0 0')
    else:
        lines.append(dx_pattern)
    for nm, v in zip(('EN_MAIN', 'EN_POST', 'EN_TMDS'), en):
        if nm in ports:
            lines.append(f'V{nm} {nm} 0 {v*vdd}')
    lines.append('VISO ISLAND_OFF 0 0')
    if 'POST_POL' in ports:      # IX-9 postcursor polarity (0 = de-emphasis)
        lines.append(f'VPOL POST_POL 0 {post_pol * vdd}')
    lines.append(f'IREF VDD IBIAS 10u')
    for b, code in zip(('MAIN', 'POST', 'TMDS'), codes):
        if f'{b}_CODE0' not in ports:
            continue
        for k, bit in enumerate(code_bits(code)):
            lines.append(f'V{b}C{k} {b}_CODE{k} 0 {bit*vdd}')
    # data words: launched T_word/4 after each WORD_CLK rising edge (20-bit port), or, with the
    # 40-bit boundary (D20..D39 present), pairs of words launched T_word/4 after each WORD_CLK40
    # rising edge (word_t0 is then a WORD_CLK40 rising edge): word 2m on D0..D19, 2m+1 on D20..D39
    if 'D39' in ports:
        pairs = [(words[2 * m], words[2 * m + 1] if 2 * m + 1 < len(words) else words[2 * m])
                 for m in range((len(words) + 1) // 2)]
        for i in range(40):
            h, j = divmod(i, 20)
            tv = [(0.0, pairs[0][h][j])] + [(word_t0 + 2 * m * tw + launch_offset(tw, True, h), pr[h][j])
                                            for m, pr in enumerate(pairs)]
            lines.append(pwl_bits(f'D{i}', f'D{i}', tv, vdd))
    else:
        for i in range(20):
            tv = [(0.0, words[0][i])]
            for k, w in enumerate(words):
                tv.append((word_t0 + k * tw + tw / 4, w[i]))
            lines.append(pwl_bits(f'D{i}', f'D{i}', tv, vdd))
    for o in ['CMD_MAIN_P', 'CMD_MAIN_N', 'CMD_POST_P', 'CMD_POST_N', 'CMD_TMDS_P', 'CMD_TMDS_N']:
        if load_f and o in ports:
            lines.append(f'C{o} {o} 0 {load_f}')
    lines.append(f'CWCK WORD_CLK 0 50f')
    if 'WORD_CLK40' in ports:
        lines.append('CWCK40 WORD_CLK40 0 50f')
    # Tail-gate load of the pad output stage (MAIN/POST: 8x4 fingers, TMDS: 8x2 fingers of W20/L1,
    # ~1-3 pF on <b>_BIAS), with the drain tied to the source.  The tail current is NOT measured
    # here: an ideal source on the drain of these pF devices (the earlier bench) makes the source's
    # branch current carry C/h times the gate node's Newton update, which cannot converge once a
    # source breakpoint cuts the step; ngspice 43 and 47 then abort ("Timestep too small ...
    # vttmds#branch" at ss/22/3.15, "vtpost#branch" elsewhere) at the end of a phase-source ramp.
    # Tail currents are measured by the DC benches (sim_static.dac_sweep / quiescent).
    for b, m in (('MAIN', 32), ('POST', 32), ('TMDS', 16)):
        if f'{b}_BIAS' in ports:
            lines.append(f'XT{b} 0 {b}_BIAS 0 0 nfet_03v3 w=20u l=1u m={m}')
    lines.append(extra)
    lines = driver_impedance(lines)
    lines.append('X0 ' + ' '.join(nets[p] for p in ports) + f' {subckt}')
    probes = probes or ['WTX_PH0', 'WORD_CLK40' if 'WORD_CLK40' in ports else 'WORD_CLK', 'CMD_MAIN_P', 'CMD_MAIN_N', 'CMD_POST_P', 'CMD_POST_N',
                        'CMD_TMDS_P', 'CMD_TMDS_N', 'MAIN_BIAS', 'TMDS_BIAS', 'WTX_EXT_DATA']
    probes = [p_ for p_ in probes if p_ in ports]
    vecs = ' '.join(f'v({p})' for p in probes) + ' i(VDD)'
    # ngspice sizes its output buffer for every node at the print step, which overflows for the
    # extracted netlist without `interp` ("memory required ... more than available"): print on a
    # >= 20 ps grid, interpolated, internal step limited to 4 ps.  (Corrupt interpolated samples
    # were seen only with a print grid finer than the internal step, 1 ps; not used here.)
    tstep = 20e-12 * max(1.0, 2.5e9 / rate)
    lines += ['.options reltol=1e-3 method=gear interp', f'.tran {tstep:.3e} {tstop:.6e} 0 4e-12', '.control',
              f'save {vecs}', 'set wr_singlescale', 'run', 'wrdata wave.txt ' + vecs,
              '.endc', '.end']
    return '\n'.join(lines) + '\n', probes + ['I_VDD']


def crossings(t, v, th=VTH, rising=None):
    s = v > th
    idx = np.nonzero(s[1:] != s[:-1])[0]
    out = []
    for i in idx:
        r = s[i + 1]
        if rising is not None and r != rising:
            continue
        f = (th - v[i]) / (v[i + 1] - v[i])
        out.append(t[i] + f * (t[i + 1] - t[i]))
    return np.array(out)


def decode(w, node, rate, t_start, t_end, vdd=3.3):
    ui = 1.0 / rate
    t = w['time']; v = w[node]
    xs = crossings(t, v)
    xs = xs[(xs > t_start) & (xs < t_end)]
    if len(xs) < 4:
        return None
    ph = np.mod(xs, ui)
    # circular mean of crossing phase
    ang = np.angle(np.mean(np.exp(2j * np.pi * ph / ui)))
    cross_phase = (ang / (2 * np.pi) * ui) % ui
    dev = (np.mod(ph - cross_phase + ui / 2, ui) - ui / 2)
    jitter_pp = float(dev.max() - dev.min())
    centre = (cross_phase + ui / 2) % ui
    ts = np.arange(t_start - (t_start % ui) + centre, t_end, ui)
    vs = np.interp(ts, t, v)
    bits = (vs > VTH).astype(int)
    margin = float(np.min(np.abs(vs - VTH)))
    return dict(bits=bits, samples=vs, cross_phase=cross_phase, jitter_pp=jitter_pp,
                eye_width_est=ui - jitter_pp, vertical_margin=margin, n_cross=len(xs))


def sim_abort(log):
    """Return the ngspice abort line (e.g. 'Timestep too small ...') or None."""
    for line in log.replace('\r', '\n').splitlines():
        # 'too small' alone also matched the pad models' harmless "IKR too small - model effect disabled"
        # load warnings (session 6), which made every pad-model deck look aborted
        if 'timestep too small' in line.lower() or 'simulation(s) aborted' in line:
            return line.strip()[:200]
    return None


def align(bits, expected):
    best = None
    n = len(bits)
    for lat in range(0, len(expected) - n + 1):
        err = int(np.sum(bits != np.array(expected[lat:lat + n])))
        if best is None or err < best[1]:
            best = (lat, err)
    return best


def run_case(work, dut, subckt, *, rate, nwords=10, corner='typical', temp=27, vdd=3.3, mode='serial', bpc=4,
             words=None, codes=(109, 32, 125), en=(1, 1, 0), extra='', tag='case', mounts=(), fallback=False):
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    rep = REP[bpc]
    tw = 20 / (rate * rep)
    ser_on = 2e-9
    # pass 1: word clock phase
    pdir = work / f'{tag}_phase'; pdir.mkdir(exist_ok=True)
    (pdir / Path(dut).name).write_text(dut_text(dut))
    zero = [[0] * 20]
    deck, names = build(dut, subckt, rate=rate, words=zero, word_t0=1, tstop=ser_on + 8 * tw, vdd=vdd,
                        corner=corner, temp=temp, codes=codes, en=en, extra=extra, ser_on=ser_on, bpc=bpc,
                        fallback=fallback)
    (pdir / 'tb.sp').write_text(deck)
    _, log = tools.ngspice(pdir, 'tb.sp', mounts=mounts)
    abort = sim_abort(log)
    if abort:
        return dict(ok=False, reason='simulator abort (phase pass): ' + abort, dut_sha256=tools.sha(dut))
    w = tools.read_wrdata(pdir / 'wave.txt', names)
    wck = 'WORD_CLK40' if 'WORD_CLK40' in w else 'WORD_CLK'
    rises = crossings(w['time'], w[wck], rising=True)
    rises = rises[rises > ser_on]
    if wck == 'WORD_CLK40' and len(rises) > 2:
        rises = rises[1:]       # first WORD_CLK40 period after the enable may be short (start-up)
    if len(rises) < 2:
        return dict(ok=False, reason='WORD_CLK not running', dut_sha256=tools.sha(dut), log_tail=log[-2000:])
    word_t0 = float(rises[0])
    measured_tw = float(np.mean(np.diff(rises))) / (2 if wck == 'WORD_CLK40' else 1)
    # pass 2: data
    if words is None:
        ubits = prbs7_bits(20 * nwords // rep)
        bits = [b for b in ubits for _ in range(rep)]       # the digital's repetition (WT19)
        words = [bits[20 * k:20 * k + 20] for k in range(nwords)]
    else:
        ubits = [b for wd in words for b in wd][::rep]
    nwords = len(words)
    tstop = word_t0 + (nwords + 3) * tw
    ddir = work / f'{tag}_data'; ddir.mkdir(exist_ok=True)
    (ddir / Path(dut).name).write_text(dut_text(dut))
    realigned = 0
    for _ in range(3):
        tstop = word_t0 + (nwords + 3) * tw
        deck, names = build(dut, subckt, rate=rate, words=words, word_t0=word_t0, tstop=tstop, vdd=vdd,
                            corner=corner, temp=temp, codes=codes, en=en, extra=extra, ser_on=ser_on, bpc=bpc,
                            fallback=fallback)
        (ddir / 'tb.sp').write_text(deck)
        _, log = tools.ngspice(ddir, 'tb.sp', mounts=mounts)
        abort = sim_abort(log)
        if abort:
            return dict(ok=False, reason='simulator abort: ' + abort, dut_sha256=tools.sha(dut), bit_rate_bps=rate,
                        bits_per_ring_cycle=bpc, ring_hz=rate / bpc, corner=corner, temp_c=temp, vdd=vdd,
                        log_tail=log[-1500:])
        w = tools.read_wrdata(ddir / 'wave.txt', names)
        nt0 = realign_t0(w['time'], w[wck], word_t0) if wck == 'WORD_CLK40' else None
        if nt0 is None:
            break
        word_t0, realigned = nt0, realigned + 1
    expected = list(ubits)
    t0 = word_t0 + 2 * tw
    t1 = word_t0 + (nwords - 1) * tw
    res = dict(dut_sha256=tools.sha(dut), serializer='generic (fallback, rate code 11)' if fallback else 'compact core',
               bit_rate_bps=rate, bits_per_ring_cycle=bpc, ring_hz=rate / bpc, corner=corner, temp_c=temp, vdd=vdd,
               word_clk_period_s=measured_tw, word_t0_s=word_t0, launch_lo_after_fall_s=LAUNCH_LO, launch_hi_after_rise_s=LAUNCH_HI,
               word_t0_realigned=realigned)
    for node in ('CMD_MAIN_N', 'CMD_MAIN_P'):
        d = decode(w, node, rate, t0, t1)
        if d is None:
            res[node] = dict(ok=False, reason='no transitions')
            continue
        bits = d['bits'] if node == 'CMD_MAIN_N' else 1 - d['bits']
        lat, err = align(bits, expected)
        res[node] = dict(bits_compared=int(len(bits)), errors=int(err), latency_bits=int(lat),
                         jitter_pp_s=d['jitter_pp'], eye_width_est_s=d['eye_width_est'],
                         vertical_margin_v=d['vertical_margin'])
    # postcursor: CMD_POST_P sampled on the main data grid must equal main delayed by one UI
    dm = decode(w, 'CMD_MAIN_N', rate, t0, t1)
    if dm is not None and en[1]:
        ui = 1.0 / rate
        ts = np.arange(t0 - (t0 % ui) + (dm['cross_phase'] + ui / 2) % ui, t1, ui)
        main = (np.interp(ts, w['time'], w['CMD_MAIN_N']) > VTH).astype(int)
        post = (np.interp(ts, w['time'], w['CMD_POST_P']) > VTH).astype(int)
        res['CMD_POST_P'] = {f'mismatches_vs_main_delayed_{k}ui': int(np.sum(post[k:] != main[:len(main) - k]))
                             for k in (0, 1, 2)}
        res['CMD_POST_P']['bits_compared'] = int(len(post) - 1)
    sel = w['time'] > t0
    res['tail_current_a'] = None   # measured by sim_static (DC), see build()
    res['bias_v'] = {b: float(np.mean(w[f'{b}_BIAS'][sel])) for b in ('MAIN', 'TMDS') if f'{b}_BIAS' in w}
    res['supply_current_avg_a'] = float(-np.mean(w['I_VDD'][sel]))
    m = res.get('CMD_MAIN_N', {})
    res['ok'] = bool(m.get('errors', 1) == 0 and m.get('bits_compared', 0) >= 20 * (nwords - 4) // rep
                     and (not en[1] or res.get('CMD_POST_P', {}).get('mismatches_vs_main_delayed_1ui', 1) == 0))
    return res


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--dut', default=str(tools.HERE / 'wiredtx.spice'))
    ap.add_argument('--subckt', default='pt_wiredtx')
    ap.add_argument('--rate', type=float, default=2.5e9)
    ap.add_argument('--corner', default='typical')
    ap.add_argument('--temp', type=float, default=27)
    ap.add_argument('--vdd', type=float, default=3.3)
    ap.add_argument('--nwords', type=int, default=8)
    ap.add_argument('--bpc', type=int, default=4)
    ap.add_argument('--work', default=str(tools.SCRATCH / 'sim'))
    ap.add_argument('--tag', default='case')
    a = ap.parse_args()
    r = run_case(a.work, a.dut, a.subckt, rate=a.rate, nwords=a.nwords, corner=a.corner, temp=a.temp,
                 vdd=a.vdd, tag=a.tag, bpc=a.bpc)
    print(json.dumps(r, indent=2))
