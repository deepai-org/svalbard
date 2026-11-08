"""ngspice benches for the rf_tx family (schematic or extracted netlists).

All decks of one invocation run inside one container of the pinned analog
image (``--network none``); waveforms stay in scratch, compact JSON results
are returned. Fixtures (sources, pad model, loads) are ideal elements; the
devices under test are gf180mcuD transistors and resistors only.
"""
import json
import subprocess
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ANALOG_IMAGE = 'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
ANALOG_IMAGE_REF = 'docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3'
MODELS = '/foss/pdks/gf180mcuD/libs.tech/ngspice'
F_LO = 2.44e9
T_LO = 1 / F_LO
CORNER_LIBS = {'tt': ('typical', 'res_typical'), 'ss': ('ss', 'res_ss'), 'ff': ('ff', 'res_ff')}
PORTS = {
    'txmix': 'VDD VSS bb_p bb_n dac_p dac_n lo_p lo_n out_p out_n ibias en sel_dac atb_bias atb_tail',
    'txsum': 'VDD VSS i_p i_n q_p q_n out_p out_n en atb_cm',
    'rfdriver': 'VDD VSS in_p in_n pad_p pad_n ibias en mute bypass g0 g1 g2 g3 atb_bias atb_pre atb_cm',
}


def header(view, corner='tt', temp=27):
    mos, res = CORNER_LIBS[corner]
    inc = []
    for blk in ('txmix_i', 'txmix_q', 'txsum', 'rfdriver'):
        f = f'/rf_tx/generated/{blk}.ext.spice' if view == 'ext' else f'/rf_tx/{blk}.spice'
        inc.append(f'.include {f}')
    return '\n'.join([f'* rf_tx bench view={view} corner={corner} temp={temp}',
                      f'.include {MODELS}/design.ngspice', f'.lib {MODELS}/sm141064.ngspice {mos}',
                      f'.lib {MODELS}/sm141064.ngspice {res}', f'.temp {temp}',
                      '.options method=gear reltol=1e-3 abstol=1e-12 vntol=1e-6', *inc, ''])


def lo_sources(prefix, delay, high=3.3, rs=50, f=F_LO):
    """Differential rail-to-rail square LO (assumed quadrature-buffer output), 50 ohm source."""
    t = 1 / f
    return (f'V{prefix}p {prefix}p_s 0 PULSE(0 {high} {delay} 30p 30p {t / 2 - 30e-12} {t})\n'
            f'V{prefix}n {prefix}n_s 0 PULSE({high} 0 {delay} 30p 30p {t / 2 - 30e-12} {t})\n'
            f'R{prefix}p {prefix}p_s {prefix}p {rs}\nR{prefix}n {prefix}n_s {prefix}n {rs}\n')


def pad_load(p='pad_p', n='pad_n', match=None):
    """rftxpad allocation: 2 ohm + 1 pF per leg, then the board load.

    match=None: 50 ohm differential (balun / DC-blocked) load straight on the pads.
    match=dict: lossy external matching network (see design_match) between the pads and the
    50 ohm differential load; the load voltage is always v(lp)-v(ln).
    """
    t = f'RPADP {p} padx_p 2\nRPADN {n} padx_n 2\nCPADP padx_p 0 1p\nCPADN padx_n 0 1p\n'
    if not match:
        return t + 'VLPP padx_p lp 0\nVLPN padx_n ln 0\nRLOAD lp ln 50\n'
    w = 2 * np.pi * match['f']
    q = match.get('q_l', 30.0)
    def shunt(a, b, kind, val, tag):
        if kind == 'L':
            return f'LSH{tag} {a} sh{tag} {val}\nRSH{tag} sh{tag} {b} {w * val / q}\n'
        return f'CSH{tag} {a} {b} {val}\n'
    if match['shunt_pad']:
        t += shunt('padx_p', 'padx_n', *match['shunt_pad'], 'A')
    ls = match['series_l'] / 2
    t += (f'LMSP padx_p msp1 {ls}\nRMSP msp1 lp {w * ls / q}\nLMSN padx_n msn1 {ls}\nRMSN msn1 ln {w * ls / q}\n')
    if match['shunt_load']:
        t += shunt('lp', 'ln', *match['shunt_load'], 'B')
    return t + f'RLOAD lp ln {match.get("r_load", 50)}\n'


def design_match(y_pad, f=F_LO, r_load=50.0, q_l=30.0):
    """Conjugate-match lossless L-section from r_load (differential, after an ideal balun) to the
    measured differential pad admittance y_pad = G + jB. Inductor Q = q_l is applied in simulation."""
    w = 2 * np.pi * f
    g, b = y_pad.real, y_pad.imag
    ro = 1 / g
    if ro >= r_load:
        qm = np.sqrt(ro / r_load - 1)
        b_net = qm / ro - b          # extra capacitive susceptance wanted at the pad side
        series_l = qm * r_load / w
        shunt_load = None
    else:
        qm = np.sqrt(r_load / ro - 1)
        b_net = -b                   # cancel pad susceptance, then series L, shunt C at the load
        series_l = qm * ro / w
        shunt_load = ('C', qm / r_load / w)
    shunt_pad = None if abs(b_net) < 1e-6 else (('C', float(b_net / w)) if b_net > 0 else ('L', float(1 / (w * -b_net))))
    if shunt_load:
        shunt_load = (shunt_load[0], float(shunt_load[1]))
    return dict(f=float(f), q_l=q_l, r_load=r_load, shunt_pad=shunt_pad, series_l=float(series_l), shunt_load=shunt_load,
                r_opt_ohm=float(ro), pad_susceptance_S=float(b))


def zout_deck(view, gain=15, f=F_LO, out='w.txt', corner='tt', temp=27, vdd=3.3, bypass=0, rs_in=0.001):
    """Differential admittance at the pad (after the 2 ohm + 1 pF pad model). bypass=1: driver off,
    bypass on; the input is then driven through rs_in per leg (txsum output impedance stand-in)."""
    g = [vdd * ((gain >> k) & 1) for k in range(4)]
    return header(view, corner, temp) + f"""
VDD vdd 0 {vdd}
VSS VSS 0 0
VEN en 0 {0 if bypass else vdd}
VM mute 0 0
VB byp 0 {vdd * bypass}
VG0 g0 0 {g[0]}
VG1 g1 0 {g[1]}
VG2 g2 0 {g[2]}
VG3 g3 0 {g[3]}
IB 0 ib 10u
VIP inps 0 2.82
VIN inns 0 2.82
RIP inps inp {rs_in}
RIN inns inn {rs_in}
X1 vdd VSS inp inn pad_p pad_n ib en mute byp g0 g1 g2 g3 ab ap ac pt_rfdriver
RPP pad_p padx_p 2
RPN pad_n padx_n 2
CPP padx_p 0 1p
CPN padx_n 0 1p
IT padx_n padx_p DC 0 AC 1
.control
ac lin 1 {f} {f}
let y = 1/(v(padx_p)-v(padx_n))
wrdata {out} real(y) imag(y)
.endc
.end
"""


def bb_sources(name, vdiff_i, vdiff_q, fbb=None, cm=1.65):
    """Baseband differential sources. DC if fbb is None, else I=cos, Q=sin at fbb."""
    if fbb is None:
        return (f'V{name}ip {name}ip 0 DC {cm + vdiff_i / 2}\nV{name}in {name}in 0 DC {cm - vdiff_i / 2}\n'
                f'V{name}qp {name}qp 0 DC {cm + vdiff_q / 2}\nV{name}qn {name}qn 0 DC {cm - vdiff_q / 2}\n')
    a, b = vdiff_i / 2, vdiff_q / 2
    return (f'V{name}ip {name}ip 0 SIN({cm} {a} {fbb} 0 0 90)\nV{name}in {name}in 0 SIN({cm} {-a} {fbb} 0 0 90)\n'
            f'V{name}qp {name}qp 0 SIN({cm} {b} {fbb} 0 0 0)\nV{name}qn {name}qn 0 SIN({cm} {-b} {fbb} 0 0 0)\n')


def chain_deck(view, *, vdd=3.3, corner='tt', temp=27, vin_i=0.3, vin_q=0.0, fbb=None, sel_dac=0,
               en=(1, 1, 1, 1), mute=0, bypass=0, gain=15, tstop=8e-9, out='w.txt', lo_high=3.3, ibias=10e-6,
               f_lo=F_LO, match=None, sat=0):
    """Full TX chain: two mixers -> txsum -> rfdriver -> pad model."""
    v = lambda b: vdd * b
    en_mi, en_mq, en_s, en_d = en
    g = [v((gain >> k) & 1) for k in range(4)]
    bb = bb_sources('bb', vin_i if not sel_dac else 0.0, vin_q if not sel_dac else 0.0, fbb)
    dac = bb_sources('dac', vin_i if sel_dac else 0.0, vin_q if sel_dac else 0.0, fbb)
    d = header(view, corner, temp) + f"""
VDMI vdd_mi 0 {vdd}
VDMQ vdd_mq 0 {vdd}
VDS vdd_s 0 {vdd}
VDD vdd_d 0 {vdd}
VSS VSS 0 0
VENMI en_mi 0 {v(en_mi)}
VENMQ en_mq 0 {v(en_mq)}
VENS en_s 0 {v(en_s)}
VEND en_d 0 {v(en_d)}
VSEL sel 0 {v(sel_dac)}
VSAT satm 0 {v(sat)}
VMUTE mute 0 {v(mute)}
VBYP byp 0 {v(bypass)}
VG0 g0 0 {g[0]}
VG1 g1 0 {g[1]}
VG2 g2 0 {g[2]}
VG3 g3 0 {g[3]}
IBMI 0 ib_mi {ibias}
IBMQ 0 ib_mq {ibias}
IBD 0 ib_d {ibias}
{bb}{dac}{lo_sources('loi', 0, lo_high, f=f_lo)}{lo_sources('loq', 1 / f_lo / 4, lo_high, f=f_lo)}
XMI vdd_mi VSS bbip bbin dacip dacin loip loin ip in ib_mi en_mi sel satm atbmi_b atbmi_t pt_txmix_i
XMQ vdd_mq VSS bbqp bbqn dacqp dacqn loqp loqn qp qn ib_mq en_mq sel satm atbmq_b atbmq_t pt_txmix_q
XS vdd_s VSS ip in qp qn sp sn en_s atbs_cm pt_txsum
XD vdd_d VSS sp sn pad_p pad_n ib_d en_d mute byp g0 g1 g2 g3 atbd_b atbd_p atbd_c pt_rfdriver
{pad_load(match=match)}
.control
tran 1p {tstop} 0 2p
wrdata {out} v(lp)-v(ln) v(sp)-v(sn) v(ip)-v(in) i(VDMI) i(VDMQ) i(VDS) i(VDD) v(atbd_b) v(atbd_p) v(atbd_c) v(atbs_cm) v(atbmi_b) v(atbmi_t) v(pad_p) v(sp)
.endc
.end
"""
    return d


def tone(t, y, f, t0, t1):
    tt = np.linspace(t0, t1, int(round((t1 - t0) / 0.5e-12)) + 1)
    yy = np.interp(tt, t, y)
    return 2 * abs(np.trapezoid(yy * np.exp(-2j * np.pi * f * tt), tt) / (t1 - t0))


def dbm(vpk_diff, rl=50.0):
    p = vpk_diff ** 2 / 2 / rl
    return float(10 * np.log10(p / 1e-3)) if p > 0 else -999.0


def run_decks(decks, label):
    """decks: {name: text}. Runs all in one analog-image container; returns {name: (stdout path, data dir)}."""
    work = (REPO / 'scratch/rf_tx/sim' / label).resolve()
    work.mkdir(parents=True, exist_ok=True)
    names = []
    for old in list(work.glob('*.txt')) + list(work.glob('*.log')):
        old.unlink()
    for name, text in decks.items():
        (work / f'{name}.sp').write_text(text)
        names.append(name)
    (work / '.spiceinit').write_text('set ngbehavior=hs\nset num_threads=1\n')
    script = ('cd /work && printf "%s\\n" ' + ' '.join(names) +
              ' | xargs -P 3 -I{} sh -c "/foss/tools/bin/ngspice -b {}.sp > {}.log 2>&1"')
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '3', '--memory', '6g', '--entrypoint', '/bin/bash',
           '-e', 'OMP_NUM_THREADS=1', '-v', f'{work}:/work', '-v', f'{HERE}:/rf_tx:ro', ANALOG_IMAGE, '-c', script]
    subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    return work


def load(work, name):
    f = Path(work) / f'{name}.txt'
    if not f.exists():
        raise RuntimeError(f'{name}: no waveform; see {work}/{name}.log')
    d = np.loadtxt(f)
    # wrdata writes (x, y) pairs per vector; keep time plus every second column
    return d[:, 0], d[:, 1::2]


def chain_metrics(work, name, tstop, fbb=None, f_lo=F_LO):
    t, y = load(work, name)
    if fbb is None:
        t1 = tstop; t0 = t1 - 8 / f_lo
        pad = tone(t, y[:, 0], f_lo, t0, t1)
        sm = tone(t, y[:, 1], f_lo, t0, t1)
        mi = tone(t, y[:, 2], f_lo, t0, t1)
        res = dict(pad_fund_mVpk_diff=round(1e3 * pad, 3), pad_dBm_50ohm=round(dbm(pad), 2),
                   sum_fund_mVpk_diff=round(1e3 * sm, 3), mixi_drain_fund_mVpk_diff=round(1e3 * mi, 3))
    else:
        t1 = tstop; t0 = t1 - 1 / fbb
        res = {}
        for lab, f in (('lsb', F_LO - fbb), ('lo', F_LO), ('usb', F_LO + fbb), ('lsb3', F_LO - 3 * fbb), ('usb3', F_LO + 3 * fbb)):
            a = tone(t, y[:, 0], f, t0, t1)
            res[f'{lab}_dBm'] = round(dbm(a), 2)
        res['wanted'] = 'usb' if res['usb_dBm'] > res['lsb_dBm'] else 'lsb'
        w, u = (res['usb_dBm'], res['lsb_dBm']) if res['wanted'] == 'usb' else (res['lsb_dBm'], res['usb_dBm'])
        res['image_rejection_dB'] = round(w - u, 2)
        res['lo_suppression_dBc'] = round(w - res['lo_dBm'], 2)
    m = t >= t0
    res['supply_mA'] = {k: round(-1e3 * float(np.mean(y[m, i])), 4) for i, k in
                        ((3, 'txmix_i'), (4, 'txmix_q'), (5, 'txsum'), (6, 'rfdriver'))}
    res['atb_V'] = {k: round(float(np.mean(y[m, i])), 4) for i, k in
                    ((7, 'rfdriver.atb_bias'), (8, 'rfdriver.atb_pre'), (9, 'rfdriver.atb_cm'),
                     (10, 'txsum.atb_cm'), (11, 'txmix_i.atb_bias'), (12, 'txmix_i.atb_tail'))}
    res['pad_cm_V'] = round(float(np.mean(y[m, 13])), 4)
    res['sum_cm_V'] = round(float(np.mean(y[m, 14])), 4)
    return res
