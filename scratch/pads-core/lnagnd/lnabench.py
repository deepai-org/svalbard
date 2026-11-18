#!/usr/bin/env python3
"""Sensitivity bench: a GENERIC pseudo-differential cascode CS LNA (not the rf_rx netlist, which is being redesigned) behind the
coupled bond-wire model of bondl.py.  Purpose: size of the effect of the standard-finger ground on differential gain, NF,
common-mode input resistance and on the conversion of die-VSS bounce into a differential input signal, for RF_RX on bonds
69/70 (option A, today) and 67/68 (option B).  Runs inside the pinned tool image:  ../dock.sh 'cd /work/lnagnd && python3 lnabench.py'
DECLARED BEFORE THE RUNS (2026-11-18):
  known answer   bond network alone (no LNA, pads open): V(padP-padN)/V(die VSS) from ngspice = numpy solve of the same L matrix within 0.2 dB
  negative ctl   all mutual inductances to the RX wires removed: bounce conversion at the open pads must fall below -80 dB
  plan limits    vs the ideal-ground case: |differential gain change| <= 0.5 dB, NF change <= 0.2 dB (cases A and B, min/nom/max);
                 option B must be >= 6 dB better than A in bounce conversion at nominal, else the move has no case.
                 Common-mode Re(Zin) is reported (rf_rx owns the limit: >= +1.0 ohm)."""
import json, math, os, subprocess, sys
import numpy as np
import bondl as b
HERE = os.path.dirname(os.path.abspath(__file__)); PDK = '/foss/pdks/gf180mcuD'; MOD = f'{PDK}/libs.tech/ngspice/sm141064.ngspice'
F0 = 2.42e9
OPT = {'A': dict(rx=(70, 69)), 'B': dict(rx=(68, 67))}
GND = [63, 71, 73]; SUP = [64, 72, 74]                 # west bonds modelled individually; 57 + the 6 other ground bonds lumped (uncoupled)
R_BOND = 0.25; L_GND_REST = 2.2 / 7; L_SUP_REST = 2.3 / 5; L_SUP_BOARD = 1.2   # nH: remaining ground / supply bonds in parallel; trace + via + 0201 ESL per supply finger
def Lmat(case, bonds):
    p = b.CASES[case]; wires = [b.wire_segs(b.W0[k]['src'], b.W0[k]['dst'], p['h'], p['f'], p['H']) for k in bonds]
    return b.matrix(wires, p['zpl'])
def bond_net(case, opt, couple_rx=True, ideal=False):
    """returns deck lines. Nodes: bp bn (board side of the RX bonds), padp padn (die side), vss (die VSS), vdd (die supply), 0 = board ground."""
    if ideal: return ['Lp bp padp 1.67n', 'Ln bn padn 1.67n', 'Rvss vss 0 1u', 'Rvdd vdd 0 1u'], None, None
    P, N = OPT[opt]['rx']; bonds = [P, N] + GND + SUP; L = Lmat(case, bonds); d = []
    nd = {P: ('bp', 'padp'), N: ('bn', 'padn')}
    for k in GND: nd[k] = ('0', 'vss')
    for k in SUP: nd[k] = (f'sb{k}', 'vdd'); d.append(f'Lsb{k} sb{k} 0 {L_SUP_BOARD}n')
    for i, k in enumerate(bonds): d += [f'Lb{k} {nd[k][0]} m{k} {L[i, i]:.5f}n', f'Rb{k} m{k} {nd[k][1]} {R_BOND}']     # 0.8 mil Al wire: 0.25 ohm (also breaks the DC inductor loops)
    for i, k in enumerate(bonds):
        for j in range(i + 1, len(bonds)):
            if not couple_rx and (i < 2) != (j < 2): continue       # negative control: nothing couples to the RX wires (P-N coupling kept)
            d.append(f'Kb{k}_{bonds[j]} Lb{k} Lb{bonds[j]} {L[i, j] / math.sqrt(L[i, i] * L[j, j]):.6f}')
    d += [f'Lgrest vss mgr {L_GND_REST:.4f}n', f'Rgrest mgr 0 {R_BOND / 7:.4f}', f'Lsrest vdd sbr {L_SUP_REST:.4f}n', f'Lsbr sbr msr {L_SUP_BOARD / 5:.4f}n', f'Rsrest msr 0 {R_BOND / 5:.4f}']
    return d, L, bonds
HDR = [f'.include {PDK}/libs.tech/ngspice/design.ngspice', f'.lib {MOD} typical', f'.lib {MOD} res_typical', f'.lib {MOD} mimcap_typical', '.temp 27', '.option rshunt=1e12']
def lna():
    d = ['* generic pseudo-differential cascode CS LNA: 450/0.28 per leg (50 x 9 um), cascode 396/0.28, 0.47 nH + 1.9 ohm degeneration to die VSS, tank 1.4 nH Q 6',
         'Vsup vf vss 3.3', 'Lfeed vf vl 1', 'Rsw vdd vx 2', 'Cblk vx vl 1', 'Cl vl vss 100p', 'Cdec vdd vss 200p',   # LNA rail vl: island switch 2 ohm from the die supply, 100 pF local decap; DC through an AC-open feed
         'Ib vl vgr 140u', 'XMr vgr vgr vss vss nfet_03v3 w=9u l=0.28u m=1', 'Cvg vgr vss 10p',
         'Rc1 vl vcas 14k', 'Rc2 vcas vss 14k', 'Ccas vcas vss 10p']
    for s in 'pn':
        d += [f'Cpad{s} pad{s} vss 0.35p', f'Rb{s} vgr g{s} 60k', f'Cin{s} pad{s} g{s} 5p', f'Rg{s} g{s} gi{s} 10',
              f'XM1{s} x{s} gi{s} s{s} vss nfet_03v3 w=9u l=0.28u m=50', f'Ldeg{s} s{s} sr{s} 0.47n', f'Rdeg{s} sr{s} vss 1.9',
              f'XM2{s} out{s} vcas x{s} vss nfet_03v3 w=9u l=0.28u m=44',
              f'Lt{s} out{s} tr{s} 1.4n', f'Rt{s} tr{s} vl 3.5', f'Ct{s} out{s} vl {{ct}}']
    return d
def run(name, lines):
    open(f'{HERE}/run/{name}.sp', 'w').write('\n'.join([f'* {name}'] + lines) + '\n.end\n')
    r = subprocess.run(['ngspice', '-b', f'{HERE}/run/{name}.sp'], capture_output=True, text=True, timeout=600)
    open(f'{HERE}/run/{name}.log', 'w').write(r.stdout[-20000:] + r.stderr[-4000:])
    return r.stdout
def meas(out, key):
    for l in out.splitlines():
        if l.strip().lower().startswith(key.lower() + ' '):
            try: return float(l.split('=')[1].split()[0])
            except ValueError: return float('nan')
    return float('nan')
os.makedirs(f'{HERE}/run', exist_ok=True); res = {}
# ---------- known answer + negative control: bond network alone
for opt in OPT:
    for tag, cr in (('known', True), ('negctl', False)):
        net, L, bonds = bond_net('nom', opt, couple_rx=cr)
        d = HDR + net + ['Rbp bp 0 1e9', 'Rbn bn 0 1e9', 'Rpp padp 0 1e9', 'Rpn padn 0 1e9', 'Cdec vdd vss 200p', 'Iinj 0 vss AC 1',
                         '.control', f'ac lin 1 {F0} {F0}', 'let conv = db(mag((v(padp)-v(bp)-v(padn)+v(bn))/v(vss)) + 1e-12)', 'print conv', '.endc']
        o = run(f'{tag}_{opt}', d); got = meas(o, 'conv')
        # numpy: unknown bond currents, die VSS / VDD node voltages; RX wires open (i = 0); EMF_k = jw sum M_kj i_j
        w = 2 * math.pi * F0; n = len(bonds); G = [2 + i for i in range(len(GND))]; S = [2 + len(GND) + i for i in range(len(SUP))]
        Z = 1j * w * L * 1e-9 + R_BOND * np.eye(n); idx = G + S; A = np.zeros((len(idx) + 2, len(idx) + 2), complex); rhs = np.zeros(len(idx) + 2, complex)
        zrest_g = 1j * w * L_GND_REST * 1e-9 + R_BOND / 7; zrest_s = 1j * w * (L_SUP_REST + L_SUP_BOARD / 5) * 1e-9 + R_BOND / 5; zc = 1 / (1j * w * 200e-12)
        for a, i in enumerate(idx):                     # branch equation: v_die_node = sum_j Z_ij i_j (+ board L for supplies); currents flow die -> board
            for c, j in enumerate(idx): A[a, c] = Z[i, j]
            if i in S: A[a, a] += 1j * w * L_SUP_BOARD * 1e-9; A[a, len(idx) + 1] = -1
            else: A[a, len(idx)] = -1
        ng = len(G)   # KCL at vss: 1 A in = sum i_gnd + vss/zrest_g + (vss - vdd)/zc ; at vdd: (vss - vdd)/zc = sum i_sup + vdd/zrest_s
        A[len(idx), :ng] = 1; A[len(idx), len(idx)] = 1 / zrest_g + 1 / zc; A[len(idx), len(idx) + 1] = -1 / zc; rhs[len(idx)] = 1
        A[len(idx) + 1, ng:len(idx)] = 1; A[len(idx) + 1, len(idx)] = -1 / zc; A[len(idx) + 1, len(idx) + 1] = 1 / zrest_s + 1 / zc
        x = np.linalg.solve(A, rhs); cur = x[:len(idx)]; vss = x[len(idx)]
        emf = sum((Z[0, i] - Z[1, i]) * c for i, c in zip(idx, cur)) if cr else 0    # RX wires carry no current: their own R and L drop nothing
        ref = 20 * math.log10(abs(emf / vss)) if cr else float('-inf')
        res[f'{tag}_{opt}'] = dict(ngspice_dB=got, numpy_dB=ref); print(tag, opt, 'ngspice', round(got, 2), 'numpy', round(ref, 2) if cr else ref, flush=True)
# ---------- LNA runs
SRC = lambda lm: ['Vsp ep 0 DC 0 AC 0.5', 'Vsn en 0 DC 0 AC -0.5', 'Rsp ep mp 50', 'Rsn en mn 50', f'Lmp mp bp {lm}n', f'Lmn mn bn {lm}n']
def lna_case(name, net, lm, ct):
    base = HDR + [f'.param ct={ct}p'] + net + lna()
    # 1 differential gain + NF
    d = base + SRC(lm) + ['.control', 'ac lin 81 1.6e9 3.2e9', 'let g = db(mag(v(outp)-v(outn)))', 'let gp = db(mag(v(padp)-v(padn)))',
        f'meas ac g0 find g at={F0}', 'meas ac gpk max g', 'meas ac fpk when g=gpk', f'meas ac gpad find gp at={F0}',
        f'noise v(outp,outn) Vsp lin 1 {F0} {F0}', 'setplot noise1', 'print onoise_spectrum', '.endc']
    o = run(name + '_dm', d); g0 = meas(o, 'g0'); nout = meas(o, 'onoise_spectrum')
    # NF: noise is referred to Vsp alone (AC 0.5 of the 1 V differential EMF): F = onoise^2 / (4kT * 100 ohm * |Gdiff|^2)
    nf = 10 * math.log10(nout ** 2 / (4 * 1.380649e-23 * 300.15 * 100 * (10 ** (g0 / 20)) ** 2))
    # 2 common-mode input impedance seen from the board side of the pair (both legs driven in phase against board ground, match inductors included)
    d = base + ['Icm 0 cm AC 1', f'Lmp cm bp {lm}n', f'Lmn cm bn {lm}n', '.control', 'ac dec 60 1e8 3e10', 'let r = real(v(cm))',
                'meas ac rmin min r', 'meas ac frmin when r=rmin', f'meas ac r24 find r at={F0}', '.endc']
    o2 = run(name + '_cm', d)
    # 3 die-VSS bounce -> differential output, referred to the differential source EMF
    d = base + ['Rsp mp 0 50', 'Rsn mn 0 50', f'Lmp mp bp {lm}n', f'Lmn mn bn {lm}n', 'Iinj 0 vss AC 1', '.control', f'ac lin 1 {F0} {F0}',
                'let t = db(mag((v(outp)-v(outn))/v(vss)))', 'print t', '.endc']
    o3 = run(name + '_bn', d); t = meas(o3, 't')
    r = dict(gain_dB=g0, gain_peak_dB=meas(o, 'gpk'), f_peak=meas(o, 'fpk'), gain_to_pad_dB=meas(o, 'gpad'), nf_dB=nf,
             cm_re_min_ohm=meas(o2, 'rmin'), cm_re_min_f=meas(o2, 'frmin'), cm_re_2p42=meas(o2, 'r24'),
             bounce_to_out_dB=t, bounce_input_referred_dB=t - g0)
    res[name] = r; print(name, {k: (round(v, 3) if abs(v) < 1e6 else f'{v:.3g}') for k, v in r.items()}, flush=True); return r
ideal, _, _ = bond_net('nom', 'A', ideal=True)
LM, CT = float(sys.argv[1]) if len(sys.argv) > 1 else 4.0, float(sys.argv[2]) if len(sys.argv) > 2 else 2.8
lna_case('ideal', ideal, LM, CT)
for opt in OPT:
    for case in ('min', 'nom', 'max'):
        net, L, bonds = bond_net(case, opt); Ld = (L[0, 0] + L[1, 1]) / 2 - L[0, 1]
        lna_case(f'{opt}_{case}', net, LM + 1.67 - Ld, CT)      # the board trim re-tunes the differential series inductance to the same total
net, _, _ = bond_net('nom', 'A', couple_rx=False); lna_case('A_nom_nocoupling_negctl', net, LM + 1.67 - 2.21, CT)
res['params'] = dict(LM_nH=LM, CT_pF=CT, F0=F0, L_GND_REST=L_GND_REST, L_SUP_REST=L_SUP_REST, L_SUP_BOARD=L_SUP_BOARD)
json.dump(res, open(f'{HERE}/lnabench.json', 'w'), indent=1)
