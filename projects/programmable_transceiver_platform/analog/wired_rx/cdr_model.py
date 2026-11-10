#!/usr/bin/env python3
"""AC-3 CDR loop sizing model (behavioural, NOT circuit evidence).

Per-ring-cycle bang-bang (Alexander) CDR: bpc data + bpc edge samples per ring cycle, votes summed in
current by unit pump legs on the pll_ring loop filter (VCTRL node: R gives the proportional path, C1
integrates; C2 ripple cap ignored).  The PFD is held off from power-up (pll_ring HOLD=1) and frequency
acquisition uses the RTL FLL on the same pump, so the integral node never changes hands (no HOLD
hand-over).  Votes act after `lat` ring cycles.

Checks (each can fail): BER bound over the simulated bits, SSC tracking (0..-5000 ppm, 33 kHz) with a
+600/-5600 ppm static offset, sinusoidal jitter tolerance against the PCIe-style mask, CID run.
Outputs generated/cdr-model.json.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
KVCO = 0.64e9      # Hz/V near 625 MHz (pll_ring evidence)
R, C1 = 20e3, 8.8e-12


def run(f_ring=625e6, bpc=4, i_leg=8e-9, lat=6, ppm=0.0, ssc=0.0, sj_ui=0.0, sj_f=1e6, rj_ui=0.02,
        isi_ui=0.0, n_cyc=200_000, cid=0, seed=1, phase0=0.3, fll_res_ppm=1000.0, settle=20_000):
    """Return dict with errors, worst |phase error| (UI).  Phase in UI, + = sampling late."""
    rng = np.random.default_rng(seed)
    T = 1 / f_ring
    f_bit = f_ring * bpc
    dv_p = i_leg * R                      # V per voting leg (held one ring cycle)
    dv_i = i_leg * T / C1                 # V integrated per leg-cycle
    # FLL hands over (same pump, no switch) with the integral node at the line offset + residual error
    v_int = (ppm + fll_res_ppm) * 1e-6 * f_ring / KVCO
    phi = phase0
    pend = [0] * lat
    errs = 0
    bits = 0
    worst = 0.0
    prev = rng.integers(0, 2)
    run_len = 0
    for n in range(n_cyc):
        t = n * T
        # line frequency offset (fraction): static + SSC triangle 0..-ssc
        fr = ppm * 1e-6
        if ssc:
            ph = (t * 33e3) % 1.0
            fr += -ssc * 1e-6 * (2 * ph if ph < 0.5 else 2 * (1 - ph))
        net = pend.pop(0)
        v_int += net * dv_i
        fvco = (v_int + net * dv_p) * KVCO / f_ring        # fractional VCO error vs nominal
        sj = sj_ui * math.sin(2 * math.pi * sj_f * t)
        # sampling phase drifts by (vco - line) fraction * bpc UI per ring cycle
        phi += (fvco - fr) * bpc
        vote = 0
        for k in range(bpc):
            if cid and (n * bpc + k) % 1000 < cid:
                b = prev
            else:
                b = int(rng.integers(0, 2))
            j = rng.normal(0, rj_ui) + sj + (isi_ui if b != prev else 0)
            e = phi + j                     # data sampler offset from eye centre (UI)
            bits += 1
            if abs(e) > 0.5 and n >= settle:
                errs += 1
            if b != prev:                   # transition: edge sample before vs after the boundary
                vote += 1 if (e + 0.5) > 0.5 else -1     # late -> edge sees new bit -> speed up (UP)
            prev = b
        pend.append(-vote)                  # UP raises VCTRL... sign: late phase -> speed VCO -> phi decreases
        if n >= settle:
            worst = max(worst, abs(phi + sj))
    return dict(bits=bits - settle * bpc, errors=errs, worst_phase_ui=round(worst, 4),
                ber95=(3.0 / (bits - settle * bpc) if errs == 0 else None))


def bandwidth_estimate(i_leg, f_ring=625e6, bpc=4, sigma=0.05, rho=0.5):
    """Linearised BB loop: K_pd = 2/(sqrt(2 pi) sigma) per transition."""
    kpd = 2 / (math.sqrt(2 * math.pi) * sigma)
    dfr = i_leg * R * KVCO / f_ring        # fractional freq per net leg vote
    w = kpd * rho * dfr * f_ring * bpc     # rad/s per UI ... phase in UI, per second (bpc votes/cycle)
    return w / (2 * math.pi)


def main():
    out = {}
    out['bw_MHz'] = {f'{i * 1e9:.0f}nA': round(bandwidth_estimate(i) / 1e6, 2) for i in (2e-9, 4e-9, 8e-9, 16e-9, 32e-9)}
    cases = {
        'static_+600': dict(ppm=600),
        'static_-5600': dict(ppm=-5600),
        'static_-5600_fll-1000': dict(ppm=-5600, fll_res_ppm=-1000),
        'ssc_5000_offset+600': dict(ssc=5000, ppm=600, n_cyc=400_000),
        'ssc_5000': dict(ssc=5000, n_cyc=400_000),
        'cid40': dict(cid=40),
    }
    for f_sj, a in ((0.1e6, 2.0), (1.5e6, 0.3), (5e6, 0.15)):   # PCIe-like mask corners, at 2 MHz-class gain
        cases[f'sj_{f_sj / 1e6:g}MHz_{a}UI'] = dict(sj_ui=a, sj_f=f_sj)
    res = {k: run(**{'i_leg': 32e-9, **kw}) for k, kw in cases.items()}
    out['cases'] = res
    out['pass'] = all(r['errors'] == 0 for r in res.values())
    out['note'] = 'behavioural model only; i_leg=32 nA/leg (about 2 MHz at 0.05 UI rms), lat=6 ring cycles, rj 0.02 UI rms; sizing, not qualification'
    (HERE / 'generated' / 'cdr-model.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))
    return 0 if out['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
