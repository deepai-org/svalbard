"""Testbenches for the RF receive family (schematic or extracted netlists).

Every function returns a dict of measured numbers (or raises).  `view` selects
the netlist: 'sch' = <block>.spice, 'ext' = generated/<block>.ext.spice
(Magic extraction with parasitic capacitance).  Corners are (mos, temp_C, vdd).
"""
import math
from pathlib import Path

import rfrx_flow as flow
import simlib as S

HERE = flow.HERE
CTRL_BBF = ['en', 'dir_tx', 'inj', 'rx_direct', 'byp_s1', 'byp_s23', 'obs_sel0', 'obs_sel1',
            'bw0', 'bw1', 'bw2', 'bw3', 'gain0', 'gain1', 'gain2', 'gain3', 'gain4', 'gain5', 'gainc0', 'gainc1',
            'qt0', 'qt1', 'island_off']
BBF_PINS = ('rx_in_p rx_in_n tx_in_p tx_in_n inj_p inj_n out_rx_p out_rx_n out_tx_p out_tx_n obs_p obs_n '
            'ibias en dir_tx inj rx_direct byp_s1 byp_s23 obs_sel0 obs_sel1 bw0 bw1 bw2 bw3 gain0 gain1 gain2 '
            'gain3 gain4 gain5 gainc0 gainc1 qt0 qt1 island_off atb_vcm atb_vbp VDD 0')


def netlist(work, block, view):
    src = HERE / f'{block}.spice' if view == 'sch' else flow.GENERATED / f'{block}.ext.spice'
    return S.prepare(work, src, f'{block}_{view}.spice')


PGA_GAIN_BITS = ('gain0', 'gain1', 'gain2', 'gain3', 'gain4', 'gain5', 'gainc0', 'gainc1')
PGA_UNITY = ('gain2',)    # PGA code for 0 dB (k = 4, coarse off): the register reset value
# Q-trim (RC-6): reset code 1 (qt0); the trim is set per part at bring-up. Benches that do not name a
# code use the per-process code from the extracted Q-trim study: tt/ss 1, ff 2 (ff peaks 6.4 dB at code 0).
QT_RESET = 1
QT_BY_PROC = {'typical': 1, 'ss': 1, 'ff': 2}
# LNA package-tolerance controls (RC-8a/RC-9/RC-10): C-trim reset code 4, se/rt off.
LNA_CT_RESET = 4


def qt_bits(code):
    return tuple(b for k, b in enumerate(('qt0', 'qt1')) if (code >> k) & 1)


def _lna_trim(vdd, ct=LNA_CT_RESET, se=False, rt=False):
    return '\n'.join([f'Vct{k} ct{k} 0 {vdd if (ct >> k) & 1 else 0}' for k in range(3)] +
                     [f'Vse se 0 {vdd if se else 0}', f'Vrt rt 0 {vdd if rt else 0}'])


def _ctl(names, on, vdd):
    """Benches that enable the filter without naming a PGA code run it at 0 dB (k = 4): a PGA
    code of all zeros mutes stage 1 (no input conductance)."""
    on = set(on)
    if 'gain2' in names and 'en' in on and not on & set(PGA_GAIN_BITS):
        on |= set(PGA_UNITY)
    if 'qt0' in names and 'qtx' not in on and not on & {'qt0', 'qt1'}:
        on |= set(qt_bits(QT_RESET))
    on.discard('qtx')     # 'qtx' = explicit qt code 0
    return '\n'.join(f'V{c} {c} 0 {vdd if c in on else 0}' for c in names)


def _tag(corner):
    c, t, v = corner
    return f'{c}_{t}_{v}'


def run(work, name, body, corner, timeout=3600):
    c, t, v = corner
    log, m = S.run(work, name, body, corner=c, temp=t, timeout=timeout)
    if 'error' in log.lower() and not m:
        raise RuntimeError(f'{name}: ngspice error\n{log[-1500:]}')
    return log, m


def _ofs(code, vdd, sfx=''):
    """Offset-DAC control sources: sign-magnitude code -31..31 (sign 1 = negative code)."""
    mag, sgn = abs(int(code)), int(code < 0)
    lines = [f'Vofs{k}{sfx} ofs{k}{sfx} 0 {vdd if (mag >> k) & 1 else 0}' for k in range(5)]
    return '\n'.join(lines + [f'Vofsg{sfx} ofs_sign{sfx} 0 {vdd if sgn else 0}'])


def tone(path, f, t0, t1, col=1):
    """Amplitude of the f component of column `col` of an ngspice wrdata file over [t0, t1]
    (trapezoidal DFT on the non-uniform time grid; [t0, t1] spans whole periods)."""
    rows = [r for r in S.read_table(path) if t0 <= r[0] <= t1]
    re_ = im = 0.
    w = 2 * math.pi * f
    for a, b in zip(rows, rows[1:]):
        dt = b[0] - a[0]
        va, vb = a[2 * col - 1], b[2 * col - 1]
        re_ += .5 * dt * (va * math.cos(w * a[0]) + vb * math.cos(w * b[0]))
        im += .5 * dt * (va * math.sin(w * a[0]) + vb * math.sin(w * b[0]))
    return 2 * math.hypot(re_, im) / (t1 - t0)


# ---------------------------------------------------------------- LNA
def lna_ac(work, view, corner=('typical', 27, 3.3), mode='active', f=2.4e9, match=None, ct=LNA_CT_RESET, se=False, rt=False):
    c, t, vdd = corner
    if match:
        src = 'Ep e_p 0 s 0 0.5\nEn e_n 0 s 0 -0.5\nRsp e_p sp 50\nRsn e_n sn 50\n' + _match_net(match)
    else:
        src = 'Ep sp 0 s 0 0.5\nEn sn 0 s 0 -0.5\nRsp sp rf_in_p 50\nRsn sn rf_in_n 50\n'
    nl = netlist(work, 'lna', view)
    on = {'active': {'en'}, 'gain_lo': {'en', 'gain_lo'}, 'bypass': {'byp'}, 'off': set()}[mode]
    body = f""".include {nl}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias 10u
{_ctl(['en', 'gain_lo', 'byp', 'island_off'], on, vdd)}
* ideal balun: 100 ohm differential source, 0.5 pF disabled-pad loading per leg
Vs s 0 DC 0 AC 1
{src}Cpp rf_in_p 0 0.5p
Cpn rf_in_n 0 0.5p
* passive-mixer input approximation: 50 ohm per leg to an AC ground at VCM
Rmp rf_out_p vm 50
Rmn rf_out_n vm 50
Rmqp rf_outq_p vm 50
Rmqn rf_outq_n vm 50
Vm vm 0 1.65
{_lna_trim(vdd, ct, se, rt)}
X1 rf_in_p rf_in_n rf_out_p rf_out_n rf_outq_p rf_outq_n ibias en gain_lo byp ct0 ct1 ct2 se rt island_off atb_nbias atb_vdcm VDD 0 pt_lna
.control
op
let idd=-i(VDD)
let vdcm=v(atb_vdcm)
print idd vdcm
ac lin 1 {f} {f}
let gv=db(v(rf_out_p)-v(rf_out_n))
let zin={'(v(sp)-v(sn))/(v(e_p)-v(e_n)-v(sp)+v(sn))*100' if match else '(v(rf_in_p)-v(rf_in_n))/(v(sp)-v(sn)-v(rf_in_p)+v(rf_in_n))*100'}
let zr=real(zin)
let zi=imag(zin)
print gv zr zi
noise v(rf_out_p,rf_out_n) Vs lin 1 {f} {f}
setplot noise1
let nf=10*log10(inoise_spectrum^2/(4*1.380649e-23*{273.15 + t}*100))
print nf
.endc
"""
    trim = '' if (ct, se, rt) == (LNA_CT_RESET, False, False) else f'ct{ct}{"se" if se else ""}{"rt" if rt else ""}_'
    log, m = run(work, f'lna_{trim}{mode}_{int(f / 1e6)}_{"m" if match else "u"}_{view}_{_tag(corner)}.cir', body, corner)
    return dict(idd_a=m.get('idd'), gain_db=m.get('gv'), zin_re_ohm=m.get('zr'), zin_im_ohm=m.get('zi'),
                nf_db=m.get('nf'), vd_cm_v=m.get('vdcm'))


def lna_unpowered(work, view, temp=27, vctl=3.63):
    """Island rail at 0 V: controls and the protected RF pad node at vctl. Pin currents."""
    nl = netlist(work, 'lna', view)
    body = f""".include {nl}
VDD VDD 0 0
Vib ibias 0 0
Ven en 0 {vctl}
Vgl gain_lo 0 {vctl}
Vby byp 0 {vctl}
Viso island_off 0 {vctl}
Vct0 ct0 0 {vctl}
Vct1 ct1 0 {vctl}
Vct2 ct2 0 {vctl}
Vse se 0 {vctl}
Vrt rt 0 {vctl}
Vrp rf_in_p 0 {vctl}
Vrn rf_in_n 0 0
X1 rf_in_p rf_in_n rf_out_p rf_out_n rf_outq_p rf_outq_n ibias en gain_lo byp ct0 ct1 ct2 se rt island_off atb_nbias atb_vdcm VDD 0 pt_lna
.option abstol=1e-15 reltol=1e-6 vntol=1e-9 itl1=500
.control
op
let ipad=abs(i(Vrp))+abs(i(Vrn))
let ictl=abs(i(Ven))+abs(i(Vgl))+abs(i(Vby))+abs(i(Viso))+abs(i(Vct0))+abs(i(Vct1))+abs(i(Vct2))+abs(i(Vse))+abs(i(Vrt))
let irail=abs(i(VDD))
print ipad ictl irail
.endc
"""
    log, m = run(work, f'lna_unpowered_{view}_{temp}.cir', body, ('typical', temp, 0))
    return dict(pad_current_a=m.get('ipad'), control_current_a=m.get('ictl'), rail_current_a=m.get('irail'))


# ---------------------------------------------------------------- mixer
def rxmix_tran(work, view, corner=('typical', 27, 3.3), block='rxmix_i', amp=0.01, fif=5e6, ofs=0):
    c, t, vdd = corner
    nl = netlist(work, block, view)
    flo = 2.4e9
    per = 1 / flo
    body = f""".include {nl}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias 10u
Ven en 0 {vdd}
Viso island_off 0 0
* RF: differential tone at LO+IF, 300 ohm per leg (LNA output resistance class), AC-coupled
Vs s 0 DC 0 SIN(0 {amp} {flo + fif})
Ep sp 0 s 0 0.5
En sn 0 s 0 -0.5
Rsp sp rp 300
Rsn sn rn 300
Ccp rp rf_p 4p
Ccn rn rf_n 4p
Vlp lo_p 0 PULSE(0 {vdd} 0 20p 20p {per / 2 - 20e-12} {per})
Vln lo_n 0 PULSE({vdd} 0 0 20p 20p {per / 2 - 20e-12} {per})
{_ofs(ofs, vdd)}
X1 rf_p rf_n lo_p lo_n bb_p bb_n ibias en ofs0 ofs1 ofs2 ofs3 ofs4 ofs_sign island_off atb_vcm atb_vbp VDD 0 pt_{block}
Cbp bb_p 0 1p
Cbn bb_n 0 1p
.save v(bb_p) v(bb_n) i(VDD) v(atb_vcm)
.tran 10p {3.5 / fif} {1.5 / fif} 10p
.control
run
let vbb=v(bb_p)-v(bb_n)
meas tran vpp pp vbb from={1.5 / fif} to={3.5 / fif}
meas tran vavg avg vbb from={1.5 / fif} to={3.5 / fif}
meas tran idd avg i(VDD) from={1.5 / fif} to={3.5 / fif}
meas tran vcm avg v(atb_vcm) from={1.5 / fif} to={3.5 / fif}
wrdata {block}_tran_{view}_{_tag(corner)}_{ofs}.dat vbb
.endc
"""
    log, m = run(work, f'{block}_tran_{view}_{_tag(corner)}_{ofs}.cir', body, corner, timeout=7200)
    a = tone(work / f'{block}_tran_{view}_{_tag(corner)}_{ofs}.dat', fif, 1.5 / fif, 3.5 / fif)
    vpp = m.get('vpp')
    g = 20 * math.log10(a / amp) if a else None
    return dict(conversion_gain_db=g, bb_tone_amp_v=a, bb_pp_v=vpp, bb_offset_v=m.get('vavg'), idd_a=-m['idd'] if 'idd' in m else None,
                vcm_v=m.get('vcm'), rf_amp_diff_v=amp, if_hz=fif, source='300 ohm/leg, 4 pF coupling')


def rxmix_dc(work, view, block='rxmix_i', vdd=3.3, en=0, temp=27, lo=0.0, vbb=None, ofs=0):
    nl = netlist(work, block, view)
    body = f""".include {nl}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias {'10u' if vdd > 0 else '0'}
Ven en 0 {en * 3.3 if vdd > 0 else 3.63}
Viso island_off 0 {0 if vdd > 0 else 3.63}
Vlp lo_p 0 {lo}
Vln lo_n 0 0
* rf_p/n sit behind the LNA's MIM output caps (no DC source): weak ties to ground only
Vrp rfr 0 0
Rrp rf_p rfr 10meg
Rrn rf_n rfr 10meg
{_ofs(ofs, vdd)}
X1 rf_p rf_n lo_p lo_n bb_p bb_n ibias en ofs0 ofs1 ofs2 ofs3 ofs4 ofs_sign island_off atb_vcm atb_vbp VDD 0 pt_{block}
{'' if vbb is None else f'Vbbp bb_p 0 {vbb + 0.2}' + chr(10) + f'Vbbn bb_n 0 {vbb - 0.2}'}
.option abstol=1e-15 reltol=1e-6 vntol=1e-9 itl1=500
.control
op
let irail=abs(i(VDD))
let irf=abs(i(Vrp))
{'' if vbb is None else 'let ibb=abs(i(Vbbp))+abs(i(Vbbn))' + chr(10) + 'print ibb'}
let ictl=abs(i(Ven))+abs(i(Viso))+abs(i(Vlp))
let bbp=v(bb_p)
let bbn=v(bb_n)
print irail irf ictl bbp bbn
.endc
"""
    log, m = run(work, f'{block}_dc_{view}_{vdd}_{en}_{temp}_{vbb}.cir', body, ('typical', temp, vdd))
    return dict(rail_current_a=m.get('irail'), rf_pin_current_a=m.get('irf'), control_current_a=m.get('ictl'),
                forced_bb_current_a=m.get('ibb'),
                bb_p_v=m.get('bbp'), bb_n_v=m.get('bbn'))


# ---------------------------------------------------------------- baseband filter
def _bbf_deck(nl, vdd, on, src='rx', inj_drive=False, extra=''):
    """Inputs at 1.65 V common mode; the filter references the measured input CM (atb_vcm)."""
    srcs = {'rx': ('rx_in', 'tx_in'), 'tx': ('tx_in', 'rx_in')}[src]
    a, b = srcs
    ref = 'Vcmr cmr 0 1.65\n'
    inj = ('Vjp inj_p cmr DC 0 AC 0.5\nVjn inj_n cmr DC 0 AC -0.5\n'
           f'Rrx1 {a}_p cmr 1meg\nRrx2 {a}_n cmr 1meg\n' if inj_drive else '')
    drive = '' if inj_drive else f'Vap {a}_p cmr DC 0 AC 0.5\nVan {a}_n cmr DC 0 AC -0.5\n'
    return f""".include {nl}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias 10u
{ref}{drive}Vbp {b}_p cmr 0
Vbn {b}_n cmr 0
{inj}{_ctl(CTRL_BBF, on, vdd)}
X1 {BBF_PINS} pt_{{blk}}
Cl1 out_rx_p 0 1p
Cl2 out_rx_n 0 1p
Cl3 out_tx_p 0 1p
Cl4 out_tx_n 0 1p
Cl5 obs_p 0 1p
Cl6 obs_n 0 1p
{extra}"""


def bbf_cm_sensitivity(work, view, corner=('typical', 27, 3.3), block='bbfilter_i', on=('en',), dv=0.1):
    """Output CM minus input CM with the input CM moved to 1.65 V + dv."""
    c, t, vdd = corner
    nl = netlist(work, block, view)
    body = _bbf_deck(nl, vdd, set(on)).replace('{blk}', block).replace('Vcmr cmr 0 1.65', f'Vcmr cmr 0 {1.65 + dv}') + f"""
.control
op
let ocm=(v(out_rx_p)+v(out_rx_n))/2-{1.65 + dv}
print ocm
.endc
"""
    log, m = run(work, f'{block}_cm_{len(on)}_{dv}_{view}_{_tag(corner)}.cir', body, corner)
    return dict(out_cm_minus_in_cm_v=m.get('ocm'), input_cm_v=1.65 + dv)


def bbf_ac(work, view, corner=('typical', 27, 3.3), block='bbfilter_i', on=('en',), src='rx', out='out_rx',
           inj_drive=False, tag='rx', qt=None):
    """qt: Q-trim code 0..3; None = the per-process code QT_BY_PROC (tt/ss 1 = reset, ff 2)."""
    c, t, vdd = corner
    nl = netlist(work, block, view)
    q = QT_BY_PROC.get(c, QT_RESET) if qt is None else qt
    on = set(on) | (set(qt_bits(q)) or {'qtx'})
    if qt is not None:
        tag = f'{tag}_qt{qt}'
    body = _bbf_deck(nl, vdd, on, src, inj_drive).replace('{blk}', block) + f"""
.control
op
let idd=-i(VDD)
let ocm=(v({out}_p)+v({out}_n))/2
let vcm=v(atb_vcm)
print idd ocm vcm
ac dec 40 10k 200Meg
let g=db(v({out}_p)-v({out}_n))
meas ac g_dc find g at=10k
meas ac g_max max g
meas ac f3db when g=(g_dc-3) fall=1
meas ac g_20m find g at=20Meg
let gl=g
meas ac f_notch min_at gl from=1Meg to=100Meg
wrdata {block}_{tag}_{view}_{_tag(corner)}.ac g
.endc
"""
    log, m = run(work, f'{block}_{tag}_{view}_{_tag(corner)}.cir', body, corner)
    return dict(idd_a=m.get('idd'), dc_gain_db=m.get('g_dc'), peak_gain_db=m.get('g_max'),
                f3db_hz=m.get('f3db'), gain_20mhz_db=m.get('g_20m'),
                out_cm_v=m.get('ocm'), vcm_v=m.get('vcm'), qt_code=q)


def bbf_direction_settle(work, view, corner=('typical', 27, 3.3), block='bbfilter_i'):
    """TX->RX turnaround at the widest bandwidth: dir_tx falls at 2 us; rx_in carries +100 mV DC."""
    c, t, vdd = corner
    nl = netlist(work, block, view)
    on = {'en'}
    ctl = _ctl([x for x in CTRL_BBF if x != 'dir_tx'], on, vdd)
    body = f""".include {nl}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias 10u
Vap rx_in_p 0 1.7
Van rx_in_n 0 1.6
Vbp tx_in_p 0 1.6
Vbn tx_in_n 0 1.7
{ctl}
Vdir dir_tx 0 PULSE({vdd} 0 2u 2n 2n 10u 20u)
X1 {BBF_PINS} pt_{block}
Cl1 out_rx_p 0 1p
Cl2 out_rx_n 0 1p
.tran 2n 5u
.control
run
let vo=v(out_rx_p)-v(out_rx_n)
meas tran vfinal avg vo from=4.5u to=5u
let err=abs(vo-vfinal)
meas tran tsettle when err=0.002 cross=last
.endc
"""
    log, m = run(work, f'{block}_dirsettle_{view}_{_tag(corner)}.cir', body, corner)
    ts = m.get('tsettle')
    return dict(final_diff_v=m.get('vfinal'), settle_1pct_after_switch_s=(ts - 2e-6) if ts else None)


def bbf_dc(work, view, block='bbfilter_i', vdd=3.3, on=(), temp=27, vpin=1.65):
    """Supply / pin currents.  vdd=0: island off, island_off=1, cross-island pins held at vpin."""
    nl = netlist(work, block, view)
    on = set(on) | ({'island_off'} if vdd == 0 else set())
    vc = 3.63 if vdd == 0 else 3.3
    body = f""".include {nl}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias {'10u' if vdd > 0 else '0'}
Vap rx_in_p 0 {vpin if vdd > 0 else 0}
Van rx_in_n 0 {vpin if vdd > 0 else 0}
Vbp tx_in_p 0 {vpin}
Vbn tx_in_n 0 {vpin}
Vop out_rx_p 0 {vpin if vdd == 0 else 1.65}
Von out_rx_n 0 {vpin if vdd == 0 else 1.65}
{_ctl(CTRL_BBF, on, vc)}
X1 {BBF_PINS} pt_{block}
.option abstol=1e-15 reltol=1e-6 vntol=1e-9 itl1=500
.control
op
let irail=abs(i(VDD))
let ipins=abs(i(Vap))+abs(i(Van))+abs(i(Vbp))+abs(i(Vbn))+abs(i(Vop))+abs(i(Von))
let itx=abs(i(Vbp))+abs(i(Vbn))
let iadc=abs(i(Vop))+abs(i(Von))
print irail ipins itx iadc
.endc
"""
    log, m = run(work, f'{block}_dc_{view}_{vdd}_{len(on)}_{temp}_{vpin}.cir', body, ('typical', temp, vdd))
    return dict(rail_current_a=m.get('irail'), signal_pin_current_a=m.get('ipins'),
                tx_in_current_a=m.get('itx'), out_rx_current_a=m.get('iadc'))


# ---------------------------------------------------------------- bb_tap
TAP_PINS = 'in_p in_n pad_p pad_n inj_p inj_n ibias obs_en inj_en island_off atb_nbias VDD 0'


def tap_observe(work, view, corner=('typical', 27, 3.3), f=20e6, amp=0.2):
    c, t, vdd = corner
    nl = netlist(work, 'bb_tap', view)
    body = f""".include {nl}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias 10u
Voe obs_en 0 {vdd}
Vie inj_en 0 0
Vis island_off 0 0
Vip in_p 0 DC 1.65 AC 0.5 SIN(1.65 {amp / 2} {f})
Vin in_n 0 DC 1.65 AC -0.5 SIN(1.65 {-amp / 2} {f})
Rjp inj_p 0 1meg
Rjn inj_n 0 1meg
X1 {TAP_PINS} pt_bb_tap
* board: 10 pF per pad, high-impedance external ADC
Cpp pad_p 0 10p
Cpn pad_n 0 10p
Rpp pad_p 0 100k
Rpn pad_n 0 100k
.control
op
let idd=-i(VDD)
let pcm=(v(pad_p)+v(pad_n))/2
print idd pcm
ac dec 40 100k 1G
let g=db(v(pad_p)-v(pad_n))
meas ac g_lf find g at=100k
meas ac f3db when g=(g_lf-3) fall=1
meas ac g_20m find g at=20Meg
tran 0.2n {4 / f} {2 / f}
let vo=v(pad_p)-v(pad_n)
meas tran vpp pp vo
.endc
"""
    log, m = run(work, f'tap_obs_{view}_{_tag(corner)}.cir', body, corner)
    vpp = m.get('vpp')
    return dict(idd_a=m.get('idd'), lf_gain_db=m.get('g_lf'), f3db_hz=m.get('f3db'), gain_20mhz_db=m.get('g_20m'),
                pad_cm_v=m.get('pcm'),
                tran_gain_20mhz_db=20 * math.log10(vpp / (2 * amp)) if vpp else None, load='10 pF || 100 kohm per pad')


def tap_inject(work, view, corner=('typical', 27, 3.3)):
    c, t, vdd = corner
    nl = netlist(work, 'bb_tap', view)
    body = f""".include {nl}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias 10u
Voe obs_en 0 {vdd}
Vie inj_en 0 {vdd}
Vis island_off 0 0
Vip in_p 0 1.65
Vin in_n 0 1.65
Vs s 0 DC 0 AC 1
Ep sp 0 s 0 0.5
En sn 0 s 0 -0.5
Rsp sp pad_p 50
Rsn sn pad_n 50
Vcm s0 0 1.65
Esp pp s0 sp 0 1
Esn pn s0 sn 0 1
Rsp2 pp pad_p 50
Rsn2 pn pad_n 50
X1 {TAP_PINS} pt_bb_tap
* chain node: bbfilter core input (40 kohm input resistors to virtual ground)
Rjp inj_p vcm 20k
Rjn inj_n vcm 20k
Vvcm vcm 0 1.65
.control
op
let idd=-i(VDD)
print idd
ac dec 20 100k 100Meg
let g=db((v(inj_p)-v(inj_n))/(v(pad_p)-v(pad_n)))
meas ac g_lf find g at=100k
meas ac g_20m find g at=20Meg
.endc
"""
    body = body.replace('Rsp sp pad_p 50\nRsn sn pad_n 50\n', '')
    log, m = run(work, f'tap_inj_{view}_{_tag(corner)}.cir', body, corner)
    return dict(idd_a=m.get('idd'), pad_to_node_gain_db=m.get('g_lf'), gain_20mhz_db=m.get('g_20m'))


def tap_off(work, view, vdd=3.3, temp=27, vpad=3.63):
    """Tap off (obs_en=inj_en=0), pads forced to vpad: pad and rail currents (vdd=0: island off)."""
    nl = netlist(work, 'bb_tap', view)
    vc = 3.63 if vdd == 0 else 0
    body = f""".include {nl}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias {'10u' if vdd > 0 else '0'}
Voe obs_en 0 0
Vie inj_en 0 {vc}
Vis island_off 0 {3.63 if vdd == 0 else 0}
Vip in_p 0 {1.65 if vdd > 0 else 0}
Vin in_n 0 {1.65 if vdd > 0 else 0}
Vpp pad_p 0 {vpad}
Vpn pad_n 0 0
Rjp inj_p 0 40k
Rjn inj_n 0 40k
X1 {TAP_PINS} pt_bb_tap
.option abstol=1e-15 reltol=1e-6 vntol=1e-9 itl1=500
.control
op
let ipad=abs(i(Vpp))+abs(i(Vpn))
let irail=abs(i(VDD))
print ipad irail
.endc
"""
    log, m = run(work, f'tap_off_{view}_{vdd}_{temp}_{vpad}.cir', body, ('typical', temp, vdd))
    return dict(pad_current_a=m.get('ipad'), rail_current_a=m.get('irail'))


# ---------------------------------------------------------------- LNA + I/Q mixers
def board_match(zin, rs=100., f=2.4e9):
    """Ideal lossless two-element L-match from rs (differential) to zin (differential).
    Re(zin) < rs: series element per leg at the pad, shunt across the pair at the source.
    Re(zin) > rs: shunt across the pair at the pad, series element per leg at the source."""
    w = 2 * math.pi * f

    def part(x_or_b, series):
        if series:   # reactance x (differential) -> per-leg element of x/2
            x = x_or_b / 2
            return ('L', x / w) if x > 0 else ('C', -1 / (w * x))
        b = x_or_b   # susceptance across the pair
        return ('C', b / w) if b > 0 else ('L', -1 / (w * b))
    rl, xl = zin.real, zin.imag
    if rl < rs:
        q = math.sqrt(rs / rl - 1)
        xs = q * rl - xl
        return dict(order='series_at_pad', series_leg=part(xs, True), shunt_diff=part(q / rs, False), q=q)
    y = 1 / zin
    g, bl = y.real, y.imag
    q = math.sqrt((1 / g) / rs - 1)
    bsh = -q * g - bl
    return dict(order='shunt_at_pad', shunt_diff=part(bsh, False), series_leg=part(-q * rs, True), q=q)


def _match_net(m):
    el = lambda kind, name, a, b, v: f"{'L' if kind == 'L' else 'C'}{name} {a} {b} {v}\n"
    (sk, sv), (pk, pv) = m['series_leg'], m['shunt_diff']
    if m['order'] == 'series_at_pad':
        return (el(sk, 'mp', 'sp', 'rf_in_p', sv) + el(sk, 'mn', 'sn', 'rf_in_n', sv) +
                el(pk, 'mx', 'sp', 'sn', pv))
    return (el(sk, 'mp', 'sp', 'rf_in_p', sv) + el(sk, 'mn', 'sn', 'rf_in_n', sv) +
            el(pk, 'mx', 'rf_in_p', 'rf_in_n', pv))


def chain_tran(work, view, corner=('typical', 27, 3.3), mode='lna', amp=3e-3, fif=5e6, flo=2.4e9, match=None,
               ofs=0, ofs_q=0):
    """RF pad -> LNA (or bypass switch) -> I/Q passive mixers + TIAs.  Conversion gain from the
    differential source EMF to each baseband output.  `match` = board_match() dict or None."""
    c, t, vdd = corner
    nl = netlist(work, 'lna', view)
    ni = netlist(work, 'rxmix_i', view)
    nq = netlist(work, 'rxmix_q', view)
    per = 1 / flo
    on = {'lna': {'en'}, 'bypass': {'byp'}}[mode]
    net = ''
    if match:
        net = _match_net(match)
        src = 'Rsp s_p sp 50\nRsn s_n sn 50\n'
        pads = ''
    else:
        src = 'Rsp s_p rf_in_p 50\nRsn s_n rf_in_n 50\n'
        pads = ''
    lo = lambda name, inv, delay: (f"V{name} {name} 0 PULSE({0 if not inv else vdd} {vdd if not inv else 0} "
                                   f"{delay} 20p 20p {per / 2 - 20e-12} {per})")
    body = f""".include {nl}
.include {ni}
.include {nq}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib1 vib ib1 10u
Ib2 vib ib2 10u
Ib3 vib ib3 10u
{_ctl(['en', 'gain_lo', 'byp', 'island_off'], on, vdd)}
Venm enm 0 {vdd}
Vs s 0 DC 0 SIN(0 {amp} {flo + fif})
Ep s_p 0 s 0 0.5
En s_n 0 s 0 -0.5
{src}{net}{pads}Cpp rf_in_p 0 0.5p
Cpn rf_in_n 0 0.5p
{lo('lip', 0, 0)}
{lo('lin', 1, 0)}
{lo('lqp', 0, per / 4)}
{lo('lqn', 1, per / 4)}
{_lna_trim(vdd)}
XL rf_in_p rf_in_n rfo_p rfo_n rfq_p rfq_n ib1 en gain_lo byp ct0 ct1 ct2 se rt island_off nb vdcm VDD 0 pt_lna
{_ofs(ofs, vdd, 'i')}
{_ofs(ofs_q, vdd, 'q')}
XI rfo_p rfo_n lip lin bip bin ib2 enm ofs0i ofs1i ofs2i ofs3i ofs4i ofs_signi island_off avi abi VDD 0 pt_rxmix_i
XQ rfq_p rfq_n lqp lqn bqp bqn ib3 enm ofs0q ofs1q ofs2q ofs3q ofs4q ofs_signq island_off avq abq VDD 0 pt_rxmix_q
Cbi1 bip 0 1p
Cbi2 bin 0 1p
Cbq1 bqp 0 1p
Cbq2 bqn 0 1p
.save v(bip) v(bin) v(bqp) v(bqn) i(VDD)
.tran 10p {3.5 / fif} {1.5 / fif} 10p
.control
run
let vi=v(bip)-v(bin)
let vq=v(bqp)-v(bqn)
meas tran vipp pp vi from={1.5 / fif} to={3.5 / fif}
meas tran vqpp pp vq from={1.5 / fif} to={3.5 / fif}
meas tran idd avg i(VDD) from={1.5 / fif} to={3.5 / fif}
wrdata {{tag}}.dat vi vq
.endc
"""
    tag = f'chain_{mode}_{"m" if match else "u"}_{int(flo / 1e6)}_{view}_{_tag(corner)}'
    body = body.replace('{tag}', tag)
    log, m = run(work, tag + '.cir', body, corner, timeout=14400)
    ai = tone(work / f'{tag}.dat', fif, 1.5 / fif, 3.5 / fif, 1)
    aq = tone(work / f'{tag}.dat', fif, 1.5 / fif, 3.5 / fif, 2)
    g = lambda v: 20 * math.log10(v / amp) if v else None
    return dict(gain_i_db=g(ai), gain_q_db=g(aq), bb_pp_i_v=m.get('vipp'), bb_pp_q_v=m.get('vqpp'),
                idd_a=-m['idd'] if 'idd' in m else None,
                f_lo_hz=flo, f_if_hz=fif, rf_emf_amp_diff_v=amp, board_match=match,
                lo='ideal 0/VDD square, 50% duty, 20 ps edges, I/Q 90 deg')


# ---------------------------------------------------------------- disabled loading of switches
def off_capacitance(work, name, devices, f, vnode=1.65, vgate_off=0.0, vdd=3.3, include=None):
    """Capacitance seen at node `a` of an OFF switch (other side at AC ground), from an AC run."""
    inc = f'.include {include}' if include else ''
    body = f"""{inc}
VDD VDD 0 {vdd}
Va a 0 DC {vnode} AC 1
Vb b 0 {vnode}
Voff off 0 {vgate_off}
Vonb onb 0 {vdd}
{devices}
.control
ac lin 1 {f} {f}
let c=imag(-i(Va))/(2*pi*{f})
print c
.endc
"""
    log, m = run(work, f'coff_{name}.cir', body, ('typical', 27, vdd))
    return m.get('c')


def chain_bb_noise(work, view, corner=('typical', 27, 3.3), f=5e6):
    """Frozen-LO estimate of the mixer/TIA/DAC noise at the I baseband output (V/sqrt(Hz) at f).
    I switches lo_p on, Q switches lo_p on (one pair of each quad conducting), LNA active, source
    terminated in 100 ohm.  Ignores noise folding from LO harmonics (optimistic)."""
    c, t, vdd = corner
    nl, ni, nq = (netlist(work, b, view) for b in ('lna', 'rxmix_i', 'rxmix_q'))
    body = f""".include {nl}
.include {ni}
.include {nq}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib1 vib ib1 10u
Ib2 vib ib2 10u
Ib3 vib ib3 10u
{_ctl(['en', 'gain_lo', 'byp', 'island_off'], {'en'}, vdd)}
Venm enm 0 {vdd}
{_ofs(0, vdd, 'i')}
{_ofs(0, vdd, 'q')}
Vs s 0 DC 0 AC 1
Ep s_p 0 s 0 0.5
En s_n 0 s 0 -0.5
Rsp s_p rf_in_p 50
Rsn s_n rf_in_n 50
Cpp rf_in_p 0 0.5p
Cpn rf_in_n 0 0.5p
Vlip lip 0 {vdd}
Vlin lin 0 0
Vlqp lqp 0 {vdd}
Vlqn lqn 0 0
{_lna_trim(vdd)}
XL rf_in_p rf_in_n rfo_p rfo_n rfq_p rfq_n ib1 en gain_lo byp ct0 ct1 ct2 se rt island_off nb vdcm VDD 0 pt_lna
XI rfo_p rfo_n lip lin bip bin ib2 enm ofs0i ofs1i ofs2i ofs3i ofs4i ofs_signi island_off avi abi VDD 0 pt_rxmix_i
XQ rfq_p rfq_n lqp lqn bqp bqn ib3 enm ofs0q ofs1q ofs2q ofs3q ofs4q ofs_signq island_off avq abq VDD 0 pt_rxmix_q
.control
noise v(bip,bin) Vs lin 1 {f} {f}
setplot noise1
let sbb=onoise_spectrum
print sbb
.endc
"""
    log, m = run(work, f'chain_noise_{view}_{_tag(corner)}.cir', body, corner)
    return dict(bb_noise_v_rthz=m.get('sbb'), f_hz=f)


def chain_nf_estimate(f_lna_db, sbb, conv_gain_db, temp=27):
    """NF of LNA + mixer: F = F_lna + S_bb / (G_conv^2 4kT 100 ohm)."""
    k = 1.380649e-23 * (273.15 + temp) * 4 * 100
    fl = 10 ** (f_lna_db / 10)
    g = 10 ** (conv_gain_db / 20)
    return 10 * math.log10(fl + sbb ** 2 / (g ** 2 * k))


def tx_observe(work, view, corner=('typical', 27, 3.3), block='bbfilter_i', amp=0.2, f=2e6):
    """rf_tx_external_upconverter: DAC -> bbfilter (TX direction, obs_sel=11) -> bb_tap -> 10 pF pads.
    AC transfer tx_in -> pad and a transient tone of `amp` V peak differential at f."""
    c, t, vdd = corner
    nf_, nt = netlist(work, block, view), netlist(work, 'bb_tap', view)
    on = {'en', 'dir_tx', 'obs_sel0', 'obs_sel1'}
    body = f""".include {nf_}
.include {nt}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias 10u
Ib2 vib ibt 10u
Vap tx_in_p 0 DC 1.65 AC 0.5 SIN(1.65 {amp / 2} {f})
Van tx_in_n 0 DC 1.65 AC -0.5 SIN(1.65 {-amp / 2} {f})
Vbp rx_in_p 0 1.65
Vbn rx_in_n 0 1.65
{_ctl(CTRL_BBF, on, vdd)}
X1 {BBF_PINS} pt_{block}
Cl3 out_tx_p 0 0.3p
Cl4 out_tx_n 0 0.3p
Voe obs_en 0 {vdd}
Vie inj_en 0 0
X2 obs_p obs_n pad_p pad_n tinj_p tinj_n ibt obs_en inj_en island_off tnb VDD 0 pt_bb_tap
Rti1 tinj_p 0 1meg
Rti2 tinj_n 0 1meg
Cpp pad_p 0 10p
Cpn pad_n 0 10p
Rpp pad_p 0 100k
Rpn pad_n 0 100k
.control
op
let idd=-i(VDD)
let pcm=(v(pad_p)+v(pad_n))/2
print idd pcm
ac dec 40 10k 200Meg
let g=db(v(pad_p)-v(pad_n))
meas ac g_lf find g at=10k
meas ac f3db when g=(g_lf-3) fall=1
meas ac g_10m find g at=10Meg
tran 2n {4 / f} {2 / f}
let vo=v(pad_p)-v(pad_n)
wrdata txobs_{view}_{_tag(corner)}_{amp}.dat vo
.endc
"""
    log, m = run(work, f'txobs_{view}_{_tag(corner)}_{amp}.cir', body, corner)
    a = tone(work / f'txobs_{view}_{_tag(corner)}_{amp}.dat', f, 2 / f, 4 / f)
    a3 = tone(work / f'txobs_{view}_{_tag(corner)}_{amp}.dat', 3 * f, 2 / f, 4 / f)
    return dict(idd_a=m.get('idd'), pad_cm_v=m.get('pcm'), lf_gain_db=m.get('g_lf'), f3db_hz=m.get('f3db'),
                gain_10mhz_db=m.get('g_10m'), tone_gain_db=20 * math.log10(a / amp) if a else None,
                hd3_dbc=20 * math.log10(a3 / a) if a and a3 else None, amp_diff_peak_v=amp, f_hz=f,
                load='10 pF || 100 kohm per pad')


def rxmix_offset(work, view, corner=('typical', 27, 3.3), block='rxmix_i', ofs=0):
    """Differential DC offset at the TIA output with the LO running and no RF input."""
    c, t, vdd = corner
    nl = netlist(work, block, view)
    per = 1 / 2.4e9
    body = f""".include {nl}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias 10u
Ven en 0 {vdd}
Viso island_off 0 0
{_ofs(ofs, vdd)}
Rsp rp 0 300
Rsn rn 0 300
Ccp rp rf_p 4p
Ccn rn rf_n 4p
Vlp lo_p 0 PULSE(0 {vdd} 0 20p 20p {per / 2 - 20e-12} {per})
Vln lo_n 0 PULSE({vdd} 0 0 20p 20p {per / 2 - 20e-12} {per})
X1 rf_p rf_n lo_p lo_n bb_p bb_n ibias en ofs0 ofs1 ofs2 ofs3 ofs4 ofs_sign island_off atb_vcm atb_vbp VDD 0 pt_{block}
Cbp bb_p 0 1p
Cbn bb_n 0 1p
.save v(bb_p) v(bb_n)
.tran 10p 300n 150n 10p
.control
run
let vbb=v(bb_p)-v(bb_n)
meas tran voff avg vbb from=200n to=300n
.endc
"""
    log, m = run(work, f'{block}_off_{view}_{_tag(corner)}_{ofs}.cir', body, corner)
    return dict(offset_v=m.get('voff'), code=ofs)


def rxmix_calibrate(work, view, corner, block='rxmix_i', probe=8):
    """What the FPGA does: measure the offset at code 0 and code `probe`, pick the nearest code,
    report the residual at that code."""
    o0 = rxmix_offset(work, view, corner, block, 0)['offset_v']
    o1 = rxmix_offset(work, view, corner, block, probe)['offset_v']
    lsb = (o1 - o0) / probe
    code = max(-31, min(31, round(-o0 / lsb)))
    r = rxmix_offset(work, view, corner, block, code)['offset_v']
    return dict(raw_offset_v=o0, lsb_v=lsb, code=code, residual_v=r)


# ---------------------------------------------------------------- transient-noise chain NF
KT4 = 4 * 1.380649e-23 * 300.15
TN_NT = 9.7e-12          # trnoise sample interval (white to ~50 GHz: covers the LO harmonics)


def trnoise_calibration(work, nt=TN_NT, tstop=2e-6):
    """One-sided PSD per NA^2 of an ngspice trnoise source (measured, not assumed)."""
    body = f"""Vn n 0 dc 0 trnoise(1m {nt} 0 0)
R1 n 0 1meg
.tran {nt} {tstop}
.control
run
wrdata tncal.dat v(n)
.endc
"""
    run(work, 'tncal.cir', body, ('typical', 27, 3.3))
    rows = S.read_table(work / 'tncal.dat')
    psd = _psd([r[0] for r in rows], [r[1] for r in rows], 1e6, 20e6)
    return psd / 1e-6


def _psd(t, v, f1, f2, exclude=None):
    """Mean one-sided PSD of v(t) between f1 and f2 (non-uniform t: linear resample + periodogram)."""
    import numpy as np
    t, v = np.asarray(t), np.asarray(v)
    n = 2 ** int(np.floor(np.log2(len(t))))
    tu = np.linspace(t[0], t[-1], n)
    vu = np.interp(tu, t, v)
    vu = vu - vu.mean()
    dt = tu[1] - tu[0]
    w = np.hanning(n)
    spec = np.abs(np.fft.rfft(vu * w)) ** 2 * 2 * dt / (w ** 2).sum()
    f = np.fft.rfftfreq(n, dt)
    sel = (f >= f1) & (f <= f2)
    if exclude:
        sel &= np.abs(f - exclude) > 3 / (t[-1] - t[0])
    return float(spec[sel].mean())


def _inject_mixer_noise(text, sub, na_ota, na_rtia):
    """Add trnoise sources to the mixer subcircuit: OTA input-referred noise (series with the + input)
    and Rtia thermal noise (current across each feedback resistor)."""
    out, inside, k = [], False, 0
    for line in text.splitlines():
        tok = line.split()
        if tok and tok[0].lower() == '.subckt':
            inside = tok[1] == sub
        if inside and tok and tok[0].lower() == '.ends':
            # (trnoise current sources stall ngspice here; a VCCS driven by a trnoise voltage works)
            out += [f'Vnr1 ncr1 0 dc 0 trnoise({na_rtia * 1e6} {TN_NT} 0 0)', 'Gnr1 x_p bb_n ncr1 0 1e-6',
                    f'Vnr2 ncr2 0 dc 0 trnoise({na_rtia * 1e6} {TN_NT} 0 0)', 'Gnr2 x_n bb_p ncr2 0 1e-6']
            inside = False
        if inside and tok and tok[-1] == 'pt_rfrx_otan' and tok[1] == 'atb_vcm':
            k += 1
            out.append(f'Vnota{k} nrefa{k} atb_vcm dc 0 trnoise({na_ota} {TN_NT} 0 0)')
            out.append(f'Rnota{k} nrefa{k} nref{k} 10')
            line = line.replace(' atb_vcm ', f' nref{k} ', 1)
        out.append(line)
    if k != 2:
        raise ValueError(f'{sub}: expected 2 TIA OTAs, found {k}')
    return '\n'.join(out) + '\n'


def chain_tnoise(work, view, kcal, lna_nf_db, ota_en, mode='lna', match=None, corner=('typical', 27, 3.3),
                 amp=5e-4, fif=4e6, tstop=3.0e-6, tstart=1.0e-6):
    """Chain NF including noise folding: transient run with white trnoise sources for the source
    (2 x 50 ohm), the LNA (input-referred, from its AC noise figure), both TIA OTAs (input-referred
    ota_en) and the TIA resistors, with the real 2.4 GHz LO switching.  A small IF tone in the same
    run gives the conversion gain; NF = S_out / (G^2 * 4kT * 100 ohm)."""
    c, t, vdd = corner
    nl = netlist(work, 'lna', view)
    names = {}
    for b in ('rxmix_i', 'rxmix_q'):
        src = (HERE / f'{b}.spice') if view == 'sch' else (flow.GENERATED / f'{b}.ext.spice')
        txt = S.ngspice_netlist(src.read_text())
        na_r = math.sqrt(KT4 / 20e3 / kcal)
        if b == 'rxmix_i':   # NF is measured on I; Q-mixer noise reaches I only through the shared RF node
            txt = _inject_mixer_noise(txt, f'pt_{b}', ota_en / math.sqrt(kcal), na_r)
        names[b] = f'{b}_{view}_tn.spice'
        (work / names[b]).write_text(txt)
    na_src = math.sqrt(KT4 * 50 / kcal)
    f_lna = 10 ** (lna_nf_db / 10) if mode == 'lna' else 1.0
    na_lna = math.sqrt(max(f_lna - 1, 0) * KT4 * 50 / kcal)
    per = 1 / 2.4e9
    on = {'lna': {'en'}, 'bypass': {'byp'}}[mode]
    if match:
        src = 'Rsp a_p sp 50\nRsn a_n sn 50\n' + _match_net(match)
    else:
        src = 'Rsp a_p rf_in_p 50\nRsn a_n rf_in_n 50\n'
    lo = lambda name, inv, delay: (f"V{name} {name} 0 PULSE({0 if not inv else vdd} {vdd if not inv else 0} "
                                   f"{delay} 20p 20p {per / 2 - 20e-12} {per})")
    body = f""".include {nl}
.include {names['rxmix_i']}
.include {names['rxmix_q']}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib1 vib ib1 10u
Ib2 vib ib2 10u
Ib3 vib ib3 10u
{_ctl(['en', 'gain_lo', 'byp', 'island_off'], on, vdd)}
Venm enm 0 {vdd}
{_ofs(0, vdd, 'i')}
{_ofs(0, vdd, 'q')}
Vs s 0 DC 0 SIN(0 {amp} {2.4e9 + fif})
Ep s_p 0 s 0 0.5
En s_n 0 s 0 -0.5
Vnsp s_p n1p dc 0 trnoise({na_src} {TN_NT} 0 0)
Vnsn s_n n1n dc 0 trnoise({na_src} {TN_NT} 0 0)
Vnlp n1p a_p dc 0 trnoise({na_lna} {TN_NT} 0 0)
Vnln n1n a_n dc 0 trnoise({na_lna} {TN_NT} 0 0)
{src}Cpp rf_in_p 0 0.5p
Cpn rf_in_n 0 0.5p
* smooth square LO (tanh of a sine, ~20 ps edges): no PWL breakpoints to collide with trnoise samples
Blip lip 0 V={vdd / 2}+{vdd / 2}*tanh(8*sin(2*pi*2.4e9*time))
Blin lin 0 V={vdd / 2}-{vdd / 2}*tanh(8*sin(2*pi*2.4e9*time))
Blqp lqp 0 V={vdd / 2}-{vdd / 2}*tanh(8*cos(2*pi*2.4e9*time))
Blqn lqn 0 V={vdd / 2}+{vdd / 2}*tanh(8*cos(2*pi*2.4e9*time))
{_lna_trim(vdd)}
XL rf_in_p rf_in_n rfo_p rfo_n rfq_p rfq_n ib1 en gain_lo byp ct0 ct1 ct2 se rt island_off nb vdcm VDD 0 pt_lna
XI rfo_p rfo_n lip lin bip bin ib2 enm ofs0i ofs1i ofs2i ofs3i ofs4i ofs_signi island_off avi abi VDD 0 pt_rxmix_i
XQ rfq_p rfq_n lqp lqn bqp bqn ib3 enm ofs0q ofs1q ofs2q ofs3q ofs4q ofs_signq island_off avq abq VDD 0 pt_rxmix_q
Cbi1 bip 0 1p
Cbi2 bin 0 1p
Cbq1 bqp 0 1p
Cbq2 bqn 0 1p
.save v(bip) v(bin) v(bqp) v(bqn)
.tran {TN_NT} {tstop} {tstart} {TN_NT}
.control
run
let vi=v(bip)-v(bin)
let vq=v(bqp)-v(bqn)
wrdata {{tag}}.dat vi vq
.endc
"""
    tag = f'tnoise_{mode}_{"m" if match else "u"}_{view}_{_tag(corner)}'
    body = body.replace('{tag}', tag)
    run(work, tag + '.cir', body, corner, timeout=14400)
    import numpy as np
    rows = S.read_table(work / f'{tag}.dat')
    t = np.array([r[0] for r in rows])
    v = np.array([r[1] for r in rows])
    n = 2 ** int(np.floor(np.log2(len(t))))
    tu = np.linspace(t[0], t[-1], n)
    vu = np.interp(tu, t, v)
    # least-squares removal of offset, slow drift (start-up settling) and the IF tone; the tone
    # amplitude gives the conversion gain of this very run
    A = np.vstack([np.ones(n), tu, tu ** 2, np.sin(2 * np.pi * fif * tu), np.cos(2 * np.pi * fif * tu)]).T
    c = np.linalg.lstsq(A, vu, rcond=None)[0]
    r = vu - A @ c
    dt = tu[1] - tu[0]
    w = np.hanning(n)
    sp = np.abs(np.fft.rfft(r * w)) ** 2 * 2 * dt / (w ** 2).sum()
    f = np.fft.rfftfreq(n, dt)
    sel = (f >= 2e6) & (f <= 9e6) & (np.abs(f - fif) > 1e6)
    s_out = float(sp[sel].mean())
    g2 = (math.hypot(c[3], c[4]) / amp) ** 2
    res = dict(gain_i_db=10 * math.log10(g2), out_psd_i_v2_hz=s_out, bins=int(sel.sum()),
               nf_i_db=10 * math.log10(s_out / (g2 * KT4 * 100)),
               psd_by_band={f'{a / 1e6:g}-{b / 1e6:g}MHz': float(sp[(f >= a) & (f <= b) & (np.abs(f - fif) > 1e6)].mean())
                            for a, b in ((2e6, 3e6), (5e6, 7e6), (7e6, 9e6))})
    # the 2-3 MHz bins still carry start-up settling residue: the 5-9 MHz value is the cleaner one
    s59 = float(sp[(f >= 5e6) & (f <= 9e6)].mean())
    res['nf_i_5to9mhz_db'] = 10 * math.log10(s59 / (g2 * KT4 * 100))
    res.update(mode=mode, board_match=match, lna_nf_input_db=lna_nf_db if mode == 'lna' else None,
               ota_en_v_rthz=ota_en, band_hz=[2e6, 9e6], analysed_window_s=[tstart, tstop], trnoise_k=kcal, channel='I (Q mixer present, noiseless)',
               model='white trnoise sources: source 2x50 ohm, LNA input-referred (its AC NF), TIA OTA '
                     'input-referred, Rtia thermal; real LO switching folds them. Not modelled: switch Ron '
                     'noise, VCM/bias noise, flicker below the band, LNA noise correlation.')
    return res


def friis(nf_ext_db, g_ext_db, nf_chip_db):
    f1, g1, f2 = 10 ** (nf_ext_db / 10), 10 ** (g_ext_db / 10), 10 ** (nf_chip_db / 10)
    return 10 * math.log10(f1 + (f2 - 1) / g1)


def ota_input_noise(work, cell='pt_rfrx_otan', block='rxmix_i', f=5e6, corner=('typical', 27, 3.3)):
    """Open-loop input-referred noise (V/rtHz at f) of a mixer TIA OTA with the block's filtered bias."""
    c, t, vdd = corner
    nl = netlist(work, block, 'sch')
    body = f""".include {nl}
VDD VDD 0 {vdd}
Ib VDD ibias 10u
Ven en 0 {vdd}
Venb enb 0 0
Xb ibias en enb vbp VDD 0 pt_rfrx_bias
Rvf vbp vbpf 100k
Cvf vbpf VDD 2p
Vcm cm 0 1.65
Xo cm inn out vbpf enb VDD 0 {cell}
Lf out inn 1k
Cf inn 0 1
Vac in2 0 0 AC 1
Cin in2 inn 1
CL out 0 1p
RL out cm 20k
.control
noise v(out) Vac lin 1 {f} {f}
setplot noise1
let en=inoise_spectrum
print en
.endc
"""
    log, m = run(work, f'otanoise_{cell}_{_tag(corner)}.cir', body, corner)
    return m.get('en')
