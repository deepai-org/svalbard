#!/usr/bin/env python3
"""QVCO frequency loop (LO3 / GX-6 / IX-5): architecture numbers, behavioural
lock + phase-settling simulation, and closed-loop phase-noise budget against
RF-RX-LOPN.  BEHAVIOURAL ONLY (no transistor-level loop exists yet): the VCO
tuning curves are the r3 transistor-level QVCO results (results.json
'extremes'); PFD/CP/divider are ideal-with-nonidealities models stated below.

Architecture (proposal, LO owner 2026-11-11):
  REF_IN 50 MHz XO (B23 lists 50.625 MHz for the wired FLL; any ref works fractionally, already on the board for the wired FLL; in internal-LO
  mode REF_IN is not carrying the external LO) -> PFD at 50 MHz
  PRE (QVCO I+ tap) -> extended 2/3 multi-modulus divider, N = 32..127
  (custom TSPC, first cell toggles at <= 3.1 GHz), fractional via a 3rd-order
  MASH 1-1-1 sigma-delta (16-bit fraction, std cells at 50 MHz).
  Lock range of the divider: (32+3)*50 = 1.75 .. (127-4)*50 = 6.15 GHz (MMD input limit ~3.1-3.5 GHz),
  which covers the whole r3 tank at every simulated corner (1.927-2.975 GHz):
  GX-6 satisfied with no clamp.
  Band search: digital FLL (counts PRE/16 against REF for 1.28 us, 4-bit
  binary search over BAND[3:0] with VTUNE pre-set to VDD/2) -> 4 x 1.6 us.
  Then type-II CP loop, 3rd-order passive filter.

    python3 loop_design.py      # prints + writes results to lcvco/loop_design.json
"""
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
FREF = 50e6
VDD = 3.3
VT_LO, VT_HI = 0.3, 3.0


def tank_points():
    r = json.loads((HERE / 'results.json').read_text())['extremes']
    pts = {}
    for k, v in r.items():
        pts[k] = v['f_hz']
    return pts


def kvco_table(pts):
    """MHz/V per (corner/variant, band) from the VTUNE 0.3 / 3.0 pair."""
    out = {}
    for k, f in pts.items():
        if k.endswith('_vt0.3'):
            base = k[:-6]
            f2 = pts.get(base + '_vt3.0')
            if f and f2:
                out[base] = dict(f_lo=f, f_hi=f2, kvco_mhz_v=(f2 - f) / (VT_HI - VT_LO) / 1e6)
    return out


# ---------------- loop filter (3rd-order passive: C1 || (R + C2)... classic) -------------
# Z(s) = (1 + s R C2) / (s (C1 + C2) (1 + s R C1 C2/(C1+C2)))   (C2 = zero cap, C1 = ripple cap)
def design(fc, pm_deg, icp, kvco_hz_v, n):
    wc = 2 * math.pi * fc
    pm = math.radians(pm_deg)
    b = (math.tan(pm) + 1 / math.cos(pm)) ** 2        # pole/zero spread for max phase at wc
    tz = math.sqrt(b) / wc                             # R C2
    tp = 1 / (wc * math.sqrt(b))                       # R C1 C2/(C1+C2)
    kv = 2 * math.pi * kvco_hz_v
    # |G(jwc)| = icp/(2pi) * kv/n * |Z(jwc)| / wc = 1
    zmag_per_ct = abs((1 + 1j * wc * tz) / (1j * wc * (1 + 1j * wc * tp)))
    ct = icp / (2 * math.pi) * kv / n * zmag_per_ct / wc
    c2 = ct * (1 - tp / tz)
    c1 = ct - c2
    r = tz / c2
    return dict(fc_hz=fc, pm_deg=pm_deg, icp_a=icp, kvco_hz_v=kvco_hz_v, n=n, c1_f=c1, c2_f=c2, r_ohm=r, b=b)


def open_loop(f, d, kvco_hz_v=None, n=None):
    s = 2j * math.pi * np.asarray(f)
    c1, c2, r = d['c1_f'], d['c2_f'], d['r_ohm']
    z = (1 + s * r * c2) / (s * (c1 + c2) * (1 + s * r * c1 * c2 / (c1 + c2)))
    kv = 2 * math.pi * (kvco_hz_v or d['kvco_hz_v'])
    return d['icp_a'] / (2 * math.pi) * kv / (n or d['n']) * z / s


def margins(d, kvco_hz_v, n):
    f = np.logspace(3, 8, 20000)
    g = open_loop(f, d, kvco_hz_v, n)
    i = np.argmin(abs(abs(g) - 1))
    return f[i], 180 + math.degrees(np.angle(g[i]))


# ---------------- time-domain behavioural hop simulation ----------------
def hop_sim(d, f_from, f_to, kv_curve, t_end=100e-6, cp_mismatch=0.05, leak_a=2e-9, t_rst=150e-12,
            vt0=VDD / 2, nsub=40):
    """Cycle-accurate behavioural model (one iteration per reference cycle, exact
    edge times, no time-step quantization): tri-state PFD with a `t_rst` reset
    pulse during which both pumps conduct with `cp_mismatch` UP/DN mismatch,
    constant `leak_a` VTUNE leakage, CP headroom roll-off outside VT_LO..VT_HI,
    3rd-order passive filter (C1 on VTUNE, R + C2) integrated in `nsub` sub-steps
    per cycle, VCO f(VTUNE) = kv_curve (r3 transistor-level end points), divider
    N = f_to / FREF exactly (sigma-delta noise is in the noise budget, not here).
    The loop closes after band search with VTUNE preset to vt0 and the PFD and
    divider reset.  'Phase-settled' = LO phase within 2 deg of its final
    trajectory (phase sampled at the reference edges, i.e. ref-spur ripple
    excluded; the spur is reported separately as a VTUNE ripple)."""
    n = f_to / FREF
    tref = 1 / FREF
    c1, c2, r, icp = d['c1_f'], d['c2_f'], d['r_ohm'], d['icp_a']
    v1 = v2 = vt0
    ph = 0.0                       # VCO phase, cycles, at the current ref edge, relative to n*k
    ncyc = int(t_end / tref)
    err, fr, rip = [], [], []
    for k in range(ncyc):
        # divider edge time relative to the ref edge: phase deficit / f
        f0 = kv_curve(v1)
        dt_e = -ph / f0            # >0: divider edge late -> UP pulse of width dt_e
        dt_e = max(min(dt_e, 0.95 * tref), -0.95 * tref)
        width = abs(dt_e)
        sgn = 1 if dt_e > 0 else -1
        iu = icp * (1 + cp_mismatch / 2) * (1 if v1 < VT_HI else max(0.0, (VDD - 0.1 - v1) / (VDD - 0.1 - VT_HI)))
        idn = icp * (1 - cp_mismatch / 2) * (1 if v1 > VT_LO else max(0.0, (v1 - 0.1) / (VT_LO - 0.1)))
        # net charge: main pulse plus both-on reset pulse (mismatch)
        q = (iu if sgn > 0 else -idn) * width + (iu - idn) * t_rst - leak_a * tref
        v1 += q / c1
        # free evolution over the cycle (R between C1 and C2), integrate VCO phase
        h = tref / nsub
        phase_cyc = 0.0
        vmax, vmin = v1, v1
        for _ in range(nsub):
            ir = (v1 - v2) / r
            v1 -= ir / c1 * h
            v2 += ir / c2 * h
            phase_cyc += kv_curve(v1) * h
            vmax, vmin = max(vmax, v1), min(vmin, v1)
        ph += phase_cyc - n
        err.append(ph * 360.0)
        fr.append(phase_cyc / tref)
        rip.append(vmax - vmin)
    t = np.arange(ncyc) * tref
    e = np.array(err)
    final = np.mean(e[t > t_end - 5e-6])
    ed = e - final
    bad = np.where(abs(ed) > 2.0)[0]
    t_settle = float(t[bad[-1] + 1]) if len(bad) and bad[-1] + 1 < len(t) else (0.0 if not len(bad) else None)
    fa = np.array(fr)
    i80 = int(80e-6 / tref)
    return dict(f_from_hz=f_from, f_to_hz=f_to, n=n, t_phase_settle_2deg_s=t_settle,
                f_err_at_80us_hz=float(np.mean(fa[i80 - 50:i80 + 50]) - f_to), vtune_final_v=v1,
                max_err_deg_after_40us=float(np.max(abs(ed[t > 40e-6]))),
                vtune_ripple_pp_v_final=float(np.mean(np.array(rip)[-100:])),
                static_phase_offset_ps=float(-final / 360.0 / f_to * 1e12))


def lin_curve(fa, fb):
    """VCO tuning curve through (0.3 V, fa) and (3.0 V, fb), saturating outside
    0..VDD (the accumulation varactor flattens towards the rails)."""
    def f(v):
        v = min(max(v, 0.0), VDD)
        return fa + (fb - fa) * (v - VT_LO) / (VT_HI - VT_LO)
    return f


# ---------------- phase noise budget ----------------
def pn_budget(d, f_off, vco_l1m_dbc, fpfd=FREF, n=49, ref_floor_dbc=-150.0, pfd_fom=-208.0, mash_order=3):
    """Closed-loop L(f) at the LO.  Contributions:
    VCO: 1/f^2 from the Leeson number at 1 MHz (run_lcvco.phase_noise), high-passed by 1/(1+G).
    REF: 25 MHz XO floor ref_floor_dbc (B23 asks <= 1 ps rms 12k-5M, which a -150 dBc/Hz floor meets) x N^2, low-passed.
    PFD/CP/divider in-band floor: normalized pfd_fom dBc/Hz (1 Hz, 1 Hz PFD) + 10log fpfd + 20log N
      (-208 is a conservative mature-CMOS value; GF180 at 25 MHz assumed 5-10 dB worse than the -215..-220 literature).
    Sigma-delta MASH 1-1-1 quantization: S_phi = (2pi)^2/(12 fpfd) (2 sin(pi f/fpfd))^(2(m-1)) rad^2/Hz at the divider
      output referred to the VCO by x1 (phase in VCO cycles) then low-passed; L = S_phi/2."""
    f = np.asarray(f_off, float)
    g = open_loop(f, d, d['kvco_hz_v'], n)
    h_lp = abs(g / (1 + g)) ** 2
    h_hp = abs(1 / (1 + g)) ** 2
    vco = 10 ** (vco_l1m_dbc / 10) * (1e6 / f) ** 2 * h_hp
    ref = 10 ** (ref_floor_dbc / 10) * n ** 2 * h_lp
    pfd = 10 ** ((pfd_fom + 10 * math.log10(fpfd) + 20 * math.log10(n)) / 10) * h_lp
    sd = (2 * math.pi) ** 2 / (12 * fpfd) * (2 * np.sin(np.pi * f / fpfd)) ** (2 * (mash_order - 1)) * h_lp / 2
    tot = vco + ref + pfd + sd
    db = lambda x: 10 * np.log10(x)
    return dict(f_hz=f.tolist(), total_dbc_hz=db(tot).tolist(), vco=db(vco).tolist(), ref=db(ref).tolist(),
                pfd_cp_div=db(pfd).tolist(), sigma_delta=db(sd).tolist())


def integrated_jitter(d, vco_l1m, n=49, f0=2.45e9, f1=1e4, f2=100e6):
    f = np.logspace(math.log10(f1), math.log10(f2), 4000)
    b = pn_budget(d, f, vco_l1m, n=n)
    l = 10 ** (np.array(b['total_dbc_hz']) / 10)
    phi2 = 2 * np.trapezoid(l, f)
    return math.sqrt(phi2) / (2 * math.pi * f0) * 1e12


MASK = {1e6: -95, 3e6: -107, 20e6: -115, 40e6: -120, 100e6: -130}


def main():
    pts = tank_points()
    kt = kvco_table(pts)
    f_min_all = min(v['f_lo'] for v in kt.values())
    f_max_all = max(v['f_hi'] for v in kt.values())
    guaranteed = (max(v['f_lo'] for k, v in kt.items() if '_b15' in k), min(v['f_hi'] for k, v in kt.items() if '_b0' in k))
    kv = [v['kvco_mhz_v'] for v in kt.values()]
    n_lo, n_hi = 32 + 3, 127 - 4          # MASH 1-1-1 swings N by -3..+4
    div_range = (n_lo * FREF, n_hi * FREF)
    res = dict(note='BEHAVIOURAL loop model; VCO curves from r3 transistor-level QVCO extremes (schematic QVCO, spiral model)',
               fref_hz=FREF, divider='extended 2/3 MMD (Vaucher, 7 cells, range-extension to N=32) N=32..127, MASH 1-1-1 fractional', divider_lock_range_hz=div_range,
               tank_all_corners_hz=(f_min_all, f_max_all), tank_guaranteed_all_corners_hz=guaranteed,
               gx6_covered=bool(div_range[0] <= f_min_all and div_range[1] >= f_max_all),
               kvco_mhz_v_range=(min(kv), max(kv)), kvco_table=kt)
    # loop: fc 400 kHz at the nominal Kvco (60 MHz/V), PM 60; Icp 100 uA
    d = design(400e3, 60, 100e-6, 60e6, 49)
    res['loop'] = d
    res['loop_area_um2_mos_cap_5ff_um2'] = (d['c1_f'] + d['c2_f']) / 5e-15
    res['margins_over_kvco_n'] = []
    for kvv in (min(kv) * 1e6, 60e6, max(kv) * 1e6):
        for n in (38, 49, 60):
            fc, pm = margins(d, kvv, n)
            res['margins_over_kvco_n'].append(dict(kvco_mhz_v=kvv / 1e6, n=n, fc_hz=fc, pm_deg=pm))
    # IX-5 hops: 78 MHz BLE CS hops (2402 <-> 2480) at the steepest and flattest curves,
    # VTUNE pre-set to VDD/2 after band search (the band search leaves the target within the band)
    hops = []
    for name, (fa, fb) in {'tt_b6': (2.3993e9 * 0.98, 2.5566e9 * 0.98),     # r2 codes x r3 load shift
                           'flat_40MHz_V': (2.40e9, 2.40e9 + 2.7 * 40e6),
                           'steep_75MHz_V': (2.36e9, 2.36e9 + 2.7 * 75e6)}.items():
        cur = lin_curve(fa, fb)
        for f_to in (2.402e9, 2.480e9):
            if not (fa <= f_to <= fb):
                continue
            r = hop_sim(d, None, f_to, cur)
            r['curve'] = name
            hops.append(r)
            print(name, f_to, {k: r[k] for k in ('t_phase_settle_2deg_s', 'f_err_at_80us_hz', 'vtune_final_v', 'max_err_deg_after_40us')}, flush=True)
    res['ix5_hops'] = hops
    band_search_s = 4 * 1.6e-6
    worst = max((h['t_phase_settle_2deg_s'] or 1) for h in hops)
    res['ix5_total_s'] = band_search_s + worst
    res['ix5_pass_75us'] = bool(res['ix5_total_s'] <= 75e-6)
    # phase noise: VCO 1 MHz numbers from run_lcvco.phase_noise (nominal / low-Q)
    pn = {}
    for case, l1m in (('nominal_q', -124.5), ('low_q', -117.7)):
        b = pn_budget(d, list(MASK), l1m)
        pn[case] = dict(vco_l1m_dbc_hz=l1m, at_mask=[dict(f_hz=f, total=t, mask=MASK[f], margin_db=MASK[f] - t,
                                                             vco=v, ref=rr, pfd=p, sd=s)
                                                        for f, t, v, rr, p, s in zip(b['f_hz'], b['total_dbc_hz'], b['vco'], b['ref'], b['pfd_cp_div'], b['sigma_delta'])],
                        rms_jitter_ps_10k_100M=integrated_jitter(d, l1m))
        pn[case]['meets_mask'] = all(x['margin_db'] >= 0 for x in pn[case]['at_mask'])
    res['phase_noise'] = pn
    (HERE / 'loop_design.json').write_text(json.dumps(res, indent=1, default=float) + '\n')
    print(json.dumps({k: res[k] for k in ('divider_lock_range_hz', 'tank_all_corners_hz', 'tank_guaranteed_all_corners_hz', 'gx6_covered',
                                          'kvco_mhz_v_range', 'loop', 'loop_area_um2_mos_cap_5ff_um2', 'margins_over_kvco_n', 'ix5_total_s', 'ix5_pass_75us')}, indent=1, default=float))
    for c, v in pn.items():
        print(c, v['meets_mask'], round(v['rms_jitter_ps_10k_100M'], 3), [(x['f_hz'], round(x['total'], 1), round(x['margin_db'], 1)) for x in v['at_mask']])


if __name__ == '__main__' and __import__('sys').argv[1:] != ['r4']:
    main()


# ---------------- round 4: jitter closure (LO owner, 2026-11-11) ----------------
# Component-level in-band model replacing the single -208 dBc/Hz FOM:
#  CP: measured schematic pt_lo_pfdcp noise (fork B, loop_tl.json): CP-only in-band at the VCO
#      -84.4 dBc/Hz @10 kHz (flicker, ~1/f) with t_on 0.98 ns, fpfd 50 MHz, N 49; thermal floor ~-106.
#      Scales with 10log(t_on) and with the flicker improvement (mirror W*L / degeneration).
#  PFD/divider retimed jitter 0.3 ps rms (white).  XO floor -150 dBc/Hz x N^2.
#  Sigma-delta: MASH 1-1-1, fractional step 2 VCO cycles (CML /2 prescaler, fork B) -> x4.
#  4th-order filter pole at 4*fc.  VCO: 1/f^2 from L(1 MHz).
R4_CP_10K, R4_CP_FLOOR = -84.4, -106.0     # fork-B r1 CP (as measured, pt_pfd reset)
# fork-F r2 CP/PFD (lo_pfdcp.spice, schematic, fixed noise bench): -125.1 dBc/Hz in-band @10 kHz at t_on 0.193 ns,
# ~-129 @1 MHz  ->  equivalent to a 33.5 dB flicker improvement and a -120.9 floor when referenced to 0.98 ns.
R4F_FLICK_IMPR, R4F_FLOOR = 33.5, -128.0 + 7.06
# worst EXTRACTED corner (fork G, g/cp_noise_ext.json): ff -123.4 dBc/Hz @10 kHz (1.7 dB worse than the schematic tt value)
R4X_FLICK_IMPR, R4X_FLOOR = 31.8, -126.3 + 7.06


def r4_jitter(fc, vco_l1m, flick_impr_db, t_on_ns, n=49, fpfd=FREF, f0=2.45e9, ref_floor=-150.0, pfd_jit=0.3e-12,
              sd_step=2, mash=3, fp3_ratio=4.0, kv=60e6, vco_f3_corner=0.0, icp_scale=False):
    """vco_f3_corner: 1/f^3 (flicker-upconversion) corner of the VCO in Hz (0 = none).
    icp_scale: LO18 Icp = 100 uA * min(1, 60 MHz/V / Kvco); CP phase noise scales ~ 1/Icp (in^2 ~ Icp)."""
    icp_ratio = min(1.0, 60e6 / kv) if icp_scale else 1.0
    f = np.logspace(4, 8, 4000)
    s = 2j * np.pi * f
    d = design(fc, 60 + math.degrees(math.atan(1 / fp3_ratio)), 100e-6, 60e6, n)
    g = open_loop(f, d, kv, n) * icp_ratio / (1 + s / (2 * np.pi * fp3_ratio * fc))
    lp, hp = abs(g / (1 + g)) ** 2, abs(1 / (1 + g)) ** 2
    ts = 10 * math.log10(t_on_ns / 0.98) - 10 * math.log10(icp_ratio)
    c = dict(vco=10 ** (vco_l1m / 10) * (1e6 / f) ** 2 * (1 + vco_f3_corner / f) * hp,
             ref=10 ** (ref_floor / 10) * n ** 2 * lp,
             cp=(10 ** ((R4_CP_10K - flick_impr_db + ts) / 10) * (1e4 / f) + 10 ** ((R4_CP_FLOOR + ts) / 10)) * lp,
             pfd_div=(2 * np.pi * f0 * pfd_jit) ** 2 / fpfd / 2 * lp,
             sd=sd_step ** 2 * (2 * np.pi) ** 2 / (12 * fpfd) * (2 * np.sin(np.pi * f / fpfd)) ** (2 * (mash - 1)) * lp / 2)
    j = {k: math.sqrt(2 * np.trapezoid(v, f)) / (2 * np.pi * f0) * 1e12 for k, v in c.items()}
    j['total'] = math.sqrt(sum(x * x for x in j.values()))
    tot = sum(c.values())
    at = {fm: float(10 * np.log10(np.interp(fm, f, tot))) for fm in MASK}
    return dict(design=d, jitter_ps=j, pn_at_mask=at, mask_ok=all(at[k] <= MASK[k] for k in MASK))


def r4_main():
    out = {}
    cases = {'as_measured_cp': (0, 0.98), 'cp_fix_-15dB_ton1.4': (15, 1.4), 'cp_fix_-15dB_ton2.2_fracN': (15, 2.2)}
    for vco in (-112.0, -117.7):
        for name, (fi, ton) in cases.items():
            for fc in (100e3, 150e3, 250e3, 400e3):
                r = r4_jitter(fc, vco, fi, ton)
                out[f'vco{vco}_{name}_fc{int(fc/1e3)}k'] = dict(jitter_ps=r['jitter_ps'], pn_at_mask=r['pn_at_mask'], mask_ok=r['mask_ok'])
    global R4_CP_FLOOR
    floor0 = R4_CP_FLOOR
    R4_CP_FLOOR = R4F_FLOOR
    out['r2_measured_cp'] = {f'vco{v}_kv{int(k/1e6)}': (lambda r: dict(jitter_ps=r['jitter_ps'], pn_at_mask=r['pn_at_mask'], mask_ok=r['mask_ok']))(
        r4_jitter(250e3, v, R4F_FLICK_IMPR, 2.2, kv=k)) for v in (-112.0, -114.6) for k in (40e6, 60e6, 120e6)}
    sel = r4_jitter(250e3, -112.0, R4F_FLICK_IMPR, 2.2)
    # audit rebuild (2026-11-11 late): extracted worst-corner CP, LO18 Icp scaling, N 44/49/56,
    # VCO bound with flicker upconversion (1/f^3 corner 0.3 and 1 MHz; no simulated flicker value exists yet)
    R4_CP_FLOOR = R4X_FLOOR
    rb = {}
    for vco in (-112.0, -114.6):
        for f3 in (0.0, 300e3, 1e6):
            for kvv in (38e6, 60e6, 122e6, 200e6):
                for nn in (44, 49, 56):
                    r = r4_jitter(250e3, vco, R4X_FLICK_IMPR, 2.2, n=nn, kv=kvv, vco_f3_corner=f3, icp_scale=True)
                    rb[f'vco{vco}_f3c{int(f3/1e3)}k_kv{int(kvv/1e6)}_n{nn}'] = dict(total_ps=r['jitter_ps']['total'], mask_ok=r['mask_ok'],
                                                                                   pn_at_mask=r['pn_at_mask'])
    out['audit_rebuild'] = rb
    out['audit_rebuild_worst'] = {f'vco{v}_f3c{int(f3/1e3)}k': max(x['total_ps'] for k, x in rb.items() if k.startswith(f'vco{v}_f3c{int(f3/1e3)}k_'))
                                  for v in (-112.0, -114.6) for f3 in (0.0, 300e3, 1e6)}
    R4_CP_FLOOR = floor0
    out['selected'] = dict(note='fpfd 50 MHz XO, Icp 100 uA, fc 250 kHz, PM 74 incl. R3/C3 pole at 1 MHz, MASH 1-1-1 step 2; '
                                'measured r2 CP/PFD (fork F, schematic) with fracN on-time 2.2 ns; VCO -112 dBc/Hz@1MHz (pessimistic; r5 RC-extracted tt is -114.6)',
                           filter=dict(r_ohm=sel['design']['r_ohm'], c1_f=sel['design']['c1_f'], c2_f=sel['design']['c2_f'], r3_ohm=10e3, c3_f=15.9e-12),
                           jitter_ps=sel['jitter_ps'], pn_at_mask=sel['pn_at_mask'], mask_ok=sel['mask_ok'])
    return out


if __name__ == '__main__' and __import__('sys').argv[1:] == ['r4']:
    r = r4_main()
    j = json.loads((HERE / 'loop_design.json').read_text())
    j['r4'] = r
    if 'loop_lo13_superseded' not in j:
        j['loop_lo13_superseded'] = j['loop']
    d4 = design(250e3, 60 + math.degrees(math.atan(0.25)), 100e-6, 60e6, 49)
    d4.update(r3_ohm=10e3, c3_f=15.9e-12, note='r4 filter; the R3/C3 pole is NOT in hop_sim (3rd-order model)')
    j['loop'] = d4
    hops = []
    for name, (fa, fb) in {'flat_40MHz_V': (2.40e9, 2.40e9 + 2.7 * 40e6), 'steep_75MHz_V': (2.36e9, 2.36e9 + 2.7 * 75e6)}.items():
        for f_to in (2.402e9, 2.480e9):
            h = hop_sim(d4, None, f_to, lin_curve(fa, fb)); h['curve'] = name; hops.append(h)
    j['ix5_hops'] = hops
    j['ix5_total_s'] = 4 * 1.6e-6 + max((h['t_phase_settle_2deg_s'] or 1) for h in hops)
    j['ix5_pass_75us'] = bool(j['ix5_total_s'] <= 75e-6)
    j['ix5_note'] = 'behavioural cycle model, r4 3rd-order filter, starts from VTUNE=VDD/2 after band search; not yet confirmed by the transistor-level ladder'
    (HERE / 'loop_design.json').write_text(json.dumps(j, indent=1, default=float) + '\n')
    print(json.dumps(r['selected'], indent=1, default=float))
