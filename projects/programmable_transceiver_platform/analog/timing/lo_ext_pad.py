#!/usr/bin/env python3
"""External-LO fallback through the real protected pads.

The lo_ext block evidence (run_timing.py tb_lo_ext) drives the LO pins from a
50 ohm source through 100 pF and an ideal 1 pF "pad". This bench replaces the
ideal pad with the drawn stress-safe pair actually bonded at REF_IN_P/N (I) and
AUX_CLK_P/N (Q): analog/pads/generated/stress-safe-families/rf-pair/
pad-extracted.spice (rf_protected_pad, same physical protection as refpad).
Each pad pair also carries its disabled diff_clk_rx receiver (refinput on
REF_IN, aux_clk_rx on AUX_CLK; extracted), as on the die.

DUT: extracted pt_lo_ext (generated/lo_ext.ext.spice) in external mode, mixer
LO nodes loaded with the RX (12x5u) and TX (4x10u) switch gates + 22 fF, as in
tb_lo_ext. Simulator: the pad family's corrected ngspice 47 image (the pad
diode-charge fix matters here), PDK models of that flow.

Per case it records the pad waveform (peak, trough, Vpp), the power the board
source delivers, and the lo_ext criteria of tb_lo_ext (f within 1 %, RX
switch Vgs on >= 0.9 V, off <= 0.5 V, |Q-I| within 80..100 deg).

    python3 lo_ext_pad.py sweep     # amplitude sweep at tt/27, ff/32/3.35, ss/32/3.15
    python3 lo_ext_pad.py corners --vpp X   # 13 envelope points at one source level
    python3 lo_ext_pad.py report    # generated/lo_ext-pad-evidence.json
"""
import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANALOG = HERE.parent
REPO = HERE.parents[3]
SCRATCH = REPO / 'scratch'
WORK = SCRATCH / 'timing' / 'lo_ext_pad'
GEN = HERE / 'generated'
PAD = ANALOG / 'pads/generated/stress-safe-families/rf-pair/pad-extracted.spice'
# REF_IN is bonded to refpad (tx_protected_pad: same stress-safe clamp plus the
# receiver's VCM bias resistors to bias.vcm = VDD/2), not to the rf pair.
REFPAD = ANALOG / 'pads/generated/stress-safe-families/reference/physical.spice'
LOEXT = GEN / 'lo_ext.ext.spice'
RX = GEN / 'diff_clk_rx.ext.spice'
SIM_IMAGE = 'svalbard/transceiver-pad-sim:ngspice47-corrected'
NGSPICE = '/opt/pad-ngspice47/bin/ngspice'
PDK = SCRATCH / 'transceiver-pad-pdk/ngspice'
F = 2.45e9
T = 12e-9
ENVELOPE = [('typical', 27, 3.3)] + [(c, t, v) for c in ('typical', 'ss', 'ff') for t in (22, 32) for v in (3.15, 3.35)]
SWEEP_CORNERS = [('typical', 27, 3.3), ('ff', 32, 3.35), ('ss', 32, 3.15)]
SWEEP_VPP = [2.0, 3.0, 4.0, 5.0]   # open-circuit per leg behind 50 ohm


def sha(p):
    return 'sha256:' + hashlib.sha256(Path(p).read_bytes()).hexdigest()


def anchor(text, r=1e12):
    """Same numerical anchoring as analog/pads/loading_audit.py: capacitor-only
    extracted conductors get a 1 Tohm path to VSS."""
    text = re.sub(r'\n\+\s*', ' ', text)
    out, caps, conn, cell = [], set(), set(), None
    for line in text.splitlines():
        f = line.split()
        if f and f[0] == '.subckt':
            cell, caps, conn = f[1], set(), set(f[2:])
        elif f and f[0].startswith('C') and cell:
            caps.update(f[1:3])
        elif f and f[0] == '.ends':
            for i, node in enumerate(sorted(caps - conn - {'0', 'VSS'})):
                out.append(f'RNUM_FLOAT_{cell}_{i} {node} VSS {r:g}')
            cell = None
        elif cell and f and not f[0].startswith(('*', '.')):
            conn.update(f[1:])
        if not line.startswith('.lib '):
            out.append(line)
    return '\n'.join(out) + '\n'


def header(corner, temp):
    lib = {'typical': ('typical', 'res_typical', 'diode_typical', 'mimcap_typical'),
           'ss': ('ss', 'res_ss', 'diode_ss', 'mimcap_ss'),
           'ff': ('ff', 'res_ff', 'diode_ff', 'mimcap_ff')}[corner]
    return (f'* lo_ext through rf_protected_pad, {corner} {temp} C\n.include {PDK}/design.ngspice\n'
            + ''.join(f'.lib {PDK}/sm141064.ngspice {x}\n' for x in lib)
            + f'.temp {temp}\n.option method=gear reltol=1e-3\n')



# D-LO-3 (package analysis 2026-11-10, spec/package-channel.md, scratch/cob/placement.py
# chain_to): per-leg COB chain, source side -> die.  Carrier: 10 pF C0G (B19) at the
# placement point, then `place_mm` of 50 ohm line (eeff 3.3) to the mezzanine
# connector (0.25 pF, conn_nH, 0.06 pF), COB B.Cu 86.6 ohm line b_mm (eeff 3.14),
# 0.10 pF, via (via_nH), F.Cu line f_mm, 0.08 pF bond land, bond wire bond_mm x
# 0.83 nH/mm with R = 0.05*bond_mm*sqrt(f/GHz) + 0.05 ohm.  Lossless lines (LC ladders).
CHAIN = None   # (place_mm, dbond_mm) when --cob
COB_LEGS = dict(ip='REF_IN', **{'in': 'REF_IN_N'}, qp='AUX_CLK_P', qn='AUX_CLK_N')


def _line(name, a, b, z0, mm, eeff, sections=None):
    """Lossless line as an LC ladder (pi sections; >= 8 sections per wavelength
    at 3x 2.45 GHz).  The ideal ngspice T element stopped the transient here."""
    td = mm * 1e-3 * math.sqrt(eeff) / 299792458.0
    if td <= 0:
        return f'R{name} {a} {b} 1e-3\n'
    nsec = sections or max(2, math.ceil(td * 3 * 2.45e9 * 8))
    L, C = z0 * td / nsec, td / z0 / nsec
    out, prev = '', a
    for k in range(nsec):
        nxt = b if k == nsec - 1 else f'{name}_{k}'
        out += f'C{name}a{k} {prev} 0 {C / 2:.4e}\nL{name}{k} {prev} {nxt} {L:.4e}\nC{name}b{k} {nxt} 0 {C / 2:.4e}\n'
        prev = nxt
    return out


def cob_leg(n, place_mm, dbond=0.0):
    g = json.loads((SCRATCH / 'cob' / 'channel.json').read_text())['geometry'][COB_LEGS[n]]
    bmm = g['bond_mm'] + dbond
    lb = bmm * 0.83
    rb = 0.05 * bmm * math.sqrt(F / 1e9) + 0.05
    return (f'CB{n} b{n} c0{n} 10p\n' + _line(f'T0{n}', f'c0{n}', f'c1{n}', 50.0, place_mm, 3.3) +
            f'CK1{n} c1{n} 0 0.25p\nLK{n} c1{n} c2{n} {g["conn_nH"]}n\nCK2{n} c2{n} 0 0.06p\n' +
            _line(f'TB{n}', f'c2{n}', f'c3{n}', 86.6, g['b_mm'], 3.14) + f'CV{n} c3{n} 0 0.10p\n'
            f'LV{n} c3{n} c4{n} {g["via_nH"]}n\n' + _line(f'TF{n}', f'c4{n}', f'c5{n}', 86.6, g['f_mm'], 3.14) +
            f'CL{n} c5{n} 0 0.08p\nLBW{n} c5{n} c6{n} {lb:.4f}n\nRBW{n} c6{n} pad{n} {rb:.4f}\n')

def deck(corner, temp, vdd, vpp, pad=True, lbond=1.5, T=T, windows=None):
    a = vpp / 2
    q = 0.25 / F
    d = header(corner, temp) + '.include lo_ext.ext.spice\n.include diff_clk_rx.ext.spice\n'
    if pad:
        d += '.include pad.spice\n.include refpad.spice\n'
    # RX mixer switch drain/source DC = the mixer's VCM = VDD/2 (rf_rx/rxmix_i.spice
    # pt_rfrx_vcm: equal resistor divider; the OTA holds x_p/x_n at VCM).  The first
    # benches used a fixed 1.65 V, which is pessimistic at 3.15 V and optimistic at 3.35 V.
    d += f'VDD vdd 0 {vdd}\nVEXT ext 0 {vdd}\nVINT int 0 0\nVCSL cmlsel 0 0\nVRXD rxd 0 {vdd / 2}\nVRXS rxs 0 {vdd / 2}\nVTXD txd 0 2.5\nVTXS txs 0 1.0\n'
    for n, ph, sg in (('ip', 0, 1), ('in', 0, -1), ('qp', q, 1), ('qn', q, -1)):
        # board: 50 ohm source, 10 pF C0G AC coupling (B19); package (B21): bond wire
        # 1 nH/mm, lbond nH per leg, 0.2 ohm (gold, skin at 2.45 GHz); pad-to-pad 0.1 pF below
        if CHAIN is None:
            d += (f'VS{n} s{n} 0 sin(0 {sg * a} {F} {ph})\nRS{n} s{n} b{n} 50\nCB{n} b{n} w{n} 10p\n'
                  f'LBW{n} w{n} wr{n} {lbond}n\nRBW{n} wr{n} pad{n} 0.2\nVLI{n} loi{n} 0 0\n')
        else:
            d += f'VS{n} s{n} 0 sin(0 {sg * a} {F} {ph})\nRS{n} s{n} b{n} 50\nVLI{n} loi{n} 0 0\n' + cob_leg(n, CHAIN[0], CHAIN[1])
        if not pad:
            d += f'CP{n} pad{n} 0 1p\n'
        d += (f'XRX{n} rxd lo{n} rxs 0 nfet_03v3 w=5u l=0.28u m=12\n'
              f'XTX{n} txd lo{n} txs 0 nfet_03v3 w=10u l=0.28u m=4\nCW{n} lo{n} 0 22f\n')
    d += 'CMIP padip padin 0.1p\nCMQP padqp padqn 0.1p\n'
    if pad:
        # REF_IN (refpad, VCM = bias.vcm = VDD/2 as in the pads family benches) carries I;
        # AUX_CLK (rf_protected_pad debug pair) carries Q; ATB_ESD_RAIL to the ATB pad (10 Mohm meter)
        d += 'XPADI padip padin 0 vcm atbi tx_protected_pad\nRATBI atbi 0 10meg\nEVCM vcm 0 vdd 0 0.5\n'
        d += 'XPADQ padqn padqp 0 atbq rf_protected_pad\nRATBQ atbq 0 10meg\n'
    # disabled receivers on both pairs (EN=0, SE=0)
    d += 'XRXI padip padin 0 0 rio rion rip riatb vdd 0 pt_diff_clk_rx\n'
    d += 'XRXQ padqp padqn 0 0 rqo rqon rqp rqatb vdd 0 pt_diff_clk_rx\n'
    d += 'X1 padip padin padqp padqn loiip loiin loiqp loiqn ext int cmlsel loip loin loqp loqn vb vdd 0 pt_lo_ext\n'
    td = T - 4e-9
    # differential LO legs for the phase/period measures (zero crossings do not
    # depend on where the bias settles; the fixed 2.45 V threshold missed at ss)
    d += 'EDI di 0 loip loin 1\nEDQ dq 0 loqp loqn 1\n'
    for k, (a_, b_) in enumerate(windows or []):
        d += (f'.measure tran w{k}_lomax max v(loip) from={a_} to={b_}\n.measure tran w{k}_lomin min v(loip) from={a_} to={b_}\n'
              f'.measure tran w{k}_qmax max v(loqp) from={a_} to={b_}\n.measure tran w{k}_qmin min v(loqp) from={a_} to={b_}\n'
              f'.measure tran w{k}_vb avg v(vb) from={a_} to={b_}\n.measure tran w{k}_loavg avg v(loip) from={a_} to={b_}\n'
              f'.measure tran w{k}_padavg avg v(padip) from={a_} to={b_}\n')
    d += f'.tran 1p {T}\n'
    for n in ('ip', 'qp', 'in'):
        d += (f'.measure tran pmax_{n} max v(pad{n}) from={td} to={T}\n.measure tran pmin_{n} min v(pad{n}) from={td} to={T}\n')
    d += (f'.measure tran lomax max v(loip) from={td} to={T}\n.measure tran lomin min v(loip) from={td} to={T}\n'
          f'.measure tran qmax max v(loqp) from={td} to={T}\n.measure tran qmin min v(loqp) from={td} to={T}\n'
          f'.measure tran vbavg avg v(vb) from={td} to={T}\n.measure tran vb0 find v(vb) at=0\n'
          f'.measure tran loavg avg v(loip) from={td} to={T}\n.measure tran qavg avg v(loqp) from={td} to={T}\n'
          f'.measure tran lonmax max v(loin) from={td} to={T}\n.measure tran lonmin min v(loin) from={td} to={T}\n'
          f'.measure tran psrcq avg par(\'-v(sqp)*i(VSqp)\') from={td} to={T}\n'
          f'.measure tran tiq trig v(di) val=0 td={td} rise=1 targ v(dq) val=0 td={td} rise=1\n'
          f'.measure tran tqi trig v(dq) val=0 td={td} rise=1 targ v(di) val=0 td={td} rise=1\n'
          f'.measure tran per trig v(di) val=0 td={td} rise=1 targ v(di) val=0 td={td} rise=5\n'
          f'.measure tran psrc avg par(\'-v(sip)*i(VSip)\') from={td} to={T}\n'
          f'.measure tran ivdd avg i(VDD) from={td} to={T}\n'
          '.end\n')
    return d


def run(name, text):
    WORK.mkdir(parents=True, exist_ok=True)
    import run_timing   # CML LO driver gate resistance wrapper (ct_locml)
    import timing_flow as tf_
    # block-unique subckt names (generic PCell names collide between extracted blocks)
    lo = tf_.uniquify_subckts(LOEXT.read_text(), 'lo_ext', keep=('pt_lo_ext', 'ct_locml'))
    (WORK / 'lo_ext.ext.spice').write_text(run_timing.rg_wrap_locml(lo))
    (WORK / 'diff_clk_rx.ext.spice').write_text(tf_.uniquify_subckts(RX.read_text(), 'diff_clk_rx', keep=('pt_diff_clk_rx',)))
    (WORK / 'pad.spice').write_text(anchor(PAD.read_text()))
    (WORK / 'refpad.spice').write_text(anchor(REFPAD.read_text()))
    (WORK / '.spiceinit').write_text('set ngbehavior=hs\n')
    dup = {k: v for k, v in tf_.check_duplicate_subckts([WORK / f for f in ('lo_ext.ext.spice', 'diff_clk_rx.ext.spice', 'pad.spice', 'refpad.spice')]).items()}
    if any(not v['equivalent'] for v in dup.values()):
        raise RuntimeError(f'non-equivalent duplicate subckts in the bench: {sorted(k for k, v in dup.items() if not v["equivalent"])}')
    (WORK / f'{name}.spice').write_text(text)
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '6g', '-e', 'OMP_NUM_THREADS=1',
           '--user', '1000:1000', '--entrypoint', NGSPICE, '--mount', f'type=bind,src={SCRATCH},dst={SCRATCH}',
           '-w', str(WORK), SIM_IMAGE, '-b', str(WORK / f'{name}.spice')]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    log = r.stdout + r.stderr
    (WORK / f'{name}.log').write_text(log)
    m = {}
    for line in log.splitlines():
        g = re.match(r'^\s*([a-z_][a-z0-9_]*)\s*=\s*([-+0-9.eE]+)', line)
        if g:
            m[g.group(1)] = float(g.group(2))
    m['_errors'] = [l.strip() for l in log.splitlines() if l.strip().lower().startswith('error') or 'failed' in l.lower()][:8]
    m['_rc'] = r.returncode
    return m


def analyse(m, corner, temp, vdd, vpp, pad):
    fo = 4 / m['per'] if m.get('per') else None
    d = None
    for k, sg in (('tiq', 1), ('tqi', -1)):
        if m.get(k, 0) > 0 and (d is None or m[k] < abs(d)):
            d = sg * m[k]
    ph = ((d * F * 360 + 180) % 360 - 180) if d is not None else None
    r = dict(corner=corner, temp_c=temp, vdd_v=vdd, source_vpp_open_circuit=vpp, pad_model='I: refpad tx_protected_pad (VCM=VDD/2); Q: rf_protected_pad' if pad else 'ideal 1 pF',
             pad_i_max_v=m.get('pmax_ip'), pad_i_min_v=m.get('pmin_ip'),
             pad_vpp_i=(m['pmax_ip'] - m['pmin_ip']) if 'pmax_ip' in m and 'pmin_ip' in m else None,
             pad_vpp_q=(m['pmax_qp'] - m['pmin_qp']) if 'pmax_qp' in m and 'pmin_qp' in m else None,
             source_total_power_per_leg_dbm=(10 * math.log10(m['psrc'] / 1e-3) if m.get('psrc', 0) > 0 else None),
             available_power_per_leg_dbm=10 * math.log10((vpp / 2) ** 2 / (8 * 50) / 1e-3),
             f_lo_hz=fo, lo_i_max_v=m.get('lomax'), lo_i_min_v=m.get('lomin'), vb_v=m.get('vbavg'),
             rx_switch_source_v=vdd / 2,
             rx_switch_vgs_on_v=(m['lomax'] - vdd / 2) if 'lomax' in m else None,
             rx_switch_vgs_off_v=(m['lomin'] - vdd / 2) if 'lomin' in m else None,
             lo_q_max_v=m.get('qmax'), lo_q_min_v=m.get('qmin'),
             lo_i_vpp=(m['lomax'] - m['lomin']) if 'lomax' in m and 'lomin' in m else None,
             lo_q_vpp=(m['qmax'] - m['qmin']) if 'qmax' in m and 'qmin' in m else None,
             source_total_power_q_leg_dbm=(10 * math.log10(m['psrcq'] / 1e-3) if m.get('psrcq', 0) > 0 else None),
             q_minus_i_deg=ph, i_vdd_ma=-m.get('ivdd', math.nan) * 1e3, sim_messages=m['_errors'])
    if m.get('qmax') is not None and m.get('qmin') is not None:
        r['rx_switch_vgs_on_q_v'] = m['qmax'] - vdd / 2
        r['rx_switch_vgs_off_q_v'] = m['qmin'] - vdd / 2
    # Steady state.  The measured window (8-12 ns) sits inside the 20-200 ns bias
    # time constants (settle step: VB/LO DC still recovering at 200 ns).  The LO
    # node's only DC path is its 20 k to VB, so in steady state avg(LO) = VB(t=0);
    # the projection keeps the measured waveform (max-avg, avg-min) about it.
    # Checked against the 200 ns run (scratch results 'settle').  I and Q both.
    need = ('lomax', 'lomin', 'loavg', 'qmax', 'qmin', 'qavg', 'vb0')
    if all(k in m for k in need):
        r['steady_state_projection'] = dict(
            vb_dc_v=m['vb0'],
            on_i_v=m['lomax'] - m['loavg'] + m['vb0'] - vdd / 2, off_i_v=m['vb0'] - (m['loavg'] - m['lomin']) - vdd / 2,
            on_q_v=m['qmax'] - m['qavg'] + m['vb0'] - vdd / 2, off_q_v=m['vb0'] - (m['qavg'] - m['qmin']) - vdd / 2)
        p_ = r['steady_state_projection']
        levels = min(p_['on_i_v'], p_['on_q_v']) >= 0.9 and max(p_['off_i_v'], p_['off_q_v']) <= 0.5
    else:
        levels = False
    r['pass'] = bool(fo and abs(fo / F - 1) < 0.01 and levels and ph is not None and 80 < abs(ph) < 100)
    return r


TAG = ''   # --tag: result-key/deck-name suffix for candidate pad models


def job(corner, temp, vdd, vpp, pad=True, lbond=1.5):
    name = f'{"pkg" if pad else "ideal"}_{corner}_{temp}_{vdd}_{vpp:g}vpp_l{lbond:g}{TAG}'
    m = run(name, deck(corner, temp, vdd, vpp, pad, lbond))
    r = analyse(m, corner, temp, vdd, vpp, pad)
    r['bond_wire_nh'] = lbond
    r['package_model'] = (f'board 50 ohm + 10 pF; bond wire {lbond:g} nH + 0.2 ohm per leg; 0.1 pF pad-to-pad' if CHAIN is None else
                          f'COB chain (scratch/cob/channel.json geometry): source + 10 pF at {CHAIN[0]:g} mm of carrier line, connector, COB traces, via, bonds {CHAIN[1]:+g} mm; 0.1 pF pad-to-pad')
    r['deck'] = str((WORK / f'{name}.spice').relative_to(REPO))
    print(json.dumps({k: r[k] for k in ('corner', 'temp_c', 'vdd_v', 'source_vpp_open_circuit', 'pad_vpp_i', 'pad_i_max_v',
                                        'rx_switch_vgs_on_v', 'rx_switch_vgs_off_v', 'lo_i_vpp', 'lo_q_vpp', 'q_minus_i_deg', 'steady_state_projection', 'pass')}), flush=True)
    return r


def save(key, rows):
    p = WORK / 'results.json'
    d = json.loads(p.read_text()) if p.exists() else {}
    key = key + TAG
    for r in rows:
        r['pad_models'] = dict(refpad=str(REFPAD.relative_to(REPO)), rf_pair=str(PAD.relative_to(REPO)), lo_ext=sha(LOEXT))
    d[key] = rows
    p.write_text(json.dumps(d, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('step', choices=['sweep', 'corners', 'report', 'settle', 'sweep_l'])
    ap.add_argument('--corner', default='ss,32,3.15')
    ap.add_argument('--tstop', type=float, default=200e-9)
    ap.add_argument('--vpp', type=float, default=4.0)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--lbond', type=float, default=1.5)
    ap.add_argument('--refpad', default='', help='candidate refpad model (tx_protected_pad), e.g. scratch/pad-compact-v2/reference_clock/pad/physical.spice')
    ap.add_argument('--rfpad', default='', help='candidate rf pair model (rf_protected_pad)')
    ap.add_argument('--tag', default='', help='suffix for deck names and result keys')
    a = ap.parse_args()
    global PAD, REFPAD, TAG, WORK
    if a.refpad:
        REFPAD = (REPO / a.refpad).resolve()
    if a.rfpad:
        PAD = (REPO / a.rfpad).resolve()
    TAG = a.tag
    if a.step == 'sweep':
        jobs = [(c, t, v, x, True, a.lbond) for c, t, v in SWEEP_CORNERS for x in SWEEP_VPP]
        # ideal-pad reference rows kept from the earlier run (key 'sweep')
        with ThreadPoolExecutor(a.jobs) as ex:
            save(f'sweep_pkg_l{a.lbond:g}', list(ex.map(lambda j: job(*j), jobs)))
    elif a.step == 'sweep_l':
        # bond-wire tolerance (B21: 1.5 +- 0.5 nH) at the low edge of the window, ss/32/3.15
        jobs = [('ss', 32, 3.15, a.vpp, True, lb) for lb in (1.0, 2.0)]
        with ThreadPoolExecutor(a.jobs) as ex:
            save(f'bondwire_ss32_{a.vpp:g}vpp', list(ex.map(lambda j: job(*j), jobs)))
    elif a.step == 'settle':
        # settling of the bias nodes (VB, LO DC, pad DC): the 12 ns benches measure
        # 8-12 ns, inside the 20 k x ~1 pF (LO) and 10 k x 2.6 pF (PS) time constants
        c, t, v = a.corner.split(',')
        t, v = int(t), float(v)
        wins = [(8e-9, 12e-9), (36e-9, 40e-9), (76e-9, 80e-9), (116e-9, 120e-9), (a.tstop - 4e-9, a.tstop)]
        name = f'settle_{c}_{t}_{v}_{a.vpp:g}vpp_l{a.lbond:g}_{a.tstop * 1e9:.0f}ns'
        m = run(name, deck(c, t, v, a.vpp, True, a.lbond, T=a.tstop, windows=wins))
        r = analyse(m, c, t, v, a.vpp, True)
        r['windows'] = [dict(t_ns=[w[0] * 1e9, w[1] * 1e9], vb=m.get(f'w{k}_vb'), lo_avg=m.get(f'w{k}_loavg'), pad_avg=m.get(f'w{k}_padavg'),
                             on=(m[f'w{k}_lomax'] - v / 2) if f'w{k}_lomax' in m else None,
                             off=(m[f'w{k}_lomin'] - v / 2) if f'w{k}_lomin' in m else None,
                             on_q=(m[f'w{k}_qmax'] - v / 2) if f'w{k}_qmax' in m else None,
                             off_q=(m[f'w{k}_qmin'] - v / 2) if f'w{k}_qmin' in m else None) for k, w in enumerate(wins)]
        r['bond_wire_nh'] = a.lbond
        p = WORK / 'results.json'
        d = json.loads(p.read_text()) if p.exists() else {}
        d.setdefault('settle', {})[name] = r
        p.write_text(json.dumps(d, indent=1))
        print(json.dumps(r['windows'], indent=0))
    elif a.step == 'corners':
        with ThreadPoolExecutor(a.jobs) as ex:
            save(f'corners_pkg_l{a.lbond:g}_{a.vpp:g}vpp', list(ex.map(lambda j: job(*j), [(c, t, v, a.vpp, True, a.lbond) for c, t, v in ENVELOPE])))
    else:
        d = json.loads((WORK / 'results.json').read_text())
        current = {k: v for k, v in d.items() if k.startswith(('sweep_pkg', 'corners_pkg', 'bondwire_', 'settle'))}
        superseded = sorted(k for k in d if k not in current)
        cps = [r for k, v in current.items() if k.startswith('corners_pkg') for r in v]
        summary = {k: dict(points=len(v), passed=sum(1 for r in v if r.get('pass')),
                           worst_on_v=min(min(r['steady_state_projection']['on_i_v'], r['steady_state_projection']['on_q_v']) for r in v),
                           worst_off_v=max(max(r['steady_state_projection']['off_i_v'], r['steady_state_projection']['off_q_v']) for r in v),
                           q_minus_i_deg=[min(r['q_minus_i_deg'] for r in v), max(r['q_minus_i_deg'] for r in v)],
                           pad_peak_max_v=max(r['pad_i_max_v'] for r in v))
                   for k, v in current.items() if k.startswith(('corners_pkg', 'bondwire_'))}
        d = current
        rec = dict(block='lo_ext', bench='lo_ext_pad.py: external LO through the drawn pads: refpad (tx_protected_pad, VCM=VDD/2) on REF_IN (I), rf_protected_pad debug pair on AUX_CLK (Q)',
                   generated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                   source_hashes={str(p.relative_to(REPO)): sha(p) for p in (Path(__file__), PAD, REFPAD, LOEXT, RX)},
                   simulator=dict(image=SIM_IMAGE, binary=NGSPICE),
                   criteria=('f within 1 %; RX switch Vgs (source at the mixer VCM = VDD/2) on >= 0.9 V and off <= 0.5 V for both I and Q, '
                             'judged on the steady-state projection (avg(LO) = VB(t=0); measured waveform kept about it); 80 < |Q-I| < 100 deg '
                             '(differential zero crossings)'),
                   package_model='board 50 ohm source + 10 pF C0G per leg (B19); bond wire 1.5 nH + 0.2 ohm per leg (B21; 1.0/2.0 nH in bondwire_*); 0.1 pF pad-to-pad',
                   pads='REF_IN (I): refpad tx_protected_pad, VCM = VDD/2 (stress-safe-families/reference/physical.spice); '
                        'AUX_CLK (Q): rf_protected_pad debug pair; both with the disabled extracted diff_clk_rx',
                   settle_note=('settle_*: long runs at ss/32/3.15, 3 Vpp. The 200 ns run used the previous lo_ext (VB = 0.773 VDD), '
                                'the 300 ns run the current one (0.716 VDD). VB and the LO DC recover towards VB(t=0) with ~200 ns time '
                                'constants, which is what the steady-state projection assumes; the pad DC is still rising at the end.'),
                   summary=summary, superseded_keys_in_scratch=superseded, results=d,
                   verdict='pass' if (cps and all(r.get('pass') for r in cps)) else 'fail')
        (GEN / 'lo_ext-pad-evidence.json').write_text(json.dumps(rec, indent=1) + '\n')
        print('written')


if __name__ == '__main__':
    main()
