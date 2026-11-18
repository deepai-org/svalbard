#!/usr/bin/env python3
"""pad_hspad benches for the R-aware comparison (same infrastructure as scratch/pads-core/hspad/hs_bench.py: stress_safe_clamp /
stress_safe_family_sims, project sim image, one ngspice at a time).
  rbench.py term <model> <tag>                      small-signal termination vs code 0..15 at the 5 corners: per leg (P, N) and
                                                    differential, DC, +-10 mV about VCM 0.4 V (two pad instances, swept code)
  rbench.py ac <model> <tag> pr:T:vdd:code[,...]    hs_bench 'ac' at the given corner/code list (+ per-leg P/N C, RL min 0.1-1.25 GHz)
  rbench.py rxpath <model> <tag> pr:T:vdd:code[,...]
Output: bench/<tag>-<part>.json (model sha inside). Raw waveforms are deleted."""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/pads-pd21')
import stress_safe_clamp as s, stress_safe_family_sims as f
HERE = Path(__file__).resolve().parent
part, model, tag = sys.argv[1], Path(sys.argv[2]).resolve(), sys.argv[3]
W = HERE / 'bench' / tag
f.DRAWN_SHUNT = True
f.FAMILIES['hs'] = dict(model=model, lifecycle=None)
text, cell, ports = f.model_text('hs')
VCM = 0.4
CORNERS = (('typical', 27, 3.3), ('ss', 32, 3.15), ('ss', 32, 3.5), ('ff', 22, 3.35), ('ff', 22, 3.63))
clist = [(a, int(b), float(c), int(d)) for a, b, c, d in (x.split(':') for x in sys.argv[4].split(','))] if len(sys.argv) > 4 else None

def inst(name, padp, padn):
    m = {'ATB_ESD_RAIL': 'ATB', 'PAD_P': padp, 'PAD_N': padn, 'RX_P': f'RXP{name}', 'RX_N': f'RXN{name}'}
    d = f'X{name} ' + ' '.join(m.get(p, p) for p in ports) + f' {cell}\n'
    for q in (f'RXP{name}', f'RXN{name}'): d += f'C{q} {q} 0 120f\nR{q} {q} 0 1g\n'
    return d

def controls(vdd, code=None, vcm=VCM):
    d = f'VDD VDD 0 {vdd}\nVSS VSS 0 0\nRATB ATB 0 10meg\nVTERM_VCM TERM_VCM 0 {vcm}\nVTERM_ENABLE TERM_ENABLE 0 {vdd}\nVVBIAS VBIAS 0 1.0\n'
    for k in range(4):
        if code is None: d += f'BTRIM{k} TERM_TRIM{k} 0 V = {vdd} * (floor((v(code)+0.5)/{1 << k}) - 2*floor((v(code)+0.5)/{2 << k}))\n'
        else: d += f'VTERM_TRIM{k} TERM_TRIM{k} 0 {vdd if code >> k & 1 else 0}\n'
    return d

out = dict(model=str(model), model_sha256=s.sha(model))
if part == 'term':
    DV = 0.01; out['term'] = {}
    for pr, t, vdd in CORNERS:
        name = f'term_{pr}_{t}_{vdd}'
        d = f.header() + text + controls(vdd) + 'Vcode code 0 0\nRcode code 0 1k\n'
        d += f'VPA PA 0 {VCM + DV}\nVNA NA 0 {VCM - DV}\nVPB PB 0 {VCM - DV}\nVNB NB 0 {VCM + DV}\n' + inst('A', 'PA', 'NA') + inst('B', 'PB', 'NB')
        d = s.corner(d, pr, t) + s.control(W, name, 'dc Vcode 0 15 1', 'i(VPA) i(VNA) i(VPB) i(VNB)')
        x = np.atleast_2d(s.run(W, name, d, timeout_s=3600))
        ipa, ina, ipb, inb = (-x[:, k] for k in (1, 2, 3, 4))
        rp = 2 * DV / (ipa - ipb); rn = 2 * DV / (inb - ina); rd = 4 * DV / (((ipa - ina) - (ipb - inb)) / 2)
        out['term'][f'{pr}_{t}_{vdd}'] = dict(code=list(range(16)), r_p=rp.round(3).tolist(), r_n=rn.round(3).tolist(), r_diff=rd.round(3).tolist())
        print(pr, t, vdd, 'Rdiff', rd.round(1).tolist(), 'P-N at code 8', round(float(rp[8] - rn[8]), 3), flush=True)
elif part == 'ac':
    import rl_cob as r
    out['ac'] = {}
    for pr, t, vdd, code in clist:
        name = f'ac_{pr}_{t}_{vdd}_{code}'
        d = f.header() + text + controls(vdd, code) + f'VACP PAD_P 0 DC {VCM} AC 0.5\nVACN PAD_N 0 DC {VCM} AC -0.5\n' + inst('A', 'PAD_P', 'PAD_N')
        d = s.corner(d, pr, t) + s.control(W, name, 'ac lin 59 0.1e9 3e9', 'i(VACP) i(VACN)')
        x = np.atleast_2d(s.run(W, name, d, timeout_s=1800))
        fr = x[:, 0]; ip = -(x[:, 1] + 1j * x[:, 2]); inn = -(x[:, 3] + 1j * x[:, 4])
        zd = 1.0 / ((ip - inn) / 2); rl = -20 * np.log10(np.abs((zd - 100) / (zd + 100)))
        cleg = 2 * (1 / zd).imag / (2 * np.pi * fr); zleg = zd / 2
        cp = (ip / 0.5).imag / (2 * np.pi * fr) * 1e15; cn = (inn / -0.5).imag / (2 * np.pi * fr) * 1e15
        rpl = 1 / (ip / 0.5).real; rnl = 1 / (inn / -0.5).real
        pick = lambda a, q: float(np.interp(q, fr, a))
        cob = {}
        for db in (-0.3, 0.0, 0.3):
            p = r.geo(dbond=db)
            zf = lambda q: complex(np.interp(q, fr, zleg.real), np.interp(q, fr, zleg.imag))
            cob[str(db)] = (round(min(r.rl(r.chain(p, q), zf(q)) for q in r.F_LO), 2), round(min(r.rl(r.chain(p, q), zf(q)) for q in r.F_HI), 2))
        out['ac'][f'{pr}_{t}_{vdd}'] = dict(code=code, rdiff_100MHz=round(float(zd[0].real), 2),
            c_leg_pF={f'{q/1e9:g}GHz': round(pick(cleg, q) * 1e12, 3) for q in (0.5e9, 1.25e9, 2.4e9)},
            c_p_n_fF_0p5GHz=[round(pick(cp, 0.5e9), 1), round(pick(cn, 0.5e9), 1)], r_p_n_parallel_100MHz=[round(float(rpl[0]), 3), round(float(rnl[0]), 3)],
            die_rl_dB={f'{q/1e9:g}GHz': round(pick(rl, q), 2) for q in (0.1e9, 0.625e9, 1.25e9, 1.5e9, 2.4e9, 3e9)},
            die_rl_min_0p1_1p25=round(float(rl[fr <= 1.25e9].min()), 2), die_rl_min_1p2_2p4=round(float(rl[(fr >= 1.2e9) & (fr <= 2.4e9)].min()), 2),
            cob_rl_min_lo_hi_by_bond=cob)
        print(pr, t, vdd, {k: v for k, v in out['ac'][f'{pr}_{t}_{vdd}'].items()}, flush=True)
elif part == 'rxpath':
    out['rxpath'] = {}
    for pr, t, vdd, code in clist:
        name = f'rx_{pr}_{t}_{vdd}_{code}'
        d = f.header() + text + controls(vdd, code) + f'VSP SP 0 DC {VCM} AC 0.5\nVSN SN 0 DC {VCM} AC -0.5\nRSP SP PAD_P 50\nRSN SN PAD_N 50\n' + inst('A', 'PAD_P', 'PAD_N')
        d = s.corner(d, pr, t) + s.control(W, name, 'ac dec 10 1e4 3e9', 'v(RXPA) v(RXNA) v(PAD_P) v(PAD_N)')
        x = np.atleast_2d(s.run(W, name, d, timeout_s=1800))
        fr = x[:, 0]; p = x[:, 1] + 1j * x[:, 2]; n = x[:, 3] + 1j * x[:, 4]; rx = p - n; pad = (x[:, 5] + 1j * x[:, 6]) - (x[:, 7] + 1j * x[:, 8])
        g = 20 * np.log10(np.abs(rx / pad)); gs = 20 * np.log10(np.abs(rx)); bal = 20 * np.log10(np.abs(p + n) / np.abs(p - n) + 1e-12)
        f3 = float(fr[np.argmax(g > g[np.argmin(np.abs(fr - 1e8))] - 3)])
        out['rxpath'][f'{pr}_{t}_{vdd}'] = dict(code=code, rx_over_pad_dB={f'{q:g}': round(float(np.interp(q, fr, g)), 3) for q in (1e6, 1e8, 1.25e9, 2.4e9)},
            rx_over_source_dB={f'{q:g}': round(float(np.interp(q, fr, gs)), 3) for q in (1e8, 1.25e9, 2.4e9)},
            rx_common_over_diff_dB={f'{q:g}': round(float(np.interp(q, fr, bal)), 1) for q in (1e8, 1.25e9, 2.4e9)}, hpf_minus3dB_hz=f3)
        print(pr, t, vdd, out['rxpath'][f'{pr}_{t}_{vdd}'], flush=True)
(HERE / 'bench').mkdir(exist_ok=True)
(HERE / 'bench' / f'{tag}-{part}.json').write_text(json.dumps(out, indent=1))
for q in W.glob('*.dat'): q.unlink()
