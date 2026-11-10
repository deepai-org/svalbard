"""All rf_tx simulation benches -> generated/rf_tx-sim-results.json.

Views: 'ext' = Magic-extracted netlists with parasitic capacitance (the clean
evidence), 'sch' = source netlists (reference). Nominal point tt / 27 C / 3.3 V.
Corners (performance only): tt/ss/ff x 22/32 C x 3.15/3.35 V. Safety cases
cover 0..3.63 V and 0..85 C.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

import simulate as S

HERE = Path(__file__).resolve().parent
T = S.T_LO


# ----------------------------------------------------------------------------
# Block-level benches (one extracted DUT, ideal fixtures)
# ----------------------------------------------------------------------------
def mixer_deck(view, *, vin=0.3, sel=0, en=1, sat=0, vdd=3.3, out='w.txt', corner='tt', temp=27, rl=300.0):
    v = lambda b: vdd * b
    bb = vin if not sel else 0.0
    dac = vin if sel else 0.0
    return S.header(view, corner, temp) + f"""
VDD vdd 0 {vdd}
VLD vld 0 3.3
VSS VSS 0 0
VEN en 0 {v(en)}
VSEL sel 0 {v(sel)}
VSAT satm 0 {v(sat)}
IB 0 ib 10u
VBP bbp 0 {1.65 + bb / 2}
VBN bbn 0 {1.65 - bb / 2}
VDP dacp 0 {1.65 + dac / 2}
VDN dacn 0 {1.65 - dac / 2}
{S.lo_sources('lo', 0)}
RLP vld op {rl}
RLN vld on {rl}
CLP op 0 150f
CLN on 0 150f
X1 vdd VSS bbp bbn dacp dacn lop lon op on ib en sel satm atb_b atb_t pt_txmix_i
.control
tran 1p 6n 0 2p
wrdata {out} v(op)-v(on) i(VLD) i(VDD) i(VBP) i(VDP) v(atb_b) v(atb_t)
.endc
.end
"""


def mixer_metrics(work, name, vin, rl=300.0):
    t, y = S.load(work, name)
    t1 = 6e-9; t0 = t1 - 8 * T; m = t >= t0
    v = S.tone(t, y[:, 0], S.F_LO, t0, t1)
    i_fund = v / rl
    return dict(out_fund_mVpk_diff=round(1e3 * v, 3), out_current_fund_uApk=round(1e6 * i_fund, 2),
                conversion_transconductance_mS=round(1e3 * i_fund / vin, 4) if vin else None,
                tail_current_mA=round(-1e3 * float(np.mean(y[m, 1])), 4),
                logic_supply_uA=round(-1e6 * float(np.mean(y[m, 2])), 3),
                bb_source_uA=round(-1e6 * float(np.mean(y[m, 3])), 4), dac_source_uA=round(-1e6 * float(np.mean(y[m, 4])), 4),
                atb_bias_V=round(float(np.mean(y[m, 5])), 4), atb_tail_V=round(float(np.mean(y[m, 6])), 4))


def sum_deck(view, *, en=1, out='w.txt', irf=0.1e-3):
    v = 3.3 * en
    idc = '0.5m' if en else '0'
    irf = irf if en else 0.0
    return S.header(view) + f"""
VDD vdd 0 3.3
VSS VSS 0 0
VEN en 0 {v}
IDIP ip 0 DC {idc} SIN({idc} {irf} {S.F_LO} 0 0 0)
IDIN in 0 DC {idc} SIN({idc} {-irf} {S.F_LO} 0 0 0)
IDQP qp 0 DC {idc} SIN({idc} {irf} {S.F_LO} 0 0 90)
IDQN qn 0 DC {idc} SIN({idc} {-irf} {S.F_LO} 0 0 90)
COP op 0 150f
CON on 0 150f
X1 vdd VSS ip in qp qn op on en acm pt_txsum
.control
tran 1p 5n 0 2p
wrdata {out} v(op)-v(on) i(VDD) v(op) v(acm) v(ip)
.endc
.end
"""


def sum_ac_deck(view, out='w.txt'):
    return S.header(view) + f"""
VDD vdd 0 3.3
VSS VSS 0 0
VEN en 0 3.3
IDIP ip 0 DC 0.5m AC 1
IDIN in 0 DC 0.5m
IDQP qp 0 DC 0.5m
IDQN qn 0 DC 0.5m
COP op 0 150f
CON on 0 150f
X1 vdd VSS ip in qp qn op on en acm pt_txsum
.control
ac lin 1 {S.F_LO} {S.F_LO}
wrdata {out} vm(ip) vm(op)
.endc
.end
"""


def driver_deck(view, *, amp=0.15, cm=2.82, gain=15, mute=0, bypass=0, en=1, out='w.txt', corner='tt', temp=27,
                vdd=3.3, rs=0.0, match=None):
    v = lambda b: vdd * b
    g = [v((gain >> k) & 1) for k in range(4)]
    src = (f'VIP sp 0 SIN({cm} {amp / 2} {S.F_LO})\nVIN sn 0 SIN({cm} {-amp / 2} {S.F_LO})\n'
           f'RSP sp inp {max(rs, 1e-3)}\nRSN sn inn {max(rs, 1e-3)}\n')
    return S.header(view, corner, temp) + f"""
VDD vdd 0 {vdd}
VSS VSS 0 0
VEN en 0 {v(en)}
VMUTE mute 0 {v(mute)}
VBYP byp 0 {v(bypass)}
VG0 g0 0 {g[0]}
VG1 g1 0 {g[1]}
VG2 g2 0 {g[2]}
VG3 g3 0 {g[3]}
IB 0 ib 10u
{src}
X1 vdd VSS inp inn pad_p pad_n ib en mute byp g0 g1 g2 g3 ab ap ac pt_rfdriver
{S.pad_load(match=match, feed='vdd')}
.control
tran 1p 5n 0 2p
wrdata {out} v(lp)-v(ln) i(VDD) v(ab) v(ap) v(ac) v(inp)-v(inn)
.endc
.end
"""


def driver_metrics(work, name, amp):
    t, y = S.load(work, name)
    t1 = 5e-9; t0 = t1 - 8 * T; m = t >= t0
    p = S.tone(t, y[:, 0], S.F_LO, t0, t1)
    vi = S.tone(t, y[:, 5], S.F_LO, t0, t1)
    return dict(input_mVpk_diff=round(1e3 * vi, 3), pad_fund_mVpk_diff=round(1e3 * p, 3), pad_dBm_50ohm=round(S.dbm(p), 2),
                voltage_gain=round(p / vi, 4) if vi > 0 else None, supply_mA=round(-1e3 * float(np.mean(y[m, 1])), 4),
                atb_bias_V=round(float(np.mean(y[m, 2])), 4), atb_pre_V=round(float(np.mean(y[m, 3])), 4),
                atb_cm_V=round(float(np.mean(y[m, 4])), 4))


# ----------------------------------------------------------------------------
# Safety benches (whole family, extracted)
# ----------------------------------------------------------------------------
def safety_deck(view, *, vdd=3.3, temp=27, en=0, ctrl=0.0, mute=1, bypass=0, gain=12, sel=0, sat=0, ibias=10e-6,
                lo_on=True, out='w.txt', corner='tt', pad_drive=None, tstop=3e-9):
    """Reset/off and fault states. ctrl = core-domain control level (V) driving en/sel/mute/bypass/g."""
    c = lambda b: ctrl * b
    g = [c((gain >> k) & 1) for k in range(4)]
    lo = (S.lo_sources('loi', 0) + S.lo_sources('loq', T / 4)) if lo_on else (
        'Vloip loip 0 0\nVloin loin 0 3.3\nVloqp loqp 0 0\nVloqn loqn 0 3.3\n')
    pad = S.pad_load() if pad_drive is None else (
        f'RPADP pad_p padx_p 2\nRPADN pad_n padx_n 2\nRSRC padx_p pdrv 50\nRSRCN padx_n pdrv 50\nVPDP pdrv 0 {pad_drive}\n')
    return S.header(view, corner, temp) + f"""
VDMI vdd_mi 0 {vdd}
VDMQ vdd_mq 0 {vdd}
VDS vdd_s 0 {vdd}
VDD vdd_d 0 {vdd}
VSS VSS 0 0
VEN en 0 {c(en)}
VSEL sel 0 {c(sel)}
VSAT satc 0 {c(sat)}
VMUTE mute 0 {c(mute)}
VBYP byp 0 {c(bypass)}
VG0 g0 0 {g[0]}
VG1 g1 0 {g[1]}
VG2 g2 0 {g[2]}
VG3 g3 0 {g[3]}
IBMI 0 ib_mi {ibias}
IBMQ 0 ib_mq {ibias}
IBD 0 ib_d {ibias}
VBB bbcm 0 1.65
{lo}
XMI vdd_mi VSS bbcm bbcm bbcm bbcm loip loin ip in ib_mi en sel satc a1 a2 pt_txmix_i
XMQ vdd_mq VSS bbcm bbcm bbcm bbcm loqp loqn qp qn ib_mq en sel satc a3 a4 pt_txmix_q
XS vdd_s VSS ip in qp qn sp sn en a5 pt_txsum
XD vdd_d VSS sp sn pad_p pad_n ib_d en mute byp g0 g1 g2 g3 a6 a7 a8 pt_rfdriver
{pad}
.control
op
print i(VDMI) i(VDMQ) i(VDS) i(VDD) i(VBB){'' if pad_drive is not None else ' i(VFEED)'}
tran 2p {tstop} 0 4p
wrdata {out} i(VDMI) i(VDMQ) i(VDS) i(VDD) i(VBB) v(pad_p) v(sp) v(ib_d) {'i(VPDP)' if pad_drive is not None else 'v(pad_n) i(VFEED)'}
.endc
.end
"""


def safety_metrics(work, name, tstop=3e-9):
    t, y = S.load(work, name)
    m = t >= tstop - 6 * T  # integer number of LO periods: displacement currents average out
    r = {k: round(-1e6 * float(np.mean(y[m, i])), 4) for i, k in
         ((0, 'txmix_i_rail_uA'), (1, 'txmix_q_rail_uA'), (2, 'txsum_rail_uA'), (3, 'rfdriver_rail_uA'), (4, 'bb_dac_source_uA'))}
    r['rail_peak_abs_uA'] = round(1e6 * float(np.max(np.abs(y[:, 0:4].sum(axis=1)))), 3)
    r['pad_p_V'] = round(float(np.mean(y[m, 5])), 4)
    r['sum_p_V'] = round(float(np.mean(y[m, 6])), 4)
    r['ibias_pin_V'] = round(float(np.mean(y[m, 7])), 4)
    r['col8'] = float(np.mean(y[m, 8]))
    if y.shape[1] > 9:   # board feed present: report it and keep rfdriver_rail_uA chip-only
        feed = -1e6 * float(np.mean(y[m, 9]))
        r['board_feed_uA'] = round(feed, 4)
        r['rfdriver_rail_uA'] = round(r['rfdriver_rail_uA'] - feed, 4)
        r['rail_peak_abs_uA'] = round(1e6 * float(np.max(np.abs(y[:, 0:4].sum(axis=1) - y[:, 9]))), 3)
    # static (DC operating point, LO at its t=0 level) currents from the log
    import re
    log = (Path(work) / f'{name}.log').read_text()
    op = {k.lower(): float(v) for k, v in re.findall(r'^i\((\w+)\)\s*=\s*([-+0-9.eE]+)', log, re.M)}
    r['dc_op_uA'] = {lab: round(-1e6 * op.get(src, float('nan')), 4) for src, lab in
                     (('vdmi', 'txmix_i_rail'), ('vdmq', 'txmix_q_rail'), ('vds', 'txsum_rail'), ('vdd', 'rfdriver_rail'),
                      ('vbb', 'bb_dac_source'))}
    if 'vfeed' in op:
        r['dc_op_uA']['board_feed'] = round(-1e6 * op['vfeed'], 4)
        r['dc_op_uA']['rfdriver_rail'] = round(r['dc_op_uA']['rfdriver_rail'] + 1e6 * op['vfeed'], 4)
    return r


def ramp_deck(view, out='w.txt', en_level=0.0):
    """Island rail ramp 0 -> 3.63 V in 200 ns (brownout/power-up), controls at reset, LO static."""
    return S.header(view) + f"""
VR rail 0 PWL(0 0 200n 3.63 400n 3.63 600n 0)
VDMI vdd_mi rail 0
VDMQ vdd_mq rail 0
VDS vdd_s rail 0
VDD vdd_d rail 0
VSS VSS 0 0
VEN en 0 {en_level}
VZ zero 0 0
VMUTE mute 0 3.3
IBMI 0 ib_mi 10u
IBMQ 0 ib_mq 10u
IBD 0 ib_d 10u
VBB bbcm 0 1.65
Vloip loip 0 0
Vloin loin 0 3.3
Vloqp loqp 0 0
Vloqn loqn 0 3.3
XMI vdd_mi VSS bbcm bbcm bbcm bbcm loip loin ip in ib_mi en zero zero a1 a2 pt_txmix_i
XMQ vdd_mq VSS bbcm bbcm bbcm bbcm loqp loqn qp qn ib_mq en zero zero a3 a4 pt_txmix_q
XS vdd_s VSS ip in qp qn sp sn en a5 pt_txsum
XD vdd_d VSS sp sn pad_p pad_n ib_d en mute zero zero zero zero zero a6 a7 a8 pt_rfdriver
{S.pad_load()}
.control
tran 0.5n 600n 0 0.5n
wrdata {out} i(VDMI)+i(VDMQ)+i(VDS)+i(VDD) v(rail) i(VBB)
.endc
.end
"""


def cap_deck(view, block, node, dc, ctrl, out='w.txt'):
    """Small-signal capacitance looking into one DUT port (100 MHz AC probe)."""
    f = 100e6
    if block == 'txmix':
        fix = (f"VBP bbp 0 1.65\nVBN bbn 0 1.65\nVDP dacp 0 1.65\nVDN dacn 0 1.65\nVLP lop 0 0\nVLN lon 0 3.3\n"
               f"VLD vld 0 3.3\nRLP vld op 300\nRLN vld on 300\nIB 0 ib 10u\nVEN en 0 {ctrl['en']}\nVSEL sel 0 {ctrl['sel']}\n")
        dut = 'X1 vdd VSS bbp bbn dacp dacn lop lon op on ib en sel VSS ab at pt_txmix_i'
    else:
        fix = (f"VIP inp 0 2.8\nVIN inn 0 2.8\nIB 0 ib 10u\nVEN en 0 {ctrl['en']}\nVMUTE mute 0 {ctrl.get('mute', 0)}\n"
               f"VBYP byp 0 {ctrl.get('bypass', 0)}\nVG g 0 3.3\n" + S.pad_load(feed='vdd'))
        dut = 'X1 vdd VSS inp inn pad_p pad_n ib en mute byp g g g g ab ap ac pt_rfdriver'
    # replace the probed node's fixture source by a DC+AC source with a current sense
    lines = [l for l in fix.splitlines() if not l.split()[1:2] == [node] or l.startswith(('R', 'C'))]
    fix = '\n'.join(lines) + f"\nVPROBE {node} 0 DC {dc} AC 1\n"
    return S.header(view) + f"""
VDD vdd 0 3.3
VSS VSS 0 0
{fix}
{dut}
.control
ac lin 1 {f} {f}
let c = abs(imag(i(VPROBE)))/(2*pi*{f})
wrdata {out} c
.endc
.end
"""


# ----------------------------------------------------------------------------
AMAM_LEVELS = (0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.3)
LO_SKEW_PS = (0, 2, 5, 10, 20)


def build(view, match=None):
    decks, meta = {}, {}

    def add(name, text, kind, **info):
        decks[name] = text.replace('wrdata w.txt', f'wrdata {name}.txt')
        meta[name] = dict(kind=kind, **info)

    # txmix block
    for lab, kw in {'mix_sat': dict(vin=0.3, sat=1), 'mix_sat_1p0': dict(vin=1.0, sat=1), 'mix_bb_1p0': dict(vin=1.0),
                    'mix_bb_p': dict(vin=0.3), 'mix_bb_n': dict(vin=-0.3), 'mix_zero': dict(vin=0.0),
                    'mix_dac': dict(vin=0.3, sel=1), 'mix_off': dict(vin=0.3, en=0)}.items():
        add(lab, mixer_deck(view, **kw), 'mixer', vin=kw['vin'])
    # a separate deck: bb driven while dac selected (unselected-input isolation)
    d = mixer_deck(view, vin=0.0, sel=1).replace('VBP bbp 0 1.65', 'VBP bbp 0 1.8').replace('VBN bbn 0 1.65', 'VBN bbn 0 1.5')
    add('mix_unselected', d, 'mixer', vin=0.3)
    # txsum block
    add('sum_on', sum_deck(view), 'sum')
    add('sum_off', sum_deck(view, en=0), 'sum')
    add('sum_ac', sum_ac_deck(view), 'sum_ac')
    # rfdriver block
    for a in (0.05, 0.15, 0.3, 0.6):
        add(f'drv_a{int(a * 1000)}', driver_deck(view, amp=a), 'driver', amp=a)
    for code in (1, 2, 4, 8, 12):
        add(f'drv_code{code}', driver_deck(view, amp=0.3, gain=code), 'driver', amp=0.3)
    add('drv_mute', driver_deck(view, amp=0.3, mute=1), 'driver', amp=0.3)
    add('drv_bypass', driver_deck(view, amp=0.3, bypass=1), 'driver', amp=0.3)
    add('drv_bypass_en0', driver_deck(view, amp=0.3, bypass=1, en=0), 'driver', amp=0.3)
    add('drv_off', driver_deck(view, amp=0.3, en=0), 'driver', amp=0.3)
    # disabled / bypass loading (capacitance seen by shared nodes)
    for lab, args in {'cap_mix_bb_off': ('txmix', 'bbp', 1.65, dict(en=0, sel=0)),
                      'cap_mix_bb_on': ('txmix', 'bbp', 1.65, dict(en=3.3, sel=0)),
                      'cap_mix_bb_unselected': ('txmix', 'bbp', 1.65, dict(en=3.3, sel=3.3)),
                      'cap_mix_dac_off': ('txmix', 'dacp', 1.65, dict(en=0, sel=0)),
                      'cap_mix_dac_on': ('txmix', 'dacp', 1.65, dict(en=3.3, sel=3.3)),
                      'cap_drv_in_on': ('rfdriver', 'inp', 2.8, dict(en=3.3)),
                      'cap_drv_in_off': ('rfdriver', 'inp', 2.8, dict(en=0)),
                      'cap_drv_in_bypass': ('rfdriver', 'inp', 2.8, dict(en=0, bypass=3.3))}.items():
        add(lab, cap_deck(view, *args), 'cap')
    # full chain
    for lab, kw in {'chain_dc': dict(vin_i=0.3), 'chain_dcneg': dict(vin_i=-0.3), 'chain_zero': dict(vin_i=0.0),
                    'chain_large': dict(vin_i=0.7), 'chain_dac': dict(vin_i=0.3, sel_dac=1),
                    'chain_bypass': dict(vin_i=0.3, bypass=1), 'chain_bypass_large': dict(vin_i=0.7, bypass=1),
                    'chain_mute': dict(vin_i=0.3, mute=1), 'chain_code4': dict(vin_i=0.3, gain=4),
                    'chain_lo_low': dict(vin_i=0.3, lo_high=2.5)}.items():
        add(lab, S.chain_deck(view, out='w.txt', **kw), 'chain', tstop=8e-9)
    # stretch goal (non-gating): LO divided by 2 and 4, same chain, same 50 ohm load
    for div in (2, 4):
        f = S.F_LO / div
        add(f'stretch_lo_div{div}', S.chain_deck(view, vin_i=0.3, f_lo=f, tstop=4e-9 + 8 / f, out='w.txt'), 'chain',
            tstop=4e-9 + 8 / f, f_lo=f)
        add(f'stretch_lo_div{div}_large', S.chain_deck(view, vin_i=0.7, f_lo=f, tstop=4e-9 + 8 / f, out='w.txt'), 'chain',
            tstop=4e-9 + 8 / f, f_lo=f)
    fbb = S.F_LO / 40
    add('chain_ssb', S.chain_deck(view, vin_i=0.3, vin_q=0.3, fbb=fbb, tstop=5e-9 + 1 / fbb, out='w.txt'), 'chain_ssb',
        tstop=5e-9 + 1 / fbb, fbb=fbb)
    add('chain_ssb_dac', S.chain_deck(view, vin_i=0.3, vin_q=0.3, fbb=fbb, sel_dac=1, tstop=5e-9 + 1 / fbb, out='w.txt'),
        'chain_ssb', tstop=5e-9 + 1 / fbb, fbb=fbb)
    # board-matched load (external lossy L-match + ideal balun, designed once at tt from the measured
    # driver output admittance; the same board is used at every corner) and saturated mode
    m = match
    for lab, kw in {'match_lin_0p1': dict(vin_i=0.1), 'match_lin_0p3': dict(vin_i=0.3), 'match_lin_0p7': dict(vin_i=0.7),
                    'match_sat_0p3': dict(vin_i=0.3, sat=1), 'match_sat_1p0': dict(vin_i=1.0, sat=1),
                    'match_zero': dict(vin_i=0.0), 'match_sat_zero': dict(vin_i=0.0, sat=1),
                    'match_bypass_0p3': dict(vin_i=0.3, bypass=1), 'match_bypass_sat_1p0': dict(vin_i=1.0, bypass=1, sat=1),
                    'match_mute_sat': dict(vin_i=1.0, sat=1, mute=1),
                    'match_code4_sat': dict(vin_i=1.0, sat=1, gain=4), 'match_code8_sat': dict(vin_i=1.0, sat=1, gain=8),
                    'match_code1_sat': dict(vin_i=1.0, sat=1, gain=1)}.items():
        add(lab, S.chain_deck(view, match=m, out='w.txt', **kw), 'chain', tstop=8e-9)
    add('match_ssb_lin', S.chain_deck(view, vin_i=0.3, vin_q=0.3, fbb=fbb, match=m, tstop=5e-9 + 1 / fbb, out='w.txt'),
        'chain_ssb', tstop=5e-9 + 1 / fbb, fbb=fbb)
    add('match_ssb_sat', S.chain_deck(view, vin_i=1.0, vin_q=1.0, fbb=fbb, sat=1, match=m, tstop=5e-9 + 1 / fbb, out='w.txt'),
        'chain_ssb', tstop=5e-9 + 1 / fbb, fbb=fbb)
    # AM-AM / AM-PM of the whole chain into the board (baseband DC on I, CW at the LO), input to the
    # modulation model (tx_modulation.py): EVM, ACLR, mask with a 20 MHz HE20 OFDM stimulus
    for v in AMAM_LEVELS:
        add(f'amam_{int(round(v * 1000)):04d}', S.chain_deck(view, vin_i=v, match=m, tstop=8e-9, out='w.txt'), 'amam',
            tstop=8e-9, vin=v)
        add(f'amamsat_{int(round(v * 1000)):04d}', S.chain_deck(view, vin_i=v, match=m, sat=1, tstop=8e-9, out='w.txt'), 'amam',
            tstop=8e-9, vin=v, sat=1)
    # LO quadrature skew (Q LO delayed by extra ps): image rejection with an SSB tone, linear level
    for sk in LO_SKEW_PS:
        d = S.chain_deck(view, vin_i=0.3, vin_q=0.3, fbb=fbb, match=m, tstop=5e-9 + 1 / fbb, out='w.txt')
        d = d.replace(f"PULSE(0 3.3 {1 / S.F_LO / 4}", f"PULSE(0 3.3 {1 / S.F_LO / 4 + sk * 1e-12}").replace(
            f"PULSE(3.3 0 {1 / S.F_LO / 4}", f"PULSE(3.3 0 {1 / S.F_LO / 4 + sk * 1e-12}")
        add(f'skew_{sk}ps', d, 'chain_ssb', tstop=5e-9 + 1 / fbb, fbb=fbb, lo_q_skew_ps=sk)
    for a in (0.1, 0.3, 0.6):
        add(f'drv_match_a{int(a * 1000)}', driver_deck(view, amp=a, match=m), 'driver', amp=a)
    # corners (performance only)
    for corner in ('tt', 'ss', 'ff'):
        for temp in (22, 32):
            for vdd in (3.15, 3.35):
                lab = f'corner_{corner}_{temp}C_{vdd}V'.replace('.', 'p')
                add(lab, S.chain_deck(view, corner=corner, temp=temp, vdd=vdd, vin_i=0.3, out='w.txt'), 'chain',
                    tstop=8e-9, corner=corner, temp=temp, vdd=vdd)
                add('m' + lab, S.chain_deck(view, corner=corner, temp=temp, vdd=vdd, vin_i=0.3, match=m, out='w.txt'), 'chain',
                    tstop=8e-9, corner=corner, temp=temp, vdd=vdd)
                add('s' + lab, S.chain_deck(view, corner=corner, temp=temp, vdd=vdd, vin_i=1.0, sat=1, match=m, out='w.txt'),
                    'chain', tstop=8e-9, corner=corner, temp=temp, vdd=vdd)
    # safety
    safe = {
        'safe_reset_3p3': dict(), 'safe_reset_3p63_85C': dict(vdd=3.63, temp=85), 'safe_reset_3p63_0C': dict(vdd=3.63, temp=0),
        'safe_reset_ff_3p63_85C': dict(vdd=3.63, temp=85, corner='ff'),
        'safe_rail_off': dict(vdd=0.0), 'safe_rail_off_ctrl_high': dict(vdd=0.0, ctrl=3.3, en=1, mute=0, gain=15, sel=1, sat=1),
        'safe_rail_off_bypass': dict(vdd=0.0, ctrl=3.3, bypass=1),
        'safe_bypass_and_en': dict(ctrl=3.3, en=1, mute=0, bypass=1, gain=15),
        'safe_en_no_bias': dict(ctrl=3.3, en=1, mute=0, gain=15, ibias=0.0),
        'safe_en_lo_stopped': dict(ctrl=3.3, en=1, mute=0, gain=15, lo_on=False),
        'safe_en_3p63_85C': dict(vdd=3.63, temp=85, ctrl=3.63, en=1, mute=0, gain=15),
        'safe_pad_driven_rail_off': dict(vdd=0.0, pad_drive=3.3),
        'safe_pad_driven_reset': dict(pad_drive=3.3),
        'safe_peer_grounded_reset': dict(pad_drive=0.0),
        'safe_peer_grounded_rail_off': dict(vdd=0.0, pad_drive=0.0),
        'safe_peer_grounded_enabled': dict(pad_drive=0.0, ctrl=3.3, en=1, mute=0, gain=15),
        'safe_peer_grounded_bypass': dict(pad_drive=0.0, ctrl=3.3, en=1, bypass=1),
    }
    for lab, kw in safe.items():
        add(lab, safety_deck(view, **kw), 'safety', **{k: v for k, v in kw.items()})
    add('safe_ramp_reset', ramp_deck(view), 'ramp', en_level=0.0)
    add('safe_ramp_en_high', ramp_deck(view, en_level=3.3), 'ramp', en_level=3.3)
    return decks, meta


def evaluate(work, meta):
    out = {}
    for name, m in meta.items():
        try:
            k = m['kind']
            if k == 'mixer':
                r = mixer_metrics(work, name, m['vin'])
            elif k == 'sum':
                t, y = S.load(work, name); t1 = 5e-9; t0 = t1 - 8 * T; mm = t >= t0
                v = S.tone(t, y[:, 0], S.F_LO, t0, t1)
                isum = 2 * 0.1e-3 * np.sqrt(2)  # |I + jQ| differential current amplitude
                r = dict(out_fund_mVpk_diff=round(1e3 * v, 3), transimpedance_ohm=round(v / isum, 2),
                         supply_mA=round(-1e3 * float(np.mean(y[mm, 1])), 4), out_p_dc_V=round(float(np.mean(y[mm, 2])), 4),
                         atb_cm_V=round(float(np.mean(y[mm, 3])), 4), in_p_dc_V=round(float(np.mean(y[mm, 4])), 4))
            elif k == 'sum_ac':
                d = np.loadtxt(Path(work) / f'{name}.txt')
                r = dict(input_impedance_ohm_at_2p44GHz=round(float(d[1]), 2), transfer_ohm_at_2p44GHz=round(float(d[3]), 2))
            elif k == 'driver':
                r = driver_metrics(work, name, m['amp'])
            elif k == 'chain':
                r = S.chain_metrics(work, name, m['tstop'], f_lo=m.get('f_lo', S.F_LO))
            elif k == 'amam':
                t, y = S.load(work, name); t1 = m['tstop']; t0 = t1 - 8 / S.F_LO
                z = S.ctone(t, y[:, 0], S.F_LO, t0, t1)
                r = dict(vin=m['vin'], out_re=float(z.real), out_im=float(z.imag), pad_dBm_50ohm=round(S.dbm(abs(z)), 3),
                         h2_dBc=round(20 * np.log10(abs(S.ctone(t, y[:, 0], 2 * S.F_LO, t0, t1)) / abs(z) + 1e-15), 2),
                         h3_dBc=round(20 * np.log10(abs(S.ctone(t, y[:, 0], 3 * S.F_LO, t0, t1)) / abs(z) + 1e-15), 2),
                         pad_h2_dBc=round(20 * np.log10(abs(S.ctone(t, y[:, 13] - y[:, 15], 2 * S.F_LO, t0, t1)) /
                                                        abs(S.ctone(t, y[:, 13] - y[:, 15], S.F_LO, t0, t1)) + 1e-15), 2),
                         pad_h3_dBc=round(20 * np.log10(abs(S.ctone(t, y[:, 13] - y[:, 15], 3 * S.F_LO, t0, t1)) /
                                                        abs(S.ctone(t, y[:, 13] - y[:, 15], S.F_LO, t0, t1)) + 1e-15), 2),
                         supply_mA=round(-1e3 * float(np.mean(y[t >= t0, 6])), 3))
            elif k == 'chain_ssb':
                r = S.chain_metrics(work, name, m['tstop'], fbb=m['fbb'])
            elif k == 'safety':
                r = safety_metrics(work, name)
                if 'pad_drive' in m:
                    r['pad_source_current_mA'] = round(-1e3 * r.pop('col8'), 4)
                else:
                    r['pad_n_V'] = round(r.pop('col8'), 4)
            elif k == 'cap':
                d = np.atleast_1d(np.loadtxt(Path(work) / f'{name}.txt'))
                r = dict(capacitance_fF=round(1e15 * float(d[1]), 2))
            elif k == 'ramp':
                t, y = S.load(work, name)
                r = dict(rail_current_peak_uA=round(1e6 * float(np.max(np.abs(y[:, 0]))), 3),
                         rail_current_at_3p63V_uA=round(-1e6 * float(np.mean(y[(t > 250e-9) & (t < 400e-9), 0])), 3),
                         bb_source_peak_uA=round(1e6 * float(np.max(np.abs(y[:, 2]))), 3))
            out[name] = dict(meta=m, result=r)
        except Exception as e:  # keep going; failures are recorded, not hidden
            out[name] = dict(meta=m, error=str(e))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--view', default='ext', choices=['ext', 'sch'])
    ap.add_argument('--only', default=None, help='comma-separated deck name prefixes')
    a = ap.parse_args()
    zw = S.run_decks({'zout': S.zout_deck(a.view, out='zout.txt')}, f'zout_{a.view}')
    zd = np.loadtxt(zw / 'zout.txt')
    match = S.design_match(complex(zd[1], zd[3]))
    decks, meta = build(a.view, match)
    if a.only:
        keep = tuple(a.only.split(','))
        decks = {k: v for k, v in decks.items() if k.startswith(keep)}
        meta = {k: v for k, v in meta.items() if k in decks}
    t0 = time.time()
    work = S.run_decks(decks, f'benches_{a.view}')
    res = evaluate(work, meta)
    doc = dict(view=a.view, analog_image=S.ANALOG_IMAGE_REF, analog_image_id=S.ANALOG_IMAGE, models=S.MODELS,
               nominal='tt / 27 C / 3.3 V', lo_assumption='differential rail-to-rail CMOS square LO, 50% duty, 30 ps edges, 50 ohm source, 2.44 GHz',
               pad_assumption='2 ohm + 1 pF per leg (rftxpad allocation); unmatched benches: 100 nH bias-tee chokes to the island rail, DC-blocked 50 ohm differential load',
               board_match=dict(match, method='board DC feed to the rf_tx island rail through per-leg chokes (Q=30) that resonate the measured '
                                'differential pad susceptance (tt, code 15, driver biased by the feed); DC blocks; ideal '
                                '200:50 ohm balun followed by a 1.0 dB resistive pad for balun insertion loss; 50 ohm load. '
                                'All board-matched powers are after the balun loss.',
                                pad_admittance_S=[float(zd[1]), float(zd[3])]),
               runtime_s=round(time.time() - t0, 1), results=res)
    if not a.only:
        (HERE / 'generated' / f'rf_tx-sim-{a.view}.json').write_text(json.dumps(doc, indent=1) + '\n')
    print(json.dumps({k: v.get('result', v.get('error')) for k, v in res.items()}, indent=1))
