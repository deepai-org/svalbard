#!/usr/bin/env python3
"""pad_hspad termination vs trim code over the MANDATE window (pads owner, 2026-11-18). Same decks as hsfix/rbench.py `term`
(DC small signal, +-10 mV about TERM_VCM, two pad instances, code swept 0..15), more corners.
    cbench.py <model.spice> <tag> [vcm]            -> hsfix2/bench/<tag>-term.json
Corners: tt / ss / ff / sf / fs x 22, 32 C x 3.15, 3.35 V; ss also at the 3.50 V trim point; tt 27 C 3.3 V.
ss / ff move MOS, poly resistor, diode and MIM together (worst pairing for a switch + poly termination); sf / fs move the MOS only.
DECLARED BEFORE THE RUNS on the final cell:
  T-A  at every corner and both metal models (typ, high) some code gives 100 ohm +-5 % differential (95..105)
  T-B  that code lies in 2..13 (two codes of range left on both sides)
  T-C  per-leg P - N difference at that code <= 1.0 ohm
  T-D  one reset code holds 80..120 ohm at every in-window corner with typical metal (reported, also with high metal)
  negative control: TERM_ENABLE = 0 must read > 10 kohm differential; known answer: the published C-only model must
  reproduce its published table (tt code 5: 101.1 ohm, hsfix/bench/pubc-term.json)"""
import sys, json, re
from pathlib import Path
import numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/pads-pd21')
import stress_safe_clamp as s, stress_safe_family_sims as f
HERE = Path(__file__).resolve().parent
model, tag = Path(sys.argv[1]).resolve(), sys.argv[2]; VCM = float(sys.argv[3]) if len(sys.argv) > 3 else 0.4
W = HERE / 'bench' / tag
f.DRAWN_SHUNT = True; f.FAMILIES['hs'] = dict(model=model, lifecycle=None)
text, cell, ports = f.model_text('hs')
CORNERS = [('typical', 27, 3.3)] + [(p, t, v) for p in ('typical', 'ss', 'ff', 'sf', 'fs') for t in (22, 32) for v in (3.15, 3.35)] + [('ss', 22, 3.5), ('ss', 32, 3.5)]
def corner(deck, process, temp):
    if process in ('typical', 'ss', 'ff'): return s.corner(deck, process, temp)
    deck, n = re.subn(r'(sm141064\.ngspice) typical\n', rf'\1 {process}\n', deck); assert n == 1
    return deck.replace('.temp 27\n', f'.temp {temp}\n')
def inst(name, padp, padn):
    m = {'ATB_ESD_RAIL': 'ATB', 'PAD_P': padp, 'PAD_N': padn, 'RX_P': f'RXP{name}', 'RX_N': f'RXN{name}'}
    d = f'X{name} ' + ' '.join(m.get(p, p) for p in ports) + f' {cell}\n'
    for q in (f'RXP{name}', f'RXN{name}'): d += f'C{q} {q} 0 120f\nR{q} {q} 0 1g\n'
    return d
def controls(vdd, en=True):
    d = f'VDD VDD 0 {vdd}\nVSS VSS 0 0\nRATB ATB 0 10meg\nVTERM_VCM TERM_VCM 0 {VCM}\nVTERM_ENABLE TERM_ENABLE 0 {vdd if en else 0}\nVVBIAS VBIAS 0 1.0\n'
    for k in range(4): d += f'BTRIM{k} TERM_TRIM{k} 0 V = {vdd if en else 0} * (floor((v(code)+0.5)/{1 << k}) - 2*floor((v(code)+0.5)/{2 << k}))\n'
    return d
DV = 0.01; out = dict(model=str(model), model_sha256=s.sha(model), vcm=VCM, term={})
def one(pr, t, vdd, en=True):
    name = f'term_{pr}_{t}_{vdd}' + ('' if en else '_off')
    d = f.header() + text + controls(vdd, en) + 'Vcode code 0 0\nRcode code 0 1k\n'
    d += f'VPA PA 0 {VCM + DV}\nVNA NA 0 {VCM - DV}\nVPB PB 0 {VCM - DV}\nVNB NB 0 {VCM + DV}\n' + inst('A', 'PA', 'NA') + inst('B', 'PB', 'NB')
    d = corner(d, pr, t) + s.control(W, name, 'dc Vcode 0 15 1', 'i(VPA) i(VNA) i(VPB) i(VNB)')
    x = np.atleast_2d(s.run(W, name, d, timeout_s=3600))
    ipa, ina, ipb, inb = (-x[:, k] for k in (1, 2, 3, 4))
    return 2 * DV / (ipa - ipb), 2 * DV / (inb - ina), 4 * DV / (((ipa - ina) - (ipb - inb)) / 2)
for pr, t, vdd in CORNERS:
    rp, rn, rd = one(pr, t, vdd)
    out['term'][f'{pr}_{t}_{vdd}'] = dict(r_p=rp.round(3).tolist(), r_n=rn.round(3).tolist(), r_diff=rd.round(3).tolist())
    print(pr, t, vdd, 'Rdiff', rd.round(1).tolist(), flush=True)
rp, rn, rd = one('typical', 27, 3.3, en=False); out['negative_control_off_min_ohm'] = float(np.min(np.abs(rd))); print('OFF min |Rdiff|', out['negative_control_off_min_ohm'])
(HERE / 'bench').mkdir(exist_ok=True); (HERE / 'bench' / f'{tag}-term.json').write_text(json.dumps(out, indent=1))
for q in W.glob('*.dat'): q.unlink()
