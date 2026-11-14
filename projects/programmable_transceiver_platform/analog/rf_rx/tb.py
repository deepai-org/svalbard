"""Testbenches for the RF receive family (schematic or extracted netlists).

Every function returns a dict of measured numbers (or raises).  `view` selects
the netlist: 'sch' = <block>.spice, 'ext' = generated/<block>.ext.spice
(Magic extraction with parasitic capacitance).  Corners are (mos, temp_C, vdd).
"""
import math
import os
import re
import threading
from pathlib import Path

import rfrx_flow as flow
import simlib as S

HERE = flow.HERE
CTRL_BBF = ['en', 'dir_tx', 'inj', 'rx_direct', 'byp_s1', 'byp_s23', 'obs_sel0', 'obs_sel1',
            'bw0', 'bw1', 'bw2', 'bw3', 'gain0', 'gain1', 'gain2', 'gain3', 'gain4', 'gain5', 'gainc0', 'gainc1',
            'qt0', 'qt1', 'island_off',
            # FD filter (fork S, bbf_fd.py): 4-bit Q-trim, fine cutoff trim, fine DCOC DAC
            'qt2', 'qt3', 'fc_fine0', 'fc_fine1', 'fc_fine2', *[f'dcf{k}' for k in range(8)], 'dcf_sign']
import bbf_fd as _bbf
import netlists as _nl
HIBP = ' hib' if _nl.OTAN_XTAIL else ''   # rxmix pin hib exists only with the switched extra TIA tail (netlists.OTAN_XTAIL)
BBF_PINS = ' '.join(_bbf.PORTS).replace(' VSS', ' 0')


SELFTEST_NETLIST = {}   # fork P: bench self-tests (bench_selftest.py) point view 'selftest' at a hand-built netlist


LNA_IND = 'nom'   # RC-16j tank spiral model variant (lna_spiral.py): nom | pess | lhi


def with_lna_ind(text, variant=None):
    """Insert the LNTA tank spiral model across tank_p/tank_n inside pt_lna (the layout core is LVS-checked
    without the spiral, which is a separate DRC-only cell, as for the QVCO)."""
    import lna_spiral
    v = variant or LNA_IND
    i = text.index('.subckt pt_lna '); e = text.index('.ends', i)
    return (text[:e] + f'Xlnaind_p VDD tank_p VSS {lna_spiral.NAMES[v]}\nXlnaind_n VDD tank_n VSS {lna_spiral.NAMES[v]}\n'
            + text[e:] + '\n' + lna_spiral.subckt(v))


def netlist(work, block, view):
    if view == 'selftest':
        return S.prepare(work, SELFTEST_NETLIST[block], f'{block}_selftest.spice')
    src = HERE / f'{block}.spice' if view == 'sch' else flow.GENERATED / f'{block}.ext.spice'
    if block == 'lna' and view in ('sch', 'ext'):
        work.mkdir(parents=True, exist_ok=True)
        t = with_lna_ind(src.read_text())
        dst = work / f'{block}_{view}_{LNA_IND}_ind.spice'
        tmp = dst.with_name(f'{dst.name}.{os.getpid()}.{threading.get_ident()}.tmp'); tmp.write_text(t); os.replace(tmp, dst)
        src = dst
    if view in ('extpr', 'extpp', 'extlo'):   # extracted + pad_rf_pair compact-pad delta + explicit gate resistance (model audit)
        work.mkdir(parents=True, exist_ok=True)
        # fork P, both ends of spec/design-assumptions.md: extpp = NF/gain-worst end (Rg 200 ohm/10 um, +25 % device C,
        # pad C +30 %); extlo = match/stability-worst end (Rg 60 ohm/10 um, no extra device C, pad C -20 %)
        rg = {'extpr': RG_PER_10UM, 'extpp': RG_PESS_PER_10UM, 'extlo': RG_LO_PER_10UM}[view]
        t = with_rg(with_pad_rf_pair(src.read_text(), block), rg)
        if block == 'lna':
            t = with_lna_ind(t, {'extpr': None, 'extpp': 'pess', 'extlo': 'lhi'}[view])
        if view == 'extpp':
            t = with_cgs_extra(t)
        if view in ('extpp', 'extlo') and block == 'lna':
            dc = PAD_PESS_EXTRA_F if view == 'extpp' else PAD_LO_EXTRA_F
            i = t.index('.subckt pt_lna '); e = t.index('.ends', i)
            t = t[:e] + f'Cpadpp_p rf_in_p VSS {dc:g}\nCpadpp_n rf_in_n VSS {dc:g}\n' + t[e:]
        src = work / f'{block}_{view}_src.spice'
        tmp = src.with_name(f'{src.name}.{os.getpid()}.{threading.get_ident()}.tmp')
        tmp.write_text(t)
        os.replace(tmp, src)     # atomic: parallel benches in one work dir must never read a half-written file
    return S.prepare(work, src, f'{block}_{view}.spice')


# pad_rf_pair (compact RF pad, republished): +42 fF (P) / +53 fF (N) per leg over the 0.5 pF/leg bench allowance.
PAD_RF_PAIR_DC_F = (42e-15, 53e-15)
# scratch/reviews/model-uncertainty-audit.md: models have rgatemod=0; add 150 ohm per 10 um of gate width.
RG_PER_10UM = 150.
# spec/design-assumptions.md pessimistic: Rg 200 ohm/10 um; RF_RX pad C +30 % of the 0.5 pF allowance
RG_PESS_PER_10UM, PAD_PESS_EXTRA_F = 200., 0.15e-12
RG_LO_PER_10UM, PAD_LO_EXTRA_F = 60., -0.10e-12     # low end: Rg 60 ohm/10 um, RF_RX pad C -20 %


def with_pad_rf_pair(text, block='lna'):
    i = text.index(f'.subckt pt_{block} '); e = text.index('.ends', i)
    return text[:e] + f'Cpadx_p rf_in_p VSS {PAD_RF_PAIR_DC_F[0]:g}\nCpadx_n rf_in_n VSS {PAD_RF_PAIR_DC_F[1]:g}\n' + text[e:]


def with_cgs_extra(text, frac=0.25, cox_ff_um2=4.5, cov_ff_um=0.2):
    """Fork P (design-assumptions '+25 % device C' / low fT end): add frac x (Cox*W*L + Cov*W) from each MOS
    gate (after with_rg: the internal gate node) to its source."""
    out, k = [], 0
    for line in text.replace('\n+', ' ').splitlines():
        out.append(line)
        m = re.match(r'^(X\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(nfet_03v3|pfet_03v3|nfet_06v0|pfet_06v0)\s+(.*)$', line)
        if m:
            w = float(re.search(r'\bw=([\d.]+)u', line).group(1)); l = float(re.search(r'\bl=([\d.]+)u', line).group(1)); k += 1
            out.append(f'Cgxx{k} {m.group(3)} {m.group(4)} {frac * (cox_ff_um2 * w * l + cov_ff_um * w) * 1e-15:.4g}')
    return '\n'.join(out) + '\n'


def with_rg(text, per10):
    out, k = [], 0
    for line in text.replace('\n+', ' ').splitlines():
        m = re.match(r'^(X\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(nfet_03v3|pfet_03v3|nfet_06v0|pfet_06v0)\s+(.*)$', line)
        if m:
            w = float(re.search(r'\bw=([\d.]+)u', line).group(1)); k += 1
            out.append(f'{m.group(1)} {m.group(2)} rgx{k} {m.group(4)} {m.group(5)} {m.group(6)} {m.group(7)}')
            out.append(f'Rgx{k} {m.group(3)} rgx{k} {per10 * w / 10:.3g}')
        else:
            out.append(line)
    return '\n'.join(out) + '\n'


PGA_GAIN_BITS = ('gain0', 'gain1', 'gain2', 'gain3', 'gain4', 'gain5', 'gainc0', 'gainc1')
PGA_UNITY = ('gain2',)    # PGA code for 0 dB (k = 4, coarse off): the register reset value
# Q-trim (RC-6): reset code 1 (qt0); the trim is set per part at bring-up. Benches that do not name a
# code use the per-process code from the extracted Q-trim study: tt/ss 1, ff 2 (ff peaks 6.4 dB at code 0).
QT_RESET = _bbf.QT_RESET    # FD filter (fork S): 4-bit Q-trim, reset code 6
QT_BY_PROC = {'typical': _bbf.QT_RESET, 'ss': _bbf.QT_RESET, 'ff': _bbf.QT_RESET}
# LNA package-tolerance controls (RC-8a/RC-9/RC-10, RC-16e): 4-bit C-trim ct0..ct3, reset code 7
# (mid-range; the board match is derived at code 7), se/rt off. Pre-LNA attenuator att0..att4 + gain_lo (fork P): reset 0.
LNA_CT_RESET = 7
LNA_CT_BITS = 4


def qt_bits(code):
    return tuple(b for k, b in enumerate(('qt0', 'qt1', 'qt2', 'qt3')) if (code >> k) & 1)


LNA_LOBIAS = False   # RC-16j: benches run the RX (full-bias) state unless set (per thread: set_lobias)
_TL = threading.local()


def set_lobias(v):
    _TL.lob = bool(v)


def lobias():
    return getattr(_TL, 'lob', LNA_LOBIAS)
# RC-16j tank-tune code per (view, process): chosen by the extracted chain NF sweep (tb.chain_det, scratch/rf-lna-p/v6;
# bring-up tunes on the measured baseband noise floor, which tracks the TIA noise gain).  LNA-only gain is NOT a valid
# tune metric (conversion gain is current-mode and flat in ct; static-LO tank impedance did not predict the optimum).
LNA_TANK_CT = {('extpr', 'typical'): 6, ('extpr', 'ss'): 6, ('extpr', 'ff'): 6, ('ext', 'typical'): 6,
               ('extpp', 'ss'): 8, ('extpp', 'typical'): 8, ('extpp', 'ff'): 8,
               ('extlo', 'typical'): 5, ('extlo', 'ss'): 5, ('extlo', 'ff'): 5}


def lna_tank_ct(view, corner):
    return LNA_TANK_CT.get((view, corner[0]), LNA_CT_RESET)


def _lna_trim(vdd, ct=LNA_CT_RESET, se=False, rt=False, att=0):
    # fork P2: also drives the rxmix hib pin = NOT lobias (extra TIA OTA tail on in RX, off in duplex)
    return '\n'.join([f'Vlob lobias 0 {vdd if lobias() else 0}', f'Vhib hib 0 {0 if lobias() else vdd}'] + [f'Vct{k} ct{k} 0 {vdd if (ct >> k) & 1 else 0}' for k in range(LNA_CT_BITS)] +
                     [f'Vatt{k} att{k} 0 {vdd if (att >> k) & 1 else 0}' for k in range(5)] +
                     [f'Vse se 0 {vdd if se else 0}', f'Vrt rt 0 {vdd if rt else 0}'])


def _ctl(names, on, vdd):
    """Benches that enable the filter without naming a PGA code run it at 0 dB (k = 4): a PGA
    code of all zeros mutes stage 1 (no input conductance)."""
    on = set(on)
    if 'gain2' in names and 'en' in on and not on & set(PGA_GAIN_BITS):
        on |= set(PGA_UNITY)
    if 'qt0' in names and 'qtx' not in on and not on & {'qt0', 'qt1', 'qt2', 'qt3'}:
        on |= set(qt_bits(QT_RESET))
    if 'fc_fine0' in names and 'en' in on and not on & {'bw0', 'bw1', 'bw2', 'bw3', 'fc_fine0', 'fc_fine1', 'fc_fine2', 'bwx'}:
        on.add('bw0')     # FD filter reset cap code 8 (bw0): ~11 MHz, the Wi-Fi 20 MHz class corner
    on.discard('qtx')     # 'qtx' = explicit qt code 0
    on.discard('bwx')     # 'bwx' = explicit cap code 0 (widest)
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


def tone_complex(path, f, t0, t1, col=1):
    """Complex amplitude (same DFT as tone) of the f component of column `col`."""
    rows = [r for r in S.read_table(path) if t0 <= r[0] <= t1]
    re_ = im = 0.
    w = 2 * math.pi * f
    for a, b in zip(rows, rows[1:]):
        dt = b[0] - a[0]
        va, vb = a[2 * col - 1], b[2 * col - 1]
        re_ += .5 * dt * (va * math.cos(w * a[0]) + vb * math.cos(w * b[0]))
        im += .5 * dt * (va * math.sin(w * a[0]) + vb * math.sin(w * b[0]))
    return complex(re_, -im) * 2 / (t1 - t0)


# ---------------------------------------------------------------- LNA
# RC-16i (inductively degenerated LNA): each CS source has its own pad, downbonded to board ground; the bond
# (+ board trace) is the degeneration inductor Ls per leg.  LNA_LS_BOND_DL shifts it (bond tolerance benches).
LNA_LS, LNA_LS_Q = 0.5e-9, 20.   # LEGACY bonded source return (fork P2).  Not buildable on the COB (RFR-12); kept for comparison runs
def src_bond(ls=None, q=None, csrc=0., gnd='0'):
    """Legacy / comparison: bonded source return ls per leg (series R = w L / q at 2.44 GHz) and source-pad capacitance csrc."""
    ls = LNA_LS if ls is None else ls; q = LNA_LS_Q if q is None else q
    r = 2 * math.pi * 2.44e9 * ls / q
    s = f'Lsbp srcp_b sbq_p {ls:.4g}\nRsbp sbq_p {gnd} {r:.4g}\nLsbn srcn_b sbq_n {ls:.4g}\nRsbn sbq_n {gnd} {r:.4g}'
    if csrc:
        s += f'\nCsbp srcp_b {gnd} {csrc:.4g}\nCsbn srcn_b {gnd} {csrc:.4g}'
    return s


SRC_BOND = None      # scratch override: a deck fragment used instead of the on-chip degeneration (old scripts set this)
LNA_DEG_VIEW = {'extpp': 'pess', 'extlo': 'lhi'}     # degeneration-spiral model variant per view (others: nominal)


def src_net(view=None, gnd='0', variant=None):
    """Source network of the LNA: ON-CHIP degeneration spirals (lna_spiral.G_DEG) from src_p / src_n to the LNA's own VSS
    (`gnd`).  No bond wire or pad is in the degeneration path (coordinator decision 2026-11-13, RFR-12)."""
    if SRC_BOND is not None:
        return SRC_BOND.replace('{gnd}', gnd)
    import lna_spiral
    v = variant or LNA_DEG_VIEW.get(view, 'nom')
    n = lna_spiral.DEG_NAMES[v]
    return f'Xdegp srcp_b {gnd} {gnd} {n}\nXdegn srcn_b {gnd} {gnd} {n}\n' + lna_spiral.subckt_deg(v)


def _mixer_model(noiseless=False):
    """Passive-mixer input approximation: 50 ohm per leg to an AC ground at VCM.  noiseless=True (fork P):
    the same conductance as a self-controlled VCCS, which carries no thermal noise (isolates LNA-generated noise)."""
    legs = (('mp', 'rf_out_p'), ('mn', 'rf_out_n'), ('mqp', 'rf_outq_p'), ('mqn', 'rf_outq_n'))
    if noiseless:
        return '\n'.join(f'G{n} {a} vm {a} vm 0.02' for n, a in legs)
    return '\n'.join(f'R{n} {a} vm 50' for n, a in legs)


def lna_ac(work, view, corner=('typical', 27, 3.3), mode='active', f=2.4e9, match=None, ct=LNA_CT_RESET, se=False, rt=False, att=0,
           noiseless_load=False):
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
{_mixer_model(noiseless_load)}
Vm vm 0 1.65
{_lna_trim(vdd, ct, se, rt, att)}
X1 rf_in_p rf_in_n rf_out_p rf_out_n rf_outq_p rf_outq_n ibias en gain_lo byp ct0 ct1 ct2 se rt island_off atb_nbias atb_vdcm VDD 0 ct3 att0 att1 att2 att3 att4 srcp_b srcn_b tkp_b tkn_b lobias pt_lna
{src_net(view)}
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
    trim = '' if (ct, se, rt, att) == (LNA_CT_RESET, False, False, 0) else f'ct{ct}{"se" if se else ""}{"rt" if rt else ""}{f"a{att}" if att else ""}_'
    trim += 'nl_' if noiseless_load else ''
    log, m = run(work, f'lna_{trim}{mode}_{int(f / 1e6)}_{"m" if match else "u"}_{view}_{_tag(corner)}.cir', body, corner)
    return dict(idd_a=m.get('idd'), gain_db=m.get('gv'), zin_re_ohm=m.get('zr'), zin_im_ohm=m.get('zi'),
                nf_db=m.get('nf'), vd_cm_v=m.get('vdcm'))


def lna_band(work, view, corner, match, ct=LNA_CT_RESET, att=0, gain_lo=False, rt=False,
             f1=2.390e9, f2=2.4935e9, step=0.5e6):
    """Fork P: S11 / gain / NF across the band in one deck (board network `match`, any order) on a uniform
    grid f1..f2 with `step` (default 0.5 MHz: 2.395 / 2.400 / 2.4835 / 2.4885 GHz are grid points; the rows
    are checked against the requested grid).  Returns rows [{f, s11_db, gain_db, nf_db, zin}] and the current."""
    c, t, vdd = corner
    nl = netlist(work, 'lna', view)
    n = int(round((f2 - f1) / step)) + 1
    freqs = (f1, f1 + (n - 1) * step)
    body = f""".include {nl}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias 10u
{_ctl(['en', 'gain_lo', 'byp', 'island_off'], {'en'} | ({'gain_lo'} if gain_lo else set()), vdd)}
Vs s 0 DC 0 AC 1
Ep e_p 0 s 0 0.5
En e_n 0 s 0 -0.5
Rsp e_p sp 50
Rsn e_n sn 50
{_match_net(match)}Cpp rf_in_p 0 0.5p
Cpn rf_in_n 0 0.5p
{_mixer_model(True)}
Vm vm 0 1.65
{_lna_trim(vdd, ct, False, rt, att)}
X1 rf_in_p rf_in_n rf_out_p rf_out_n rf_outq_p rf_outq_n ibias en gain_lo byp ct0 ct1 ct2 se rt island_off atb_nbias atb_vdcm VDD 0 ct3 att0 att1 att2 att3 att4 srcp_b srcn_b tkp_b tkn_b lobias pt_lna
{src_net(view)}
.control
op
let idd=-i(VDD)
print idd
ac lin {n} {freqs[0]} {freqs[-1]}
let zin=(v(sp)-v(sn))/(v(e_p)-v(e_n)-v(sp)+v(sn))*100
let s11=db((zin-100)/(zin+100))
let gv=db(v(rf_out_p)-v(rf_out_n))
wrdata lnaband_{{tag}}_ac.txt s11 gv real(zin) imag(zin)
noise v(rf_out_p,rf_out_n) Vs lin {n} {freqs[0]} {freqs[-1]}
setplot noise1
let nf=10*log10(inoise_spectrum^2/(4*1.380649e-23*{273.15 + t}*100))
wrdata lnaband_{{tag}}_nf.txt nf
.endc
"""
    import hashlib
    tag = f'{view}_{_tag(corner)}_ct{ct}_a{att}{"g" if gain_lo else ""}{"r" if rt else ""}_{hashlib.md5(str(match).encode()).hexdigest()[:8]}'
    body = body.replace('{tag}', tag)
    log, m = run(work, f'lnaband_{tag}.cir', body, corner)
    a = S.read_table(work / f'lnaband_{tag}_ac.txt'); q = S.read_table(work / f'lnaband_{tag}_nf.txt')
    rows = [dict(f=r[0], s11_db=r[1], gain_db=r[3], zin=[r[5], r[7]], nf_db=w[1]) for r, w in zip(a, q)]
    want = [f1 + k * step for k in range(n)]
    assert len(rows) == n and all(abs(r['f'] - x) < 1e3 for r, x in zip(rows, want)), 'lna_band: grid mismatch'
    return dict(idd_a=m.get('idd'), rows=rows)


def lna_compression(work, view, corner, match, p_dbm, att=0, gain_lo=False, ct=LNA_CT_RESET, f=2.442e9, back=30., rt=False):
    """Fork P: large-signal gain (LNA alone, board network `match`, mixer model 50 ohm/leg) at a CW input of
    p_dbm (available from the 100 ohm source) relative to the same point `back` dB lower.  Returns the gain
    compression (dB, positive = compressed) and the output amplitude."""
    c, t, vdd = corner
    nl = netlist(work, 'lna', view)
    per = 1 / f
    t1 = 60 * per; t0 = t1 - 40 * per
    def one(pw, tag):
        a = math.sqrt(8 * 100 * 1e-3 * 10 ** (pw / 10))   # EMF peak, differential
        body = f""".include {nl}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias 10u
{_ctl(['en', 'gain_lo', 'byp', 'island_off'], {'en'} | ({'gain_lo'} if gain_lo else set()), vdd)}
Vs s 0 DC 0 SIN(0 {a} {f})
Ep e_p 0 s 0 0.5
En e_n 0 s 0 -0.5
Rsp e_p sp 50
Rsn e_n sn 50
{_match_net(match)}Cpp rf_in_p 0 0.5p
Cpn rf_in_n 0 0.5p
Rmp rf_out_p vm 50
Rmn rf_out_n vm 50
Rmqp rf_outq_p vm 50
Rmqn rf_outq_n vm 50
Vm vm 0 1.65
{_lna_trim(vdd, ct, False, rt, att)}
X1 rf_in_p rf_in_n rf_out_p rf_out_n rf_outq_p rf_outq_n ibias en gain_lo byp ct0 ct1 ct2 se rt island_off atb_nbias atb_vdcm VDD 0 ct3 att0 att1 att2 att3 att4 srcp_b srcn_b tkp_b tkn_b lobias pt_lna
{src_net(view)}
.tran {per / 40:.4g} {t1:.6g} 0 {per / 40:.4g}
.control
run
let vo=v(rf_out_p)-v(rf_out_n)
let vg=v(x1.g_p)-v(x1.g_n)
wrdata {tag}.dat vo vg
.endc
"""
        run(work, f'{tag}.cir', body, corner)
        return a, tone(Path(work) / f'{tag}.dat', f, t0, t1, 1), tone(Path(work) / f'{tag}.dat', f, t0, t1, 2)
    tag = f'lnacmp_{view}_{_tag(corner)}_a{att}{"g" if gain_lo else ""}{"r" if rt else ""}_{int(round(p_dbm))}'
    try:
        a1, o1, g1 = one(p_dbm, tag + '_hi')
        a0, o0, g0 = one(p_dbm - back, tag + '_lo')
    except Exception as e:   # the extracted netlist does not expose x1.g_p: retry without the gate probe
        return dict(error=str(e)[:300])
    comp = 20 * math.log10((o0 / a0) / (o1 / a1))
    return dict(p_dbm=p_dbm, att=att, gain_lo=gain_lo, compression_db=round(comp, 3),
                gain_small_db=round(20 * math.log10(o0 / a0), 2), out_amp_v=o1, gate_amp_v=g1)


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
Vct3 ct3 0 {vctl}
Vat0 att0 0 {vctl}
Vat1 att1 0 {vctl}
Vat2 att2 0 {vctl}
Vat3 att3 0 {vctl}
Vat4 att4 0 {vctl}
Vlob lobias 0 {vctl}
Vse se 0 {vctl}
Vrt rt 0 {vctl}
Vrp rf_in_p 0 {vctl}
Vrn rf_in_n 0 0
X1 rf_in_p rf_in_n rf_out_p rf_out_n rf_outq_p rf_outq_n ibias en gain_lo byp ct0 ct1 ct2 se rt island_off atb_nbias atb_vdcm VDD 0 ct3 att0 att1 att2 att3 att4 srcp_b srcn_b tkp_b tkn_b lobias pt_lna
{src_net(view)}
.option abstol=1e-15 reltol=1e-6 vntol=1e-9 itl1=500
.control
op
let ipad=abs(i(Vrp))+abs(i(Vrn))
let ictl=abs(i(Ven))+abs(i(Vgl))+abs(i(Vby))+abs(i(Viso))+abs(i(Vct0))+abs(i(Vct1))+abs(i(Vct2))+abs(i(Vct3))+abs(i(Vat0))+abs(i(Vat1))+abs(i(Vat2))+abs(i(Vat3))+abs(i(Vat4))+abs(i(Vlob))+abs(i(Vse))+abs(i(Vrt))
let irail=abs(i(VDD))
print ipad ictl irail
.endc
"""
    log, m = run(work, f'lna_unpowered_{view}_{temp}.cir', body, ('typical', temp, 0))
    return dict(pad_current_a=m.get('ipad'), control_current_a=m.get('ictl'), rail_current_a=m.get('irail'))


# ---------------------------------------------------------------- mixer
def rxmix_tran(work, view, corner=('typical', 27, 3.3), block='rxmix_i', amp=0.01, fif=5e6, ofs=0, hib=True, lo=None):
    """hib = True: RX state (extra TIA OTA tail on); False: duplex state (rxmix pin hib = 0)."""
    c, t, vdd = corner
    hs = ('' if hib else '_hib0') + lo_tag(lo)
    nl = netlist(work, block, view)
    flo = 2.4e9
    per = 1 / flo
    old_square = (f'Vlp lo_p 0 PULSE(0 {vdd} 0 20p 20p {per / 2 - 20e-12} {per})\n'
                  f'Vln lo_n 0 PULSE({vdd} 0 0 20p 20p {per / 2 - 20e-12} {per})')
    body = f""".include {nl}
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib vib ibias 10u
Ven en 0 {vdd}
Viso island_off 0 0
Vhib hib 0 {vdd if hib else 0}
* RF: differential tone at LO+IF, 300 ohm per leg (LNA output resistance class), AC-coupled
Vs s 0 DC 0 SIN(0 {amp} {flo + fif})
Ep sp 0 s 0 0.5
En sn 0 s 0 -0.5
Rsp sp rp 300
Rsn sn rn 300
Ccp rp rf_p 4p
Ccn rn rf_n 4p
{(old_square if not lo else lo_sources(lo, vdd, flo, ('lo_p', 'lo_n', 'lo_qx', 'lo_qy')))}
{_ofs(ofs, vdd)}
X1 rf_p rf_n lo_p lo_n bb_p bb_n ibias en ofs0 ofs1 ofs2 ofs3 ofs4 ofs_sign island_off atb_vcm atb_vbp{HIBP} VDD 0 pt_{block}
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
wrdata {block}_tran_{view}_{_tag(corner)}_{ofs}{hs}.dat vbb
.endc
"""
    log, m = run(work, f'{block}_tran_{view}_{_tag(corner)}_{ofs}{hs}.cir', body, corner, timeout=7200)
    a = tone(work / f'{block}_tran_{view}_{_tag(corner)}_{ofs}{hs}.dat', fif, 1.5 / fif, 3.5 / fif)
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
Vhib hib 0 {vdd if vdd > 0 else 3.63}
Vlp lo_p 0 {lo}
Vln lo_n 0 0
* rf_p/n sit behind the LNA's MIM output caps (no DC source): weak ties to ground only
Vrp rfr 0 0
Rrp rf_p rfr 10meg
Rrn rf_n rfr 10meg
{_ofs(ofs, vdd)}
X1 rf_p rf_n lo_p lo_n bb_p bb_n ibias en ofs0 ofs1 ofs2 ofs3 ofs4 ofs_sign island_off atb_vcm atb_vbp{HIBP} VDD 0 pt_{block}
{'' if vbb is None else f'Vbbp bb_p 0 {vbb + 0.2}' + chr(10) + f'Vbbn bb_n 0 {vbb - 0.2}'}
.option abstol=1e-15 reltol=1e-6 vntol=1e-9 itl1=500
.control
op
let irail=abs(i(VDD))
let irf=abs(i(Vrp))
{'' if vbb is None else 'let ibb=abs(i(Vbbp))+abs(i(Vbbn))' + chr(10) + 'print ibb'}
let ictl=abs(i(Ven))+abs(i(Viso))+abs(i(Vlp))+abs(i(Vhib))
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


def _ladder_net(m):
    """Board ladder (fork P, lna_match.py): m['net'] = [(kind, value), ...] from the pad toward the source;
    kind sL/sC = per-leg series element, pC/pL = element across the pair, pT = trimmer capacitor across the pair.
    The first sL includes the bond wire (m['lb'], drawn separately so its tolerance can be applied:
    m['lb_actual']).  m['lossy'] = True adds the pessimistic part losses of lna_match (L Q 20, C Q 100, bond Q 50,
    trimmer Q 50 + 0.4 nH ESL + 0.1 pF per terminal), evaluated at m.get('f_q', 2.44e9)."""
    import lna_match as LM
    lb, lba = m.get('lb', LM.BOND), m.get('lb_actual', m.get('lb', LM.BOND))
    lossy, w = m.get('lossy', False), 2 * math.pi * m.get('f_q', 2.44e9)
    rs = lambda l, q: f' {w * l / q:.4g}' if lossy else ''
    s, cur = '', {'p': 'rf_in_p', 'n': 'rf_in_n'}
    for i, (t, v) in enumerate(m['net']):
        if t in ('sL', 'sC'):
            for sd in 'pn':
                nxt = f'bl{i}_{sd}'
                if i == 0 and t == 'sL':
                    lx = max(v - lb, 1e-13)
                    s += f'Lbw{sd} {cur[sd]} bq{sd}a {lba}\nRbw{sd} bq{sd}a bq{sd} {w * lba / LM.Q_BOND if lossy else 1e-6:.4g}\n'
                    s += f'Lbx{i}{sd} bq{sd} bx{i}{sd} {lx}\nRbx{i}{sd} bx{i}{sd} {nxt} {w * lx / LM.Q_L if lossy else 1e-6:.4g}\n'
                elif t == 'sL':
                    s += f'Lbx{i}{sd} {cur[sd]} bx{i}{sd} {v}\nRbx{i}{sd} bx{i}{sd} {nxt} {w * v / LM.Q_L if lossy else 1e-6:.4g}\n'
                else:
                    s += f'Cbx{i}{sd} {cur[sd]} {nxt} {v}\n'
                cur[sd] = nxt
        elif t == 'pT':
            a, b = cur['p'], cur['n']
            s += (f'Cbt{i} {a} bt{i}x {v}\nRbt{i} bt{i}x bt{i}y {1 / (w * v * LM.Q_T) if lossy else 1e-6:.4g}\n'
                  f'Lbt{i} bt{i}y {b} {LM.ESL_T if lossy else 1e-15}\n')
            if lossy:
                s += f'Cbtp{i} {a} 0 {LM.CTERM_T}\nCbtn{i} {b} 0 {LM.CTERM_T}\n'
        elif t == 'pC':
            s += f'Cbx{i}d {cur["p"]} {cur["n"]} {v}\n'
            if lossy:
                s += f'Rbx{i}d {cur["p"]} {cur["n"]} {LM.Q_C / (w * v):.4g}\n'
        else:
            s += f'Lbx{i}d {cur["p"]} {cur["n"]} {v}\n'
    return s + f'Rbjp sp {cur["p"]} 1m\nRbjn sn {cur["n"]} 1m\n'


def _match_net(m):
    if m.get('order') == 'ladder':
        return _ladder_net(m)
    el = lambda kind, name, a, b, v: f"{'L' if kind == 'L' else 'C'}{name} {a} {b} {v}\n"
    (sk, sv), (pk, pv) = m['series_leg'], m['shunt_diff']
    if m['order'] == 'series_at_pad':
        return (el(sk, 'mp', 'sp', 'rf_in_p', sv) + el(sk, 'mn', 'sn', 'rf_in_n', sv) +
                el(pk, 'mx', 'sp', 'sn', pv))
    return (el(sk, 'mp', 'sp', 'rf_in_p', sv) + el(sk, 'mn', 'sn', 'rf_in_n', sv) +
            el(pk, 'mx', 'rf_in_p', 'rf_in_n', pv))


def chain_tran(work, view, corner=('typical', 27, 3.3), mode='lna', amp=3e-3, fif=5e6, flo=2.4e9, match=None,
               ofs=0, ofs_q=0):
    ct, rt = (match or {}).get('ct', LNA_CT_RESET), bool((match or {}).get('rt', False))   # RC-16h board trim state
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
{_lna_trim(vdd, ct, False, rt)}
XL rf_in_p rf_in_n rfo_p rfo_n rfq_p rfq_n ib1 en gain_lo byp ct0 ct1 ct2 se rt island_off nb vdcm VDD 0 ct3 att0 att1 att2 att3 att4 srcp_b srcn_b tkp_b tkn_b lobias pt_lna
{src_net(view)}
{_ofs(ofs, vdd, 'i')}
{_ofs(ofs_q, vdd, 'q')}
XI rfo_p rfo_n lip lin bip bin ib2 enm ofs0i ofs1i ofs2i ofs3i ofs4i ofs_signi island_off avi abi{HIBP} VDD 0 pt_rxmix_i
XQ rfq_p rfq_n lqp lqn bqp bqn ib3 enm ofs0q ofs1q ofs2q ofs3q ofs4q ofs_signq island_off avq abq{HIBP} VDD 0 pt_rxmix_q
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
    iq = {}
    if ai and aq:   # I/Q balance from the same transient: complex tone fit, image rejection of the uncorrected pair
        ci = tone_complex(work / f'{tag}.dat', fif, 1.5 / fif, 3.5 / fif, 1); cq = tone_complex(work / f'{tag}.dat', fif, 1.5 / fif, 3.5 / fif, 2)
        r = cq / ci
        ph = math.degrees(math.atan2(r.imag, r.real))
        perr = abs(ph) - 90.
        gr = abs(r); cs = math.cos(math.radians(perr))
        iq = dict(iq_gain_mismatch_db=20 * math.log10(gr), iq_phase_error_deg=perr,
                  irr_db=10 * math.log10((1 + 2 * gr * cs + gr * gr) / (1 - 2 * gr * cs + gr * gr)))
    return dict(gain_i_db=g(ai), gain_q_db=g(aq), **iq, bb_pp_i_v=m.get('vipp'), bb_pp_q_v=m.get('vqpp'),
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
XL rf_in_p rf_in_n rfo_p rfo_n rfq_p rfq_n ib1 en gain_lo byp ct0 ct1 ct2 se rt island_off nb vdcm VDD 0 ct3 att0 att1 att2 att3 att4 srcp_b srcn_b tkp_b tkn_b lobias pt_lna
{src_net(view)}
XI rfo_p rfo_n lip lin bip bin ib2 enm ofs0i ofs1i ofs2i ofs3i ofs4i ofs_signi island_off avi abi{HIBP} VDD 0 pt_rxmix_i
XQ rfq_p rfq_n lqp lqn bqp bqn ib3 enm ofs0q ofs1q ofs2q ofs3q ofs4q ofs_signq island_off avq abq{HIBP} VDD 0 pt_rxmix_q
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
Vhib hib 0 {vdd}
{_ofs(ofs, vdd)}
Rsp rp 0 300
Rsn rn 0 300
Ccp rp rf_p 4p
Ccn rn rf_n 4p
Vlp lo_p 0 PULSE(0 {vdd} 0 20p 20p {per / 2 - 20e-12} {per})
Vln lo_n 0 PULSE({vdd} 0 0 20p 20p {per / 2 - 20e-12} {per})
X1 rf_p rf_n lo_p lo_n bb_p bb_n ibias en ofs0 ofs1 ofs2 ofs3 ofs4 ofs_sign island_off atb_vcm atb_vbp{HIBP} VDD 0 pt_{block}
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


def _flat_ota_owners(text, sub):
    """Compact flat rxmix extractions (fork V) have no X..pt_rfrx_otan instance: the TIA OTA input
    pairs are flat pfets `<inst>_tail atb_vcm` (gate on atb_vcm, source on `<inst>_tail`).  Returns the
    sorted owner prefixes (XX6 = x_p side = ota1, XX7 = ota2), empty for hierarchical netlists."""
    owners, inside = set(), False
    for line in text.splitlines():
        tok = line.split()
        if tok and tok[0].lower() == '.subckt':
            inside = tok[1] == sub
        if inside and len(tok) > 5 and tok[2] == 'atb_vcm' and 'pfet' in line:   # tail as drain or source
            owners.update(x[:-5] for x in (tok[1], tok[3]) if x.endswith('_tail'))
    return sorted(owners)


def _flat_ota_line(line, owners):
    """Rewrite one flat input-pair line of OTA owner k onto nref<k>; returns (line, k or 0)."""
    tok = line.split()
    tl = [x for x in (tok[1:2] + tok[3:4]) if x.endswith('_tail') and x[:-5] in owners] if len(tok) > 5 else []
    if owners and tl and tok[2] == 'atb_vcm':
        k = owners.index(tl[0][:-5]) + 1
        tok[2] = f'nref{k}'
        return ' '.join(tok), k
    return line, 0


def _inject_mixer_noise(text, sub, na_ota, na_rtia):
    """Add trnoise sources to the mixer subcircuit: OTA input-referred noise (series with the + input)
    and Rtia thermal noise (current across each feedback resistor)."""
    out, inside, k = [], False, 0
    owners = _flat_ota_owners(text, sub)
    for line in text.splitlines():
        tok = line.split()
        if tok and tok[0].lower() == '.subckt':
            inside = tok[1] == sub
        if inside and owners:
            line, kk = _flat_ota_line(line, owners)
            tok = line.split()
        if inside and tok and tok[0].lower() == '.ends':
            if owners:
                out += [f'Vnota{j} nrefa{j} atb_vcm dc 0 trnoise({na_ota} {TN_NT} 0 0)' for j in (1, 2)]
                out += [f'Rnota{j} nrefa{j} nref{j} 10' for j in (1, 2)]
                k = len(owners)
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
XL rf_in_p rf_in_n rfo_p rfo_n rfq_p rfq_n ib1 en gain_lo byp ct0 ct1 ct2 se rt island_off nb vdcm VDD 0 ct3 att0 att1 att2 att3 att4 srcp_b srcn_b tkp_b tkn_b lobias pt_lna
{src_net(view)}
XI rfo_p rfo_n lip lin bip bin ib2 enm ofs0i ofs1i ofs2i ofs3i ofs4i ofs_signi island_off avi abi{HIBP} VDD 0 pt_rxmix_i
XQ rfq_p rfq_n lqp lqn bqp bqn ib3 enm ofs0q ofs1q ofs2q ofs3q ofs4q ofs_signq island_off avq abq{HIBP} VDD 0 pt_rxmix_q
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


def ota_input_noise(work, cell='pt_rfrx_otan', block='rxmix_i', f=5e6, corner=('typical', 27, 3.3), hib=True):
    """Open-loop input-referred noise (V/rtHz at f) of a mixer TIA OTA with the block's filtered bias.
    hib = True: RX state (pdx = 0, extra tail on); False: duplex state (pdx = VDD, base tail only)."""
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
Xo cm inn out vbpf enb {('0 ' if hib else 'VDD ') if (cell == 'pt_rfrx_otan' and HIBP) else ''}VDD 0 {cell}
Lf out inn 1k
* (RC-16e) no Cf here: a 1 F shunt with the 1 F Cin halved the drive and doubled the reported en
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
    log, m = run(work, f'otanoise_{cell}_{_tag(corner)}{"" if hib else "_hib0"}.cir', body, corner)
    return m.get('en')


# ---------------------------------------------------------------- LO source models (MW-20)
# The benches historically drive the mixers with an ideal 0/VDD square.  The real LO chain does not deliver that: pt_lo_ext
# (analog/timing/lo_ext_pad.py) passes with a SINE about VB ~ 0.739 VDD whose peak on-Vgs (above the 1.65 V mixer CM) is only
# 0.9-1.16 V (scratch/reviews/mode-walk.md MW-20).  lo = None: ideal square; ('sine', vb, amp): sine about vb (V) with amplitude
# amp (V) on each phase; ('include', path): a deck fragment from the LO owner that defines the four sources / the extracted LO
# distribution driving nodes lip lin lqp lqn (chain benches) or lo_p lo_n (rxmix benches).
LO_REAL = {'ext_best_1v16': ('sine', 2.44, 0.37), 'cml_1v05': ('sine', 2.44, 0.26), 'floor_0v90': ('sine', 2.44, 0.11)}


def lo_tag(lo):
    if not lo:
        return ''
    return f'_losin{lo[1]:g}_{lo[2]:g}' if lo[0] == 'sine' else '_loinc' + __import__('hashlib').md5(str(lo[1]).encode()).hexdigest()[:6]


def lo_sources(lo, vdd, flo, nodes=('lip', 'lin', 'lqp', 'lqn')):
    """LO drive for the nodes (I+, I-, Q+, Q-); same phase convention as the square bench."""
    if lo and lo[0] == 'include':
        return f'.include {lo[1]}'
    if lo and lo[0] == 'sine':
        vb, a = lo[1], lo[2]
        ex = [f'{vb}+{a}*sin(2*pi*{flo:g}*time)', f'{vb}-{a}*sin(2*pi*{flo:g}*time)',
              f'{vb}-{a}*cos(2*pi*{flo:g}*time)', f'{vb}+{a}*cos(2*pi*{flo:g}*time)']
    else:
        ex = [f'{vdd / 2}+{vdd / 2}*tanh(8*sin(2*pi*{flo:g}*time))', f'{vdd / 2}-{vdd / 2}*tanh(8*sin(2*pi*{flo:g}*time))',
              f'{vdd / 2}-{vdd / 2}*tanh(8*cos(2*pi*{flo:g}*time))', f'{vdd / 2}+{vdd / 2}*tanh(8*cos(2*pi*{flo:g}*time))']
    return '\n'.join(f'Bl{n} {n} 0 V={e}' for n, e in zip(nodes, ex))


# ---------------------------------------------------------------- deterministic chain NF (fork F/J)
# Same noise model as chain_tnoise (source 2 x 50 ohm, LNA input-referred from its AC NF, TIA OTA en, Rtia),
# but every path's |H| is measured with a small coherent tone in ONE transient (real 2.4 GHz LO switching),
# so there is no statistical scatter (chain_tnoise: +-1.5 dB with 4-8 bins; it read 11.87 dB for the
# previous LNA, this bench 14.16 dB).  SSB = I-channel, image band counted as noise (the published basis);
# DSB = image band counted as signal (zero-IF basis, RF-RX-NFSYS).
DET_T0, DET_T1 = 1.0e-6, 3.0e-6
DET_TONES = [('sig', 4.0, 1), ('sig', 6.0, 1), ('sig', 8.5, 1), ('img', 4.5, -1), ('h3u', 5.0, 3), ('h3l', 5.5, -3),
             ('h5u', 9.0, 5), ('h5l', 9.5, -5), ('ota1', 6.5, 0), ('ota2', 7.0, 0), ('r1', 7.5, 0), ('r2', 8.0, 0)]
DET_SRC, DET_OTA, DET_R = 1e-4, 1e-4, 1e-8


def _det_mixer_text(sub):
    txt = S.ngspice_netlist((flow.GENERATED / f'{sub}.ext.spice').read_text())
    if sub != 'rxmix_i':
        return txt
    f = {k: m for k, m, _ in DET_TONES}
    out, inside, k = [], False, 0
    owners = _flat_ota_owners(txt, f'pt_{sub}')
    for line in txt.splitlines():
        tok = line.split()
        if tok and tok[0].lower() == '.subckt':
            inside = tok[1] == f'pt_{sub}'
        if inside and owners:
            line, kk = _flat_ota_line(line, owners)
            tok = line.split()
        if inside and tok and tok[0].lower() == '.ends':
            if owners:
                out += [f'Vnota{j} nrefa{j} atb_vcm dc 0 SIN(0 {DET_OTA} {f["ota%d" % j] * 1e6})' for j in (1, 2)]
                out += [f'Rnota{j} nrefa{j} nref{j} 10' for j in (1, 2)]
                k = len(owners)
            out += [f'Vnr1 ncr1 0 dc 0 SIN(0 {DET_R * 1e6} {f["r1"] * 1e6})', 'Gnr1 x_p bb_n ncr1 0 1e-6',
                    f'Vnr2 ncr2 0 dc 0 SIN(0 {DET_R * 1e6} {f["r2"] * 1e6})', 'Gnr2 x_n bb_p ncr2 0 1e-6']
            inside = False
        if inside and tok and tok[-1] == 'pt_rfrx_otan' and tok[1] == 'atb_vcm':
            k += 1
            out.append(f'Vnota{k} nrefa{k} atb_vcm dc 0 SIN(0 {DET_OTA} {f["ota%d" % k] * 1e6})')
            out.append(f'Rnota{k} nrefa{k} nref{k} 10')
            line = line.replace(' atb_vcm ', f' nref{k} ', 1)
        out.append(line)
    if k != 2:
        raise RuntimeError('chain_det: expected two TIA OTAs on atb_vcm in rxmix_i')
    return '\n'.join(out) + '\n'


def chain_det(work, view, corner=('typical', 27, 3.3), ct=LNA_CT_RESET, match=None, flo=2.4e9, rt=False, lo=None):
    import numpy as np
    c, t, vdd = corner
    work.mkdir(parents=True, exist_ok=True)
    if match is None:
        u = lna_ac(work, view, corner, ct=ct)
        match = board_match(complex(u['zin_re_ohm'], u['zin_im_ohm']))
    mm = lna_ac(work, view, corner, ct=ct, match=match, rt=rt)
    # LNA's own noise (review: the 50 ohm/leg mixer MODEL's thermal noise must not be injected again; the real mixers
    # are in the transient): input-referred noise factor with a noiseless load of the same conductance
    mm_nl = lna_ac(work, view, corner, ct=ct, match=match, rt=rt, noiseless_load=True)
    nl = netlist(work, 'lna', view)
    for b in ('rxmix_i', 'rxmix_q'):
        (work / f'{b}_det.spice').write_text(_det_mixer_text(b))
    terms = [f'{DET_SRC}*sin(2*pi*{abs(hs) * flo + (1 if hs > 0 else -1) * fm * 1e6:.6e}*time)'
             for k, fm, hs in DET_TONES if hs != 0]
    rtag = f'chdet_{view}_{_tag(corner)}_ct{ct}{"_rt" if rt else ""}{lo_tag(lo)}'
    body = f""".include {nl}
.include rxmix_i_det.spice
.include rxmix_q_det.spice
VDD VDD 0 {vdd}
Vibs vib 0 3.3
Ib1 vib ib1 10u
Ib2 vib ib2 10u
Ib3 vib ib3 10u
{_ctl(['en', 'gain_lo', 'byp', 'island_off'], {'en'}, vdd)}
Venm enm 0 {vdd}
{_ofs(0, vdd, 'i')}
{_ofs(0, vdd, 'q')}
Bs s 0 V={'+'.join(terms)}
Ep a_p 0 s 0 0.5
En a_n 0 s 0 -0.5
Rsp a_p sp 50
Rsn a_n sn 50
{_match_net(match)}Cpp rf_in_p 0 0.5p
Cpn rf_in_n 0 0.5p
{lo_sources(lo, vdd, flo)}
{_lna_trim(vdd, ct=ct, rt=rt)}
XL rf_in_p rf_in_n rfo_p rfo_n rfq_p rfq_n ib1 en gain_lo byp ct0 ct1 ct2 se rt island_off nb vdcm VDD 0 ct3 att0 att1 att2 att3 att4 srcp_b srcn_b tkp_b tkn_b lobias pt_lna
{src_net(view)}
XI rfo_p rfo_n lip lin bip bin ib2 enm ofs0i ofs1i ofs2i ofs3i ofs4i ofs_signi island_off avi abi{HIBP} VDD 0 pt_rxmix_i
XQ rfq_p rfq_n lqp lqn bqp bqn ib3 enm ofs0q ofs1q ofs2q ofs3q ofs4q ofs_signq island_off avq abq{HIBP} VDD 0 pt_rxmix_q
Cbi1 bip 0 1p
Cbi2 bin 0 1p
Cbq1 bqp 0 1p
Cbq2 bqn 0 1p
.save v(bip) v(bin)
.tran 5p {DET_T1} 0 8p
.control
run
linearize v(bip) v(bin)
let vi=v(bip)-v(bin)
wrdata {rtag}.dat vi
.endc
"""
    deck = f'* {rtag}.cir\n' + flow.sim_header(c, t) + body + '\n.end\n'
    if (work / f'{rtag}.cir').exists() and (work / f'{rtag}.dat').exists() and (work / f'{rtag}.cir').read_text() == deck:
        pass   # fork P: identical deck already simulated (deterministic) -> reuse the transient
    else:
        run(work, rtag + '.cir', body, corner, timeout=6 * 3600)
    rows = S.read_table(work / f'{rtag}.dat')
    tt = np.array([r[0] for r in rows]); vv = np.array([r[1] for r in rows])
    sel = (tt >= DET_T0) & (tt <= DET_T1)
    tt, vv = tt[sel], vv[sel]
    cols = [np.ones_like(tt), tt - DET_T0, (tt - DET_T0) ** 2]
    for _, fm, _ in DET_TONES:
        cols += [np.sin(2 * np.pi * fm * 1e6 * tt), np.cos(2 * np.pi * fm * 1e6 * tt)]
    A = np.vstack(cols).T
    cf = np.linalg.lstsq(A, vv, rcond=None)[0]
    amp = {}
    for i, (k, fm, _) in enumerate(DET_TONES):
        amp.setdefault(k, []).append((fm, math.hypot(cf[3 + 2 * i], cf[4 + 2 * i])))
    hs = sorted((fm, a / DET_SRC) for fm, a in amp['sig'])
    hsig = lambda f: float(np.interp(f, [x[0] for x in hs], [x[1] for x in hs]))
    f_lna = 10 ** (mm_nl['nf_db'] / 10)
    # fork P: noise folded from the odd LO harmonics is measured, not assumed.  (a) source noise at h*fLO
    # through the real board network + LNA + mixer (the h3/h5 tones, F = 1); (b) the LNA's OWN output noise
    # at h*fLO (tb.lna_ac noise analysis, same board network, noiseless 50 ohm/leg load) folded by the mixer's h-th harmonic
    # conversion, taken as 1/h of the fundamental (ideal 50 % hard-switched passive mixer), per sideband.
    hn = {h: lna_ac(work, view, corner, ct=ct, match=match, f=h * flo, noiseless_load=True, rt=rt) for h in (3, 5)}
    g1 = 10 ** (mm['gain_db'] / 20)
    kt = 4 * 1.380649e-23 * (273.15 + t) * 100
    lna_h = {}
    for h in (3, 5):
        if hn[h].get('nf_db') is None or hn[h].get('gain_db') is None:
            lna_h[h] = None; continue
        n_out = (10 ** (hn[h]['nf_db'] / 10) - 1) * 10 ** (hn[h]['gain_db'] / 10) * kt   # LNA-only output noise, V^2/Hz
        lna_h[h] = n_out / h ** 2 / (g1 ** 2 * kt)                                       # input-referred, per sideband
    en = ota_input_noise(work, corner=corner, hib=not lobias())   # duplex (lobias): rxmix hib = 0, base OTA tail
    sv = {'ota': (DET_OTA, en ** 2), 'r': (DET_R, KT4 / 20e3)}
    parts = {}
    for k, lst in amp.items():
        for fm, a in lst:
            fk = 1.0 if k[:1] == 'h' else f_lna
            ref, s_ = sv.get(k.rstrip('12'), (DET_SRC, KT4 * 100 * fk))
            parts.setdefault(k, []).append((a / ref) ** 2 * s_ / (hsig(fm) ** 2 * KT4 * 100))
    F = {k: float(np.mean(v)) for k, v in parts.items()}
    for h in (3, 5):
        for sb in 'ul':
            if lna_h[h] is not None:
                F[f'h{h}{sb}_lna'] = lna_h[h]
    tot = sum(F.values())
    return dict(corner=list(corner), ct=ct, view=view, lna_matched=mm, match=match,
                nf_ssb_db=10 * math.log10(tot), nf_dsb_db=10 * math.log10(tot / (1 + F['img'] / F['sig'])),
                f_parts={k: round(v, 4) for k, v in F.items()},
                lna_harmonic={f'h{h}': dict(nf_db=hn[h].get('nf_db'), gain_db=hn[h].get('gain_db'), folded_per_sideband=lna_h[h],
                                           mixer_conversion_rel='1/h (ideal)') for h in (3, 5)},
                gain_sig_db={f'{fm}MHz': round(20 * math.log10(h), 2) for fm, h in hs}, ota_en_v_rthz=en,
                resid_rms_v=float((vv - A @ cf).std()))
