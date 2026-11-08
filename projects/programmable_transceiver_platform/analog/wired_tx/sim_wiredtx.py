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


def pwl_bits(name, node, times_vals, vdd, edge=100e-12):
    pts = ['0', f'{times_vals[0][1]*vdd:g}']
    level = times_vals[0][1]
    for t, v in times_vals[1:]:
        if v != level:
            pts += [f'{t:.6e}', f'{level*vdd:g}', f'{t+edge:.6e}', f'{v*vdd:g}']
            level = v
    return f'V{name} {node} 0 PWL({" ".join(pts)})'


def phase_sources(rate, vdd, stopped=False, bpc=4):
    """Four ring phases (PH0 first, 90 deg apart), 50 % duty, ring = rate/bpc,
    plus the bits-per-cycle mode pins (bpc 4: quarter, 2: MODE_H, 1: MODE_F)."""
    tq = bpc / rate
    tr = min(50e-12, tq / 16)
    out = []
    for k, ph in enumerate(('0', '90', '180', '270')):
        if stopped:
            out.append(f'VPH{ph} WTX_PH{ph} 0 {vdd if ph in ("180", "270") else 0}')
        else:
            out.append(f'VPH{ph} WTX_PH{ph} 0 PULSE(0 {vdd} {k*tq/4:.6e} {tr} {tr} {tq/2-tr:.6e} {tq:.6e})')
    out += [f'VMODEH MODE_H 0 {vdd if bpc == 2 else 0}', f'VMODEF MODE_F 0 {vdd if bpc == 1 else 0}']
    return out


def build(dut, subckt, *, rate, words, word_t0, tstop, vdd=3.3, corner='typical', temp=27, bpc=4,
          mode='serial', codes=(109, 32, 125), en=(1, 1, 0), wtx_ext=0, dx_pattern=None,
          load_f=20e-15, extra='', probes=None, ser_on=2e-9):
    text = Path(dut).read_text()
    ports = ports_of(text, subckt)
    tw = 20 / rate
    nets = {p: p for p in ports}
    lines = ['* pt_wiredtx transient testbench', tools.model_header(corner, temp), f'.include {Path(dut).name}',
             f'VDD VDD 0 {vdd}', 'VSS VSS 0 0']
    lines += phase_sources(rate, vdd, bpc=bpc)
    lines.append(f'VSER SER_EN 0 PWL(0 0 {ser_on} 0 {ser_on+100e-12} {vdd})')
    lines.append(f'VEXT WTX_EXT 0 {wtx_ext*vdd}')
    if dx_pattern is None:
        lines.append('VDX DX 0 0')
    else:
        lines.append(dx_pattern)
    for nm, v in zip(('EN_MAIN', 'EN_POST', 'EN_TMDS'), en):
        lines.append(f'V{nm} {nm} 0 {v*vdd}')
    lines.append('VISO ISLAND_OFF 0 0')
    lines.append(f'IREF VDD IBIAS 10u')
    for b, code in zip(('MAIN', 'POST', 'TMDS'), codes):
        for k, bit in enumerate(code_bits(code)):
            lines.append(f'V{b}C{k} {b}_CODE{k} 0 {bit*vdd}')
    # data words: launched T_word/4 after each WORD_CLK rising edge
    for i in range(20):
        tv = [(0.0, words[0][i])]
        for k, w in enumerate(words):
            tv.append((word_t0 + k * tw + tw / 4, w[i]))
        lines.append(pwl_bits(f'D{i}', f'D{i}', tv, vdd))
    for o in ['CMD_MAIN_P', 'CMD_MAIN_N', 'CMD_POST_P', 'CMD_POST_N', 'CMD_TMDS_P', 'CMD_TMDS_N']:
        if load_f:
            lines.append(f'C{o} {o} 0 {load_f}')
    lines.append(f'CWCK WORD_CLK 0 50f')
    # tail replicas of the pad output stage (MAIN/POST: 8x4 fingers, TMDS: 8x2 fingers of W20/L1)
    for b, m in (('MAIN', 32), ('POST', 32), ('TMDS', 16)):
        lines.append(f'VT{b} T{b} 0 1.0')
        lines.append(f'XT{b} T{b} {b}_BIAS 0 0 nfet_03v3 w=20u l=1u m={m}')
    lines.append(extra)
    lines.append('X0 ' + ' '.join(nets[p] for p in ports) + f' {subckt}')
    probes = probes or ['WTX_PH0', 'WORD_CLK', 'CMD_MAIN_P', 'CMD_MAIN_N', 'CMD_POST_P', 'CMD_POST_N',
                        'CMD_TMDS_P', 'CMD_TMDS_N', 'MAIN_BIAS', 'TMDS_BIAS', 'WTX_EXT_DATA']
    vecs = ' '.join(f'v({p})' for p in probes) + ' i(VTMAIN) i(VTPOST) i(VTTMDS) i(VDD)'
    # ngspice sizes its output buffer for every node at the print step, which
    # overflows for long runs of the extracted netlist: print on a 20 ps grid
    # (interpolated) while limiting the internal step to 4 ps.
    tstep = 20e-12 * max(1.0, 2.5e9 / rate)
    lines += ['.options reltol=1e-3 method=gear interp', f'.tran {tstep:.3e} {tstop:.6e} 0 4e-12', '.control',
              f'save {vecs}', 'set wr_singlescale', 'run', 'wrdata wave.txt ' + vecs,
              '.endc', '.end']
    return '\n'.join(lines) + '\n', probes + ['I_TMAIN', 'I_TPOST', 'I_TTMDS', 'I_VDD']


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


def align(bits, expected):
    best = None
    n = len(bits)
    for lat in range(0, len(expected) - n + 1):
        err = int(np.sum(bits != np.array(expected[lat:lat + n])))
        if best is None or err < best[1]:
            best = (lat, err)
    return best


def run_case(work, dut, subckt, *, rate, nwords=10, corner='typical', temp=27, vdd=3.3, mode='serial', bpc=4,
             words=None, codes=(109, 32, 125), en=(1, 1, 0), extra='', tag='case', mounts=()):
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    tw = 20 / rate
    ser_on = 2e-9
    # pass 1: word clock phase
    pdir = work / f'{tag}_phase'; pdir.mkdir(exist_ok=True)
    (pdir / Path(dut).name).write_text(Path(dut).read_text())
    zero = [[0] * 20]
    deck, names = build(dut, subckt, rate=rate, words=zero, word_t0=1, tstop=ser_on + 3 * tw, vdd=vdd,
                        corner=corner, temp=temp, codes=codes, en=en, extra=extra, ser_on=ser_on, bpc=bpc)
    (pdir / 'tb.sp').write_text(deck)
    _, log = tools.ngspice(pdir, 'tb.sp', mounts=mounts)
    w = tools.read_wrdata(pdir / 'wave.txt', names)
    rises = crossings(w['time'], w['WORD_CLK'], rising=True)
    rises = rises[rises > ser_on]
    if len(rises) < 2:
        return dict(ok=False, reason='WORD_CLK not running', log_tail=log[-2000:])
    word_t0 = float(rises[0])
    measured_tw = float(np.mean(np.diff(rises)))
    # pass 2: data
    if words is None:
        bits = prbs7_bits(20 * nwords)
        words = [bits[20 * k:20 * k + 20] for k in range(nwords)]
    nwords = len(words)
    tstop = word_t0 + (nwords + 3) * tw
    ddir = work / f'{tag}_data'; ddir.mkdir(exist_ok=True)
    (ddir / Path(dut).name).write_text(Path(dut).read_text())
    deck, names = build(dut, subckt, rate=rate, words=words, word_t0=word_t0, tstop=tstop, vdd=vdd,
                        corner=corner, temp=temp, codes=codes, en=en, extra=extra, ser_on=ser_on, bpc=bpc)
    (ddir / 'tb.sp').write_text(deck)
    _, log = tools.ngspice(ddir, 'tb.sp', mounts=mounts)
    w = tools.read_wrdata(ddir / 'wave.txt', names)
    expected = [b for wd in words for b in wd]
    t0 = word_t0 + 2 * tw
    t1 = word_t0 + (nwords - 1) * tw
    res = dict(bit_rate_bps=rate, bits_per_ring_cycle=bpc, ring_hz=rate / bpc, corner=corner, temp_c=temp, vdd=vdd,
               word_clk_period_s=measured_tw, word_t0_s=word_t0)
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
    res['tail_current_a'] = {b: float(-np.mean(w[f'I_T{b}'][sel])) for b in ('MAIN', 'POST', 'TMDS')}
    res['bias_v'] = {b: float(np.mean(w[f'{b}_BIAS'][sel])) for b in ('MAIN', 'TMDS')}
    res['supply_current_avg_a'] = float(-np.mean(w['I_VDD'][sel]))
    m = res.get('CMD_MAIN_N', {})
    res['ok'] = bool(m.get('errors', 1) == 0 and m.get('bits_compared', 0) >= 20 * (nwords - 4))
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
