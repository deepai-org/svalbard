#!/usr/bin/env python3
"""AC-3 CDR r-pi loop model (behavioural, NOT circuit evidence) -- resume 4.

Architecture (replaces the r-ac3 vote-on-filter pump, AC3-W8):
  * proportional path: the per-bit votes UPk/DNk (k = 0..bpc-1) drive the RX ring's fast-tune port
    (pt_pll_ring r8 `FT` legs) directly.  Each net vote shifts the ring frequency by kp (fraction) for
    exactly one ring cycle.  No charge pump, so no switch-charge offset: any constant injection is a
    static frequency offset that the integral path absorbs.
  * integral path: the votes are summed over M ring cycles (decimator in pt_cdr), and the SIGN of the
    sum fires one fixed pump packet on the existing VCTRL filter (ki = fractional frequency step per
    packet).  The pump then toggles at <= f_ring/M, so the measured per-toggle error scales by 1/M
    and can be overcome by the packet (checked with `pump_offset`).
  * frequency acquisition: RTL FLL on the integral pump (AC3-W1), residual `fll_res_ppm`.
Votes act `lat` ring cycles after the sampling edge.

Jitter / channel terms: rj (rms UI), channel ISI as data-dependent edge jitter (+-isi/2 UI on a
transition after a run), ring random-walk jitter `ring_rw_ps` rms per ring cycle, phase-trim residual
`ptrim_ui` (static sampling offset), slicer aperture.  The BER bound is the statistical
eye: for each simulated bit, P(err) = Q((half_eye - |deterministic offset|)/rj); the sum is reported
(`ber_stat`), plus bit errors counted with the random draw.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def qfunc(x):
    return 0.5 * math.erfc(x / math.sqrt(2))


def run(f_ring=625e6, bpc=4, kp=300e-6, ki=10e-6, m_dec=16, lat=5, ppm=0.0, ssc=0.0, ssc_f=33e3,
        sj_ui=0.0, sj_f=1e6, rj_ui=0.02, isi_ui=0.088, ring_rw_ps=0.6, ptrim_ui=0.033, half_eye=0.42,
        n_cyc=150_000, settle=30_000, seed=1, phase0=0.4, fll_res_ppm=1000.0, pump_offset=0.0,
        int_lat=None, density=0.5, int_mode='dec', tau_avg=32.0, ki_rate=0.8e-6, vsat=0.5,
        vote_bias=0.0, kz=0.0, ota_tau=0.0, inj_alt_ppm=0.0, inj_tau=8.0):
    """pump_offset: fraction of one integral packet delivered (signed) on every packet regardless of
    sign (switch-charge error that survives decimation).
    int_mode='analog' (r-pi choice): net votes (+ vote_bias, in vote units: switch injection and OTA
    offset referred to the averaging node) -> first-order RC average with tau_avg ring cycles -> OTA
    (tanh, saturating at +-vsat vote units) -> integral node slews ki_rate (fraction) per ring cycle at
    full output.  kz: OTA current also crosses the 20 kOhm filter R -> extra frequency term kz*tanh
    (fraction) on VCTRL (lagging proportional term).  ota_tau (ring cycles, r9): first-order lag of the OTA
    output (the nA OTA's internal mirror pole; 0 = none).
    inj_alt_ppm (r7ring, measured): fast-tune switch injection = ring frequency offset (ppm) that appears when ALL
    bpc vote legs change state every ring cycle with net-zero votes (FU/FD alternation bench).  Modelled as a
    frequency term proportional to the vote-leg activity (legs whose vote changed vs the previous cycle / bpc),
    low-pass filtered with inj_tau ring cycles (the charge recovers through the steered/source node).  It is
    data-dependent (transition density), so the integral path cannot treat it as a constant.  Returns dict."""
    rng = np.random.default_rng(seed)
    T = 1 / f_ring
    rw = ring_rw_ps * 1e-12 * f_ring * bpc            # UI per ring cycle (rms)
    f_int = (ppm + fll_res_ppm) * 1e-6                 # integral node, fractional VCO offset
    phi = phase0
    pend = [0] * lat
    acc = 0
    acc_n = 0
    int_pend = []
    il = int_lat if int_lat is not None else 2
    prev = 0
    worst = 0.0
    errs = 0
    ber_sum = 0.0
    nbits = 0
    phis = []
    y = 0.0
    inj = 0.0
    legs_prev = [0] * bpc
    leg_pend = [[0] * bpc for _ in range(lat)]
    for n in range(n_cyc):
        t = n * T
        fr = ppm * 1e-6
        if ssc:
            ph = (t * ssc_f) % 1.0
            fr += -ssc * 1e-6 * (2 * ph if ph < 0.5 else 2 * (1 - ph))
        net = pend.pop(0)
        legs = leg_pend.pop(0)
        if inj_alt_ppm:
            act = sum(a != b for a, b in zip(legs, legs_prev)) / bpc
            inj += (act * inj_alt_ppm * 1e-6 - inj) / inj_tau
        legs_prev = legs
        if int_mode == 'analog':
            acc = acc + (net + vote_bias - acc) / tau_avg          # RC averaging node (vote units)
            y0 = math.tanh(acc / vsat)
            y = y0 if not ota_tau else y + (y0 - y) / ota_tau
            f_int += ki_rate * y
            fvco = f_int + kz * y + kp * net + inj
        else:                                                      # decimated sign packets
            acc += net
            acc_n += 1
            if acc_n == m_dec:
                s = (acc > 0) - (acc < 0)
                int_pend.append((n + il, s))
                acc = 0
                acc_n = 0
            while int_pend and int_pend[0][0] <= n:
                _, s = int_pend.pop(0)
                if s:
                    f_int += ki * s + ki * pump_offset
            fvco = f_int + kp * net + inj
        phi += (fvco - fr) * bpc + rng.normal(0, rw)
        sj = sj_ui * math.sin(2 * math.pi * sj_f * t)
        vote = 0
        lv = [0] * bpc
        for k in range(bpc):
            b = prev ^ 1 if rng.random() < density else prev    # transition density
            trans = b != prev
            isi = (isi_ui / 2) * (1 if rng.random() < 0.5 else -1) if trans else 0.0
            det = phi + sj + ptrim_ui + isi
            e = det + rng.normal(0, rj_ui)
            if n >= settle:
                nbits += 1
                ber_sum += qfunc((half_eye - abs(phi + sj + ptrim_ui) - isi_ui / 2) / rj_ui)
                if abs(e) > half_eye:
                    errs += 1
            if trans:
                vote += 1 if e > 0 else -1     # late (+) -> UP -> speed up
                lv[k] = 1 if e > 0 else -1
            prev = b
        # phi counts sampling lag; fvco here is the lag rate, so UP (late) enters as -vote
        pend.append(-vote)
        leg_pend.append(lv)
        if n >= settle:
            a = abs(phi + sj)
            worst = max(worst, a)
            if n % 50 == 0:
                phis.append(phi)
    ber = ber_sum / max(nbits, 1)
    pk = float(np.percentile(np.abs(np.array(phis) - np.mean(phis)), 99.9)) if phis else None
    return dict(bits=nbits, errors=errs, ber_stat=ber, worst_phase_ui=round(worst, 4),
                dither_p999_ui=round(pk, 4) if pk is not None else None,
                mean_phase_ui=round(float(np.mean(phis)), 4) if phis else None)


PCIE_G1_MASK = [(0.1e6, 2.0), (0.5e6, 0.6), (1.5e6, 0.3), (5e6, 0.15), (15e6, 0.15)]   # SJ amplitude (UI), same corners as cdr_model.py (0.1/1.5/5 MHz) plus 0.5 and 15 MHz


def jtol_margin(kw, f_sj, a_mask, n_cyc=80_000):
    """Largest SJ amplitude multiplier (x mask) with ber_stat < 1e-12 (bisection on 0.25..8)."""
    lo, hi = 0.0, 8.0
    for _ in range(7):
        mid = (lo + hi) / 2 if hi < 8 else (lo * 2 if lo else 1.0)
        r = run(**{**kw, 'sj_ui': a_mask * mid, 'sj_f': f_sj, 'n_cyc': n_cyc, 'settle': 20_000})
        ok = r['ber_stat'] < 1e-12 and r['errors'] == 0
        if ok:
            lo = mid
        else:
            hi = mid
        if hi >= 8 and lo >= 4:
            break
    return lo


CASES = {
    'static_+600': dict(ppm=600),
    'static_-5600': dict(ppm=-5600),
    'fll_res_-1000': dict(ppm=-5600, fll_res_ppm=-1000),
    'ssc_5000': dict(ssc=5000, n_cyc=300_000),
    'ssc_5000_+600': dict(ssc=5000, ppm=600, n_cyc=300_000),
    'pump_offset_0.5': dict(ppm=600, pump_offset=0.5),
}


def suite(base, cases=CASES):
    return {k: run(**{**base, **kw}) for k, kw in cases.items()}


def main():
    base = dict(kp=300e-6, ki=10e-6, m_dec=16, lat=5)
    out = {'base': base}
    out['cases'] = suite(base)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
