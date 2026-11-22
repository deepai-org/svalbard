#!/usr/bin/env python3
"""em_check.py <res.json> [out.json]: per-net DC EM screen of the termination / common-mode nets (review-a12 F1, review-a13 C1).
netres must have run TU_* / TERM_VCM* with path_fraction 0.02 (fixspec11.py), so per-unit straps are in max_run_current_density_per_um.
Ratings 85 C: 0.58 mA per via cut, 2.09 mA/um (wtx_mux8_layout.py:42, DRM 14.2). Each element: worse of typ and high. Codes 0..15.
Design basis (a14, coordinator): (A) 10.5 mA per pad (data-balanced average), ratio <= 0.86 (>= 16 % margin); (B) 15.75 mA static in one leg
(far end terminated), ratio <= 1.0; (C) 21 mA static, far end open: information.
Currents per basis with pad current I: TU_x_g = I x n_g / (8 + code), max over codes 0..15 with bit g on (B always); bus path
disconnect -> group g: that group's current; TERM_VCM pin -> disconnect: 2 I for (A), I for (B)/(C); discharge path 0.2 mA."""
import json, sys
CUT, RUN = 0.58, 2.09
N = dict(B=8, T0=1, T1=2, T2=4, T3=8)
BASES = dict(A=(10.5, 2., .86), B=(15.75, 1., 1.0), C=(21., 1., None))
# --basis NAME=I_pad,k_pin,limit (repeatable; limit 'info' = no limit) replaces the defaults, e.g. 100BASE-TX:
#   --basis A100=20,2,0.86 --basis B100=30,1,1.0      (k_pin: TERM_VCM pin current = k_pin x I_pad)
import argparse as _ap
_p = _ap.ArgumentParser(); _p.add_argument('res'); _p.add_argument('out', nargs='?'); _p.add_argument('--basis', action='append', default=[])
_a = _p.parse_args(); sys.argv = [sys.argv[0], _a.res] + ([_a.out] if _a.out else [])
if _a.basis:
    BASES = {}
    for b_ in _a.basis:
        n_, v_ = b_.split('='); i_, k_, l_ = v_.split(','); BASES[n_] = (float(i_), float(k_), None if l_ == 'info' else float(l_))
def igroup(g, ipad):
    return max(ipad * N[g] / (8 + c) for c in range(16) if g == 'B' or (c >> int(g[1])) & 1)
r = json.load(open(sys.argv[1])); out = dict(res=sys.argv[1], gds_sha256=r.get('gds_sha256'), ratings=dict(mA_per_cut=CUT, mA_per_um=RUN), codes='0..15', bases={})
for b, (ipad, kpin, lim) in BASES.items():
    rows = []
    for net, nd in r['nets'].items():
        keys = set()
        for cn in ('typ', 'high'): keys |= set(nd['corners'].get(cn, {}).get('paths', {}))
        for pk in keys:
            if net.startswith('TU_'): i = igroup(net.split('_')[2], ipad)
            elif net == 'TERM_VCM_BUS':
                if not pk.startswith('nmos:TERM_VCM|'): continue
                i = igroup(pk.split('_')[-1], ipad)
            elif net == 'TERM_VCM': i = 0.2 if 'res:' in pk else kpin * ipad
            elif net in ('PAD_P', 'PAD_N'):    # review-a16: bond -> resistor heads (termination current) and bond -> cascode drains (drive current), both at I_pad
                if pk.startswith('bond|res:'): i = ipad                   # all termination units in parallel
                elif pk.startswith('bond|nmos:SUM_'): i = ipad / 8.      # one of 8 driver units (drive current)
                else: continue                                            # detect isolate (uA) and diode paths: not DC-loaded
            else: continue
            fc = dens = 0.; wc = None
            for cn in ('typ', 'high'):
                p = nd['corners'].get(cn, {}).get('paths', {}).get(pk)
                if not p: continue
                mc = p.get('max_current_fraction_per_cut')
                if isinstance(mc, dict) and mc.get('fraction', 0) > fc: fc, wc = mc['fraction'], dict(mc, corner=cn)
                dens = max(dens, p.get('max_run_current_density_per_um') or 0.)
            rows.append(dict(net=net, path=pk, i_mA=round(i, 3), per_cut_mA=round(fc * i, 3), run_mA_um=round(dens * i, 3), cut_ratio=round(fc * i / CUT, 3),
                             run_ratio=round(dens * i / RUN, 3), where_cut=wc))
    worst = max(rows, key=lambda x: max(x['cut_ratio'], x['run_ratio'])); wr = max(worst['cut_ratio'], worst['run_ratio'])
    over = [x for x in rows if lim is not None and max(x['cut_ratio'], x['run_ratio']) > lim]
    out['bases'][b] = dict(i_pad_mA=ipad, limit_ratio=lim, n_paths=len(rows), worst_ratio=wr, worst=worst, n_over=len(over), over=over,
                           per_net={n: max((x for x in rows if x['net'] == n), key=lambda x: max(x['cut_ratio'], x['run_ratio'])) for n in sorted({x['net'] for x in rows})})
    print(f"basis {b}: {ipad} mA/pad limit {lim} worst {wr:.3f} ({worst['net']} {worst['path']}) over {len(over)}")
    for n, x in out['bases'][b]['per_net'].items(): print(f"   {n:14s} I {x['i_mA']:6.2f}  cut {x['per_cut_mA']:.3f} ({x['cut_ratio']:.2f})  run {x['run_mA_um']:.2f} ({x['run_ratio']:.2f})")
if len(sys.argv) > 2: json.dump(out, open(sys.argv[2], 'w'), indent=1)
sys.exit(1 if any(v['n_over'] for v in out['bases'].values()) else 0)
