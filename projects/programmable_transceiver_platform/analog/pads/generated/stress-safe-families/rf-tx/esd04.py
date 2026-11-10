#!/usr/bin/env python3
"""ESD-04: RF_TX pad protection that stays off to >= 4.4 V at ff (rftxpad).

Candidate = the compact rf_pair extraction (pad-compact-v2/rf-pair, same steering diodes, MIMs,
RC clamp, bleed, ATB tap => same pad C) with the static 3-stage diode-connected shunt removed and
replaced by a gate-coupled nfet_06v0 shunt (GCNMOS): drain ESD_RAIL, source VSS, gate GC;
Cc (MIM) ESD_RAIL->GC, Rg (ppolyf_u_1k_6p0) GC->VSS. DC: gate held at VSS -> off at any rail
voltage below junction breakdown. Fast events: gate coupled to ~Cc/(Cc+Cg) of the rail step.
Benches: (1) DC common-mode I-V (txc.py method), (2) txc transient 3.3 V +/- 0.8 V behind 25 ohm,
(3) the family stress fixtures via stress_safe_family_sims (--models rfpad=<cand>), run separately.
"""
import sys, re, json, math, subprocess, hashlib
from pathlib import Path
import numpy as np
PADS = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
sys.path.insert(0, str(PADS))
import stress_safe_clamp as s
W = Path(__file__).resolve().parent
BASE = Path('/home/ubuntu/svalbard/scratch/pad-compact-v2/rf-pair/pad-extracted.spice')
PDK = s.SCRATCH / 'transceiver-pad-pdk/ngspice'
CLAMP_GATE = 'a_2245_90628#'
F = 2.45e9
TSTOP = 1000e-9   # rail (peak detector) settles in a few 100 ns; measure the last 24 periods

def cand(name, w_fingers=224, finger=53.6, mim=8, rg_sq=20, gc=True, out=None, base=BASE):
    t = re.sub(r'\n\+\s*', ' ', base.read_text())
    keep, removed = [], 0
    for l in t.splitlines():
        f = l.split()
        if l.startswith('X') and len(f) > 5 and f[5] == 'nfet_06v0' and 'w=50u' in l and f[2] != CLAMP_GATE:
            removed += 1; continue
        keep.append(l)
    if gc:
        add = [f'XGCN ESD_RAIL GC VSS VSS nfet_06v0 w={finger}u l=0.7u m={w_fingers}',
               f'XGCC ESD_RAIL GC cap_mim_2f0_m4m5_noshield c_width=31.6u c_length=31.6u m={mim}',
               f'XGCR GC VSS VSS ppolyf_u_1k_6p0 r_width=1u r_length={rg_sq}u']
        i = max(k for k, l in enumerate(keep) if l.startswith('.ends'))
        keep[i:i] = add
    txt = '\n'.join(keep) + '\n'
    from loading_audit import anchor_floating_conductors
    txt, _ = anchor_floating_conductors(txt, 1e12)
    p = out or (W / f'{name}.spice'); p.write_text(txt)
    return p, removed

def header(corner, temp):
    d = (f'.include {PDK}/design.ngspice\n.lib {PDK}/sm141064.ngspice typical\n.lib {PDK}/sm141064.ngspice res_typical\n'
         f'.lib {PDK}/sm141064.ngspice diode_typical\n.lib {PDK}/sm141064.ngspice mimcap_typical\n.temp 27\n')
    return s.corner(d, corner, temp)

def dc(model, corner, temp, tag):
    name = f'dc_{tag}_{corner}_{temp}'
    d = header(corner, temp) + f'.include {model}\nXP PN PP VSS ATB rf_protected_pad\nVSS VSS 0 0\nRATB ATB 0 10meg\nVP PP 0 0\nEN PN 0 PP 0 1\n'
    d += '.option method=gear reltol=1e-4 abstol=1e-13\n'
    d += s.control(W, name, 'dc VP 0 5.4 0.05', 'i(VP) v(xp.esd_rail)')
    x = s.run(W, name, d, timeout_s=1800)
    v, i = x[:, 0], -x[:, 1]
    on = next((float(v[k]) for k in range(len(v)) if i[k] > 10e-6), None)
    return dict(onset_10uA_V=on, I_uA={f'{q:.2f}': float(np.interp(q, v, i)) * 1e6 for q in (3.3, 3.35, 4.1, 4.4, 5.0)})

def tran(model, corner, temp, tag, amp=0.8, vdc=3.3):
    name = f'tr_{tag}_{corner}_{temp}_{amp}'
    d = header(corner, temp) + f'.include {model}\nXP PN PP VSS ATB rf_protected_pad\nVSS VSS 0 0\nRATB ATB 0 10meg\n'
    # DC-fed pads (balun centre tap) start at vdc; ramp the RF in over 10 ns, then 20 ns steady state.
    d += f'VSP SP 0 sin({vdc} {amp} {F} 0)\nRSP SP PP 25\nVSN SN 0 sin({vdc} {-amp} {F} 0)\nRSN SN PN 25\n'
    d += '.option method=gear reltol=1e-3\n'
    vec = 'v(PP) v(SP) v(xp.esd_rail)' + (' v(xp.xphysical.gc)' if 'gc' in tag else '')
    x = s.run(W, name, d + s.control(W, name, f'tran 2p {TSTOP*1e9:.0f}n', vec), timeout_s=3600)
    # resample onto exactly 24 RF periods (integer cycles: the reactive current averages to zero)
    tt = TSTOP - 10e-9 + np.arange(24 * 200) / (200 * F); T = 24 / F
    vp = np.interp(tt, x[:, 0], x[:, 1]); vs = np.interp(tt, x[:, 0], x[:, 2]); ic = (vs - vp) / 25.
    m = slice(None); x = np.column_stack([tt] + [np.interp(tt, x[:, 0], x[:, k]) for k in range(1, x.shape[1])])
    harm = lambda k: 2 * abs(np.trapezoid(ic * np.exp(-2j * np.pi * k * F * tt), tt)) / T
    harm = lambda k: 2 * abs(np.mean(ic * np.exp(-2j * np.pi * k * F * tt)))
    h = [harm(k) for k in (1, 2, 3)]
    # clamp HD3 relative to the delivered fundamental across the 100 ohm per-leg load (txc convention)
    return dict(pad_peak_V=float(vp.max()), pad_min_V=float(vp.min()), rail_V=float(x[:, 3].mean()),
                gc_max_V=float(x[:, 4].max()) if x.shape[1] > 4 else None,
                I_avg_uA=float(np.mean(ic)) * 1e6, P_uW_per_leg=float(np.mean(ic * vp)) * 1e6,
                I_h1_uA=h[0] * 1e6, I_h2_uA=h[1] * 1e6, I_h3_uA=h[2] * 1e6,
                HD3_dBc_at_100ohm=20 * math.log10(max(h[2] * 100, 1e-15) / amp),
                HD2_dBc_at_100ohm=20 * math.log10(max(h[1] * 100, 1e-15) / amp))

def hbm(model, corner, temp, tag, kv=2.0, leg='P', sign=1):
    """HBM-like current (compact-model diagnostic, not qualification): 2 ns rise, 150 ns decay,
    peak kv/1.5 kohm, into PAD_<leg> of an unpowered die (other leg 1 Mohm/1 pF peer, 1 nH bonds)."""
    ip = kv * 1e3 / 1500.
    name = f'hbm_{tag}_{corner}_{temp}_{kv}_{leg}_{"pos" if sign > 0 else "neg"}'
    d = header(corner, temp) + f'.include {model}\nXP PN PP VSS ATB rf_protected_pad\nVSS VSS 0 0\nRATB ATB 0 10meg\nCATB ATB 0 10p\n'
    for l in 'PN':
        d += f'R{l} B{l} 0 1meg\nC{l} B{l} 0 1p\nL{l} B{l} P{l} 1n\n'
    a, b = ('VSS', f'P{leg}') if sign > 0 else (f'P{leg}', 'VSS')
    d += f'IZ {a} {b} EXP(0 {ip} 5n 2n 15n 150n)\n.option method=gear reltol=1e-3\n'
    vec = 'v(PP) v(PN) v(xp.esd_rail)' + (' v(xp.xphysical.gc)' if 'gc' in tag else '')
    x = s.run(W, name, d + s.control(W, name, 'tran 0.05n 600n', vec), timeout_s=3600)
    r = dict(peak_A=ip, pad_peak_abs_V=float(abs(x[:, 1:3]).max()), rail_max_V=float(x[:, 3].max()))
    if x.shape[1] > 4: r['gc_max_V'] = float(x[:, 4].max())
    t = x[:, 0]; r['pad_V_at'] = {f'{q*1e9:.0f}ns': float(np.interp(q, t, x[:, 1 if leg == 'P' else 2])) for q in (20e-9, 100e-9, 300e-9, 500e-9)}
    return r

def powerup(model, corner, temp, tag, rise):
    """TX DC feed ramp: both pads 0 -> 3.3 V through 25 ohm in `rise`; peak/settled pad current."""
    name = f'pu_{tag}_{corner}_{temp}_{rise}'
    d = header(corner, temp) + f'.include {model}\nXP PN PP VSS ATB rf_protected_pad\nVSS VSS 0 0\nRATB ATB 0 10meg\n'
    d += f'VS S 0 PWL(0 0 {rise} 3.3 {3*float(rise.rstrip("u"))}u 3.3)\nRP S PP 25\nRN S PN 25\n.option method=gear reltol=1e-3\n'
    stop = 3 * float(rise.rstrip('u'))
    vec = 'v(PP) v(S) v(xp.esd_rail)' + (' v(xp.xphysical.gc)' if 'gc' in tag else '')
    x = s.run(W, name, d + s.control(W, name, f'tran {stop/3000:.4g}u {stop}u', vec), timeout_s=3600)
    i = (x[:, 2] - x[:, 1]) / 25.
    r = dict(rise=rise, I_peak_mA_per_leg=float(i.max()) * 1e3, I_end_uA=float(i[-20:].mean()) * 1e6, rail_end_V=float(x[-1, 3]))
    if x.shape[1] > 4: r['gc_max_V'] = float(x[:, 4].max())
    return r

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('--tag', default='gc'); ap.add_argument('--mim', type=int, default=8)
    ap.add_argument('--rg', type=float, default=20); ap.add_argument('--fingers', type=int, default=224)
    ap.add_argument('--parts', nargs='*', default=['dc', 'tran']); ap.add_argument('--corners', nargs='*', default=['ff:32', 'typical:27', 'ss:32'])
    ap.add_argument('--noshunt', action='store_true'); ap.add_argument('--report'); ap.add_argument('--baseline', action='store_true'); ap.add_argument('--model'); ap.add_argument('--amps', nargs='*', type=float, default=[0.8])
    a = ap.parse_args()
    if a.model:      # a drawn extraction (e.g. layout/rftxpad3/pad-extracted.spice), anchored, unchanged
        from loading_audit import anchor_floating_conductors
        model = W / f'{a.tag}.spice'; model.write_text(anchor_floating_conductors(re.sub(r'\n\+\s*', ' ', Path(a.model).read_text()), 1e12)[0]); removed = 0
    elif a.baseline:   # held compact rf_pair (static 3-stage shunt), anchored, unchanged
        from loading_audit import anchor_floating_conductors
        model = W / 'baseline_rf_pair.spice'; model.write_text(anchor_floating_conductors(re.sub(r'\n\+\s*', ' ', BASE.read_text()), 1e12)[0]); removed = 0
    else:
        model, removed = cand(a.tag, a.fingers, mim=a.mim, rg_sq=a.rg, gc=not a.noshunt)
    res = dict(model=str(model), model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(), removed_shunt_fingers=removed,
               params=dict(fingers=a.fingers, finger_um=53.6, mim_31p6=a.mim, rg_squares=a.rg, gc=not a.noshunt), results={})
    rep = Path(a.report or (W / f'{a.tag}.json'))
    for c in a.corners:
        corner, temp = c.split(':'); temp = int(temp); r = {}
        if 'dc' in a.parts: r['dc'] = dc(model, corner, temp, a.tag)
        if 'tran' in a.parts:
            r['tran'] = tran(model, corner, temp, a.tag)
            for amp in a.amps:
                if amp != 0.8: r[f'tran_amp{amp}'] = tran(model, corner, temp, a.tag, amp=amp)
        if 'hbm' in a.parts: r['hbm2kV_P_pos'] = hbm(model, corner, temp, a.tag)
        if 'powerup' in a.parts: r['powerup'] = [powerup(model, corner, temp, a.tag, q) for q in ('1u', '10u')]
        res['results'][c] = r; print(c, json.dumps(r), flush=True)
        rep.write_text(json.dumps(res, indent=1))
