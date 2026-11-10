"""pt_wiredtx driving the pads family's extracted wired-TX output stage.

Load models (owned by analog/pads, used read-only):
  * generated/steering-buffer/physical.spice   tx_steering_buffer_flat_physical (x6)
  * generated/wired-transmit-extracted-c.spice tx_protected_pad
External network per mode, after a 1 ohm / 1 nH bond per leg (pads fixture):
  serial  100 ohm differential board load, on-chip termination on, TERM_VCM
          held by an ideal 1.65 V source (stand-in for the pads termination
          buffer), optional short lossy channel before the load;
  tmds    on-chip termination off, independent 3.3 V supply through 50 ohm
          per leg (TMDS sink termination), TMDS branch only;
  ext     WTX_EXT=1: a behavioural stand-in for the shared diff_clk_rx output
          (DX) drives the MAIN branch; serializer clock stopped.
The pads netlist was produced and validated by the pads agent with a patched
ngspice47; here it is simulated with the analog image's ngspice 43 for a
functional demonstration only.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import sim_wiredtx as S
import tools

PADS = tools.PROJECT / 'analog/pads/generated'
STEER = PADS / 'steering-buffer/physical.spice'
PAD = PADS / 'wired-transmit-extracted-c.spice'
BRANCH_CMDS = ['CMD_MAIN_P', 'CMD_MAIN_N', 'CMD_POST_P', 'CMD_POST_N', 'CMD_TMDS_P', 'CMD_TMDS_N']


def clean_lib(text):
    return '\n'.join(l for l in text.splitlines() if not l.lower().startswith(('.lib', '.include')))


def channel(lines, sections=10, length_cm=5.0, z0=50.0, er=4.2, r_per_cm=0.6):
    """Single-ended RLC ladder per leg (lossy microstrip stand-in, DC + skin-ish R)."""
    td_cm = (er ** 0.5) / 3e10  # s per cm
    l_cm = z0 * td_cm
    c_cm = td_cm / z0
    seg = length_cm / sections
    for leg in ('P', 'N'):
        prev = f'BOARD_{leg}'
        for i in range(sections):
            mid, nxt = f'CH{leg}{i}M', (f'FAR_{leg}' if i == sections - 1 else f'CH{leg}{i}')
            lines += [f'RCH{leg}{i} {prev} {mid} {r_per_cm*seg:.4g}', f'LCH{leg}{i} {mid} {nxt} {l_cm*seg:.4g}',
                      f'CCH{leg}{i} {nxt} 0 {c_cm*seg:.4g}']
            prev = nxt
    return dict(sections=sections, length_cm=length_cm, z0_ohm=z0, er=er, r_ohm_per_cm=r_per_cm,
                delay_s=td_cm * length_cm)


# Package channel (spec/package-channel.md, scratch/cob/channel.json, WIRE_TX_P/N geometry): bond wire
# 0.832 nH/mm (25 um Au over In1), finger 0.08 pF, F.Cu 86.6 ohm microstrip (eeff 3.14), via, B.Cu
# microstrip, connector land 0.06 pF, connector contact (L per contact, 0.25 pF), then the carrier 50-ohm
# line to the AC-coupling cap (B22, 100 nF) and the far-end 50-ohm termination.  Placement points
# P1..P4 = carrier line 2 / 10 / 30 / 50 mm; bond length +-0.3 mm at P1..P4 (spec section 6).
PKG = dict(P=dict(bond_mm=2.44, f_mm=1.11, b_mm=4.05, via_nH=0.278, conn_nH=0.99),
           N=dict(bond_mm=2.42, f_mm=1.06, b_mm=2.08, via_nH=0.452, conn_nH=0.85))
PLACEMENT_MM = dict(P1=2.0, P2=10.0, P3=30.0, P4=50.0)


def _tline(lines, name, a, b, z0, eeff, length_mm, nseg=None, r_per_mm=0.0):
    td = (eeff ** 0.5) / 3e8 * length_mm * 1e-3
    nseg = nseg or max(1, int(length_mm / 2.0) + 1)
    lt, ct = z0 * td / nseg, td / z0 / nseg
    prev = a
    for i in range(nseg):
        nxt = b if i == nseg - 1 else f'{name}{i}'
        mid = f'{name}m{i}'
        lines += [f'R{name}{i} {prev} {mid} {max(r_per_mm * length_mm / nseg, 1e-3):.4g}',
                  f'L{name}{i} {mid} {nxt} {lt:.4g}', f'C{name}{i} {nxt} 0 {ct:.4g}']
        prev = nxt


def pkg_chain(lines, placement='P1', dbond_mm=0.0):
    for leg in ('P', 'N'):
        g = PKG[leg]
        lb = (g['bond_mm'] + dbond_mm) * 0.832e-9
        lines += [f'RBW{leg} PAD_{leg} BW{leg} 0.2', f'LBW{leg} BW{leg} FG{leg} {lb:.4g}', f'CFG{leg} FG{leg} 0 0.08p']
        _tline(lines, f'TF{leg}', f'FG{leg}', f'VA{leg}', 86.6, 3.14, g['f_mm'], nseg=1)
        lines += [f'LVA{leg} VA{leg} VB{leg} {g["via_nH"]}n', f'CVA{leg} VB{leg} 0 0.1p']
        _tline(lines, f'TB{leg}', f'VB{leg}', f'LD{leg}', 86.6, 3.14, g['b_mm'], nseg=2)
        lines += [f'CLD{leg} LD{leg} 0 0.06p', f'LCN{leg} LD{leg} CN{leg} {g["conn_nH"]}n', f'CCN{leg} CN{leg} 0 0.25p']
        _tline(lines, f'TC{leg}', f'CN{leg}', f'BOARD_{leg}', 50.0, 3.3, PLACEMENT_MM[placement], r_per_mm=0.01)
        lines += [f'CAC{leg} BOARD_{leg} FAR_{leg} 100n', f'RFAR_{leg} FAR_{leg} FARCM 50']
    lines.append('CFARCM FARCM 0 10p')
    return dict(topology='package (bond, COB 87 ohm, via, connector) + carrier line + 100 nF AC + 50 ohm far end',
                placement=placement, carrier_mm=PLACEMENT_MM[placement], dbond_mm=dbond_mm, geometry=PKG)


def deck(dut, subckt, *, mode, rate, words, word_t0, tstop, vdd=3.3, corner='typical', temp=27,
         codes=(109, 20, 125), lossy=False, dx_bits=None, dx_rate=None, ext_switch_t=None, rx=False, bpc=4,
         pkg=None):
    ports = S.ports_of(Path(dut).read_text(), subckt)
    tw = 20 / rate
    L = ['* pt_wiredtx + pads extracted TX output stage', tools.model_header_dir(corner, temp, tools.PAD_MODELS)]
    for sec in ('res_typical', 'diode_typical', 'mimcap_typical'):
        L.append(f'.lib {tools.PAD_MODELS}/sm141064.ngspice {sec}')
    L += [f'.include {Path(dut).name}', '.include steer.spice', '.include pad.spice',
          f'VDD VDD 0 {vdd}', 'VSS VSS 0 0']
    L += S.phase_sources(rate, vdd, stopped=(mode == 'ext'), bpc=bpc)
    ser_on = 2e-9
    if mode == 'ext':
        if ext_switch_t is None:
            L += ['VSER SER_EN 0 0', f'VEXT WTX_EXT 0 {vdd}']
        else:  # serializer running first, then handover to external data
            L += [S.pwl_bits('SER', 'SER_EN', [(0.0, 0), (ser_on, 1)], vdd),
                  S.pwl_bits('EXT', 'WTX_EXT', [(0.0, 0), (ext_switch_t, 1)], vdd)]
    else:
        L += [S.pwl_bits('SER', 'SER_EN', [(0.0, 0), (ser_on, 1)], vdd), 'VEXT WTX_EXT 0 0']
    if dx_bits is not None and rx:
        # shared receiver (timing family's extracted pt_diff_clk_rx) on WTX_EXT_P/N:
        # 500 mVpp differential, AC-coupled through 10 pF per leg
        ui = 1 / dx_rate
        t0 = 2e-9
        tv = [(0.0, 0)] + [(t0 + i * ui, b) for i, b in enumerate(dx_bits)]
        for leg, sign in (('P', 1), ('N', -1)):
            pts = ['0', f'{1.65 - sign*0.125:g}']
            lvl = 0
            for t, b in tv[1:]:
                if b != lvl:
                    pts += [f'{t:.6e}', f'{1.65 + sign*0.125*(2*lvl-1):g}', f'{t+0.1*ui:.6e}',
                            f'{1.65 + sign*0.125*(2*b-1):g}']
                    lvl = b
            # AC-coupled (10 pF) like the receiver's other uses; it self-biases to its trip point
            L.append(f'BX{leg} SRC_{leg} 0 V=pwl(time, {", ".join(pts)})')   # no breakpoints
            L.append(f'CX{leg} SRC_{leg} WTX_EXT_{leg} 10p')
        L.append('.include rx.spice')
        L.append('XRX WTX_EXT_N WTX_EXT_P WTX_EXT VSS DXB DX PRESENT ATB_DET VDD VSS pt_diff_clk_rx')
    elif dx_bits is not None:
        ui = 1 / dx_rate
        t0 = 2e-9
        tv = [(0.0, 0)] + [(t0 + i * ui, b) for i, b in enumerate(dx_bits)]
        L.append(S.pwl_bits('DX', 'DX', tv, vdd, edge=0.1 * ui))
    else:
        L.append('VDX DX 0 0')
    en = {'serial': (1, 1, 0), 'tmds': (0, 0, 1), 'ext': (1, 0, 0)}[mode]
    for nm, v in zip(('EN_MAIN', 'EN_POST', 'EN_TMDS'), en):
        L.append(f'V{nm} {nm} 0 {v*vdd}')
    L += ['VISO ISLAND_OFF 0 0', 'IREF VDD IBIAS 10u']
    for b, code in zip(('MAIN', 'POST', 'TMDS'), codes):
        for k, bit in enumerate(S.code_bits(code)):
            L.append(f'V{b}C{k} {b}_CODE{k} 0 {bit*vdd}')
    w40 = 'D39' in ports     # 40-bit boundary: word pairs launched on WORD_CLK40 rising (see sim_wiredtx)
    if w40:
        pairs = [(words[2 * m], words[2 * m + 1] if 2 * m + 1 < len(words) else words[2 * m])
                 for m in range((len(words) + 1) // 2)]
        for i in range(40):
            h, j = divmod(i, 20)
            tv = [(0.0, pairs[0][h][j])] + [(word_t0 + 2 * m * tw + tw / 4, pr[h][j]) for m, pr in enumerate(pairs)]
            L.append(S.pwl_bits(f'D{i}', f'D{i}', tv, vdd))
        L.append('CWCK40 WORD_CLK40 0 50f')
    else:
        for i in range(20):
            tv = [(0.0, words[0][i])] + [(word_t0 + k * tw + tw / 4, w[i]) for k, w in enumerate(words)]
            L.append(S.pwl_bits(f'D{i}', f'D{i}', tv, vdd))
    L.append('CWCK WORD_CLK 0 50f')
    L = S.driver_impedance(L)   # realistic DUT-input driver resistance (see sim_wiredtx)
    L.append('X0 ' + ' '.join(ports) + f' {subckt}')
    for c in BRANCH_CMDS:
        L.append(f'XSB_{c} VDD VSS {c} {c[4:]} tx_steering_buffer_flat_physical')
    # pad control/bias stand-ins, each through a small series resistance
    L += [f'VCAS CAS_SRC 0 {vdd}', 'RCAS CAS_SRC CASCODE 50', 'VDETEN DETEN_SRC 0 0', 'RDETEN DETEN_SRC DETECT_ENABLE 100',
          f'VDETPB DETPB_SRC 0 {vdd}', 'RDETPB DETPB_SRC DETECT_PBIAS 100']
    if mode in ('serial', 'ext'):   # ext data drives the MAIN branch with the serial termination
        L += [f'VTERMEN TERM_EN_SRC 0 {vdd}', 'RTERMEN TERM_EN_SRC TERM_ENABLE 100', 'VTVCM TVCM_SRC 0 1.65', 'RTVCM TVCM_SRC TERM_VCM 2']
    else:
        L += ['VTERMEN TERM_EN_SRC 0 0', 'RTERMEN TERM_EN_SRC TERM_ENABLE 100', 'RTVCM TERM_VCM 0 1meg']
    L.append('XPAD PAD_P PAD_N VDD VSS CASCODE MAIN_P MAIN_N MAIN_BIAS POST_P POST_N POST_BIAS TMDS_P TMDS_N '
             'TMDS_BIAS DETECT_ENABLE DETECT_PBIAS TERM_ENABLE TERM_VCM tx_protected_pad')
    if not pkg:
        for leg in ('P', 'N'):
            L += [f'RB{leg} BOARD_{leg} BOND_{leg} 1', f'LB{leg} BOND_{leg} PAD_{leg} 1n']
    net = {}
    if pkg and mode == 'serial':
        net = pkg_chain(L, *pkg)
        out = ('FAR_P', 'FAR_N')
    elif mode == 'tmds':
        L.append(f'VPEER PEER 0 {vdd}')
        L += ['RPU_P PEER BOARD_P 50', 'RPU_N PEER BOARD_N 50']
        net = dict(topology='split_pullup_50ohm_to_independent_3v3')
        out = ('BOARD_P', 'BOARD_N')
    else:
        if lossy:
            net = channel(L)
            L += ['RFAR_P FAR_P FARCM 50', 'RFAR_N FAR_N FARCM 50', 'CFARCM FARCM 0 10p']
            out = ('FAR_P', 'FAR_N')
        else:
            L.append('RDIFF BOARD_P BOARD_N 100')
            net = dict(topology='100ohm_differential')
            out = ('BOARD_P', 'BOARD_N')
    probes = [f'v({out[0]},{out[1]})', f'v({out[0]})', f'v({out[1]})', 'v(WORD_CLK40)' if w40 else 'v(WORD_CLK)', 'v(CMD_MAIN_N)',
              'v(CMD_TMDS_N)', 'v(PAD_P)', 'v(PAD_N)', 'v(x0.SER)', 'v(x0.EXT)', 'i(VDD)', 'v(MAIN_BIAS)', 'v(TMDS_BIAS)']
    names = ['DIFF', 'OUTP', 'OUTN', 'WORD_CLK', 'CMD_MAIN_N', 'CMD_TMDS_N', 'PAD_P', 'PAD_N', 'SER', 'EXT',
             'I_VDD', 'MAIN_BIAS', 'TMDS_BIAS']
    L += ['.options reltol=1e-3 method=gear rshunt=1e10 interp', f'.tran 20p {tstop:.6e} 0 4p', '.control',
          'save ' + ' '.join(probes), 'set wr_singlescale', 'run', 'wrdata wave.txt ' + ' '.join(probes), '.endc', '.end']
    return '\n'.join(L) + '\n', names, net


def eye(w, rate, t0, t1, expected=None, node='DIFF'):
    """Eye at the best sampling phase: vertical opening and crossing spread."""
    ui = 1.0 / rate
    t, v = w['time'], w[node]
    xs = S.crossings(t, v, th=0.0)
    xs = xs[(xs > t0) & (xs < t1)]
    if len(xs) < 4:
        return dict(ok=False, reason='no transitions')
    ph = np.mod(xs, ui)
    ang = np.angle(np.mean(np.exp(2j * np.pi * ph / ui)))
    cp = (ang / (2 * np.pi) * ui) % ui
    dev = np.mod(ph - cp + ui / 2, ui) - ui / 2
    best = None
    for frac in np.linspace(0.3, 0.7, 9):
        ts = np.arange(t0 - (t0 % ui) + cp + frac * ui, t1, ui)
        vs = np.interp(ts, t, v)
        hi, lo = vs[vs > 0], vs[vs <= 0]
        if len(hi) and len(lo):
            h = float(hi.min() - lo.max())
            if best is None or h > best[0]:
                best = (h, frac, (vs > 0).astype(int), vs)
    h, frac, bits, vs = best
    r = dict(eye_height_v=h, sample_phase_ui=float(frac), crossing_spread_pp_s=float(dev.max() - dev.min()),
             eye_width_est_s=float(ui - (dev.max() - dev.min())), amplitude_pp_v=float(vs.max() - vs.min()),
             n_bits=int(len(bits)))
    if expected is not None:
        lat, err = S.align(bits, expected)
        r.update(errors=int(err), latency_bits=int(lat))
    return r


def run(work, dut, subckt='pt_wiredtx', *, mode='serial', rate=2.5e9, nwords=8, corner='typical', temp=27,
        vdd=3.3, lossy=False, codes=(109, 20, 125), tag=None, bpc=4, pkg=None):
    work = Path(work); tag = tag or f'{mode}_{rate/1e9:g}G'
    tw = 20 / rate
    def prep(d):
        d.mkdir(parents=True, exist_ok=True)
        (d / Path(dut).name).write_text(Path(dut).read_text())
        (d / 'steer.spice').write_text(clean_lib(STEER.read_text()))
        (d / 'pad.spice').write_text(clean_lib(PAD.read_text()))
    pdir = work / f'{tag}_phase'; prep(pdir)
    txt, names, _ = deck(pdir / Path(dut).name, subckt, mode=mode, rate=rate, words=[[0] * 20], word_t0=1,
                         tstop=2e-9 + 8 * tw, vdd=vdd, corner=corner, temp=temp, codes=codes, lossy=lossy, bpc=bpc,
                         pkg=pkg)
    (pdir / 'tb.sp').write_text(txt)
    _, _log = tools.ngspice_host(pdir, 'tb.sp')
    if S.sim_abort(_log):
        return dict(ok=False, reason='simulator abort: ' + S.sim_abort(_log))
    w = tools.read_wrdata(pdir / 'wave.txt', names)
    rises = S.crossings(w['time'], w['WORD_CLK'], rising=True)
    rises = rises[rises > 2e-9]
    if 'D39' in S.ports_of(Path(dut).read_text(), subckt) and len(rises) > 2:
        rises = rises[1:]       # WORD_CLK40: skip the start-up period
    if len(rises) < 1:
        return dict(ok=False, reason='WORD_CLK not running')
    word_t0 = float(rises[0])
    bits = S.prbs7_bits(20 * nwords)
    words = [bits[20 * k:20 * k + 20] for k in range(nwords)]
    ddir = work / f'{tag}_data'; prep(ddir)
    txt, names, net = deck(ddir / Path(dut).name, subckt, mode=mode, rate=rate, words=words, word_t0=word_t0,
                           tstop=word_t0 + (nwords + 3) * tw, vdd=vdd, corner=corner, temp=temp, codes=codes,
                           lossy=lossy, bpc=bpc, pkg=pkg)
    (ddir / 'tb.sp').write_text(txt)
    _, _log = tools.ngspice_host(ddir, 'tb.sp')
    if S.sim_abort(_log):
        return dict(ok=False, reason='simulator abort: ' + S.sim_abort(_log))
    w = tools.read_wrdata(ddir / 'wave.txt', names)
    t0, t1 = word_t0 + 2 * tw, word_t0 + (nwords - 1) * tw
    r = dict(mode=mode, bit_rate_bps=rate, bits_per_ring_cycle=bpc, corner=corner, temp_c=temp, vdd=vdd,
             codes=dict(zip(('main', 'post', 'tmds'), codes)), network=net, lossy_channel=lossy)
    r['eye'] = eye(w, rate, t0, t1, bits)
    sel = w['time'] > t0
    r['pad_levels_v'] = dict(p_min=float(w['PAD_P'][sel].min()), p_max=float(w['PAD_P'][sel].max()),
                             n_min=float(w['PAD_N'][sel].min()), n_max=float(w['PAD_N'][sel].max()))
    r['vdd_current_avg_a'] = float(-np.mean(w['I_VDD'][sel]))
    r['bias_v'] = dict(main=float(np.mean(w['MAIN_BIAS'][sel])), tmds=float(np.mean(w['TMDS_BIAS'][sel])))
    r['ok'] = bool(r['eye'].get('errors', 1) == 0)
    return r


RX = tools.PROJECT / 'analog/timing/generated/diff_clk_rx.ext.spice'


def run_ext(work, dut, subckt='pt_wiredtx', *, rate=1e9, nbits=48, handover=False, corner='typical', temp=27,
            vdd=3.3, tag=None, rx=False):
    """External-data fallback: DX pattern reaches the pad; optional BBM handover."""
    work = Path(work); tag = tag or ('ext_handover' if handover else f'ext_{rate/1e9:g}G' + ('_rx' if rx else ''))
    d = work / tag
    d.mkdir(parents=True, exist_ok=True)
    if rx:
        (d / 'rx.spice').write_text(clean_lib(RX.read_text()))
    (d / Path(dut).name).write_text(Path(dut).read_text())
    (d / 'steer.spice').write_text(clean_lib(STEER.read_text()))
    (d / 'pad.spice').write_text(clean_lib(PAD.read_text()))
    payload = S.prbs7_bits(nbits)
    pre = 128 if rx else 0     # B12: >= 128 balanced bits before payload (AC-coupled source)
    bits = [1 - (i % 2) for i in range(pre)] + payload
    sw = 6e-9 if handover else None
    tstop = 2e-9 + (len(bits) + 2) / rate + (8e-9 if handover else 0)
    if handover:
        bits_t0 = 2e-9
    txt, names, _ = deck(d / Path(dut).name, subckt, mode='ext', rate=2.5e9, words=[[0] * 20], word_t0=1,
                         tstop=tstop, vdd=vdd, corner=corner, temp=temp, dx_bits=bits, dx_rate=rate,
                         ext_switch_t=sw, rx=rx)
    (d / 'tb.sp').write_text(txt)
    _, _log = tools.ngspice_host(d, 'tb.sp')
    if S.sim_abort(_log):
        return dict(ok=False, reason='simulator abort: ' + S.sim_abort(_log))
    w = tools.read_wrdata(d / 'wave.txt', names)
    r = dict(mode='ext', rate_bps=rate, corner=corner, temp_c=temp, vdd=vdd, handover=handover,
             receiver=('timing extracted pt_diff_clk_rx (DX from OUTN, legs swapped), 500 mVpp diff, AC-coupled 10 pF/leg, 128-bit 1010 preamble' if rx else 'ideal DX source'))
    if handover:
        t = w['time']
        ser_fall = S.crossings(t, w['SER'], rising=False)
        ext_rise = S.crossings(t, w['EXT'], rising=True)
        r['ser_fall_s'] = float(ser_fall[0]) if len(ser_fall) else None
        r['ext_rise_s'] = float(ext_rise[0]) if len(ext_rise) else None
        r['break_before_make_gap_s'] = (r['ext_rise_s'] - r['ser_fall_s']) if len(ser_fall) and len(ext_rise) else None
        both = (w['SER'] > 1.65) & (w['EXT'] > 1.65)
        r['overlap_samples'] = int(both.sum())
        r['ok'] = bool(r['break_before_make_gap_s'] and r['break_before_make_gap_s'] > 0 and not both.any())
        return r
    ui = 1 / rate
    t0 = 2e-9 + (pre + 4) * ui
    t1 = 2e-9 + (pre + nbits - 2) * ui
    r['eye'] = eye(w, rate, t0, t1, payload)
    r['preamble_bits'] = pre
    r['ok'] = bool(r['eye'].get('errors', 1) == 0)
    return r


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--dut', default=str(tools.SCRATCH / 'layout/pt_wiredtx_pex.spice'))
    ap.add_argument('--mode', default='serial', choices=['serial', 'tmds', 'ext', 'handover'])
    ap.add_argument('--rate', type=float, default=2.5e9)
    ap.add_argument('--ext-rate', type=float, default=1e9)
    ap.add_argument('--lossy', action='store_true')
    ap.add_argument('--rx', action='store_true')
    ap.add_argument('--bpc', type=int, default=4)
    ap.add_argument('--corner', default='typical')
    ap.add_argument('--work', default=str(tools.SCRATCH / 'integration'))
    a = ap.parse_args()
    if a.mode in ('ext', 'handover'):
        r = run_ext(a.work, a.dut, rate=a.ext_rate, handover=a.mode == 'handover', corner=a.corner, rx=a.rx)
    else:
        r = run(a.work, a.dut, mode=a.mode, rate=a.rate, lossy=a.lossy, corner=a.corner, bpc=a.bpc)
    print(json.dumps(r, indent=2))
