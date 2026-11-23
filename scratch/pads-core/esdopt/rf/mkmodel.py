#!/usr/bin/env python3
"""mkmodel.py <flat.spice> <netres json> <corner typ|high> <out> <legs P,N> <n_dn per site> [--erail P=16.1,N=19.7]
Lumped R + C ESD model of an rf-shell option-A candidate (form read by esd3.py):
  wrapper  .subckt rf_pad PAD_P [PAD_N] VSS [DVDD] ATB_ESD_RAIL   (ESD_RAIL is internal: pad-local in the chip)
  inner    .subckt physical <flat ports incl. ESD_RAIL>  = the Magic cthresh-0 extraction (all devices, all C lines), with
           site down-diodes on PAD_x__dn (anode VSS__ax), site up-diodes on PAD_x__up (cathode DVDD__kx), core-array diodes on PAD_x__core,
           core-array rail diodes' cathodes on ESD_RAIL__kx, every other VSS terminal of the network on VSS__net, and the resistors
           bond->dn, bond->up, bond->core (netres, this GDS), landings->anodes / cathodes (netres), VSS__net -> ring landings (netres land|clampsrc),
           ESD_RAIL__kx -> ESD_RAIL (esdcheck REPORT Result 2: rail diodes' cathode rings -> clamp drains; netres groups them wrongly).
  C lines stay on the full nets (PAD C at the bond node). Identical diodes: the first n_dn nd2ps VSS-PAD_x of the extraction are the site ones."""
import sys, json, re
src, resf, corner, out, legs, ndn = sys.argv[1:7]; legs = legs.split(','); ndn = int(ndn)
ER = {'typ': {'P': 16.1, 'N': 19.7}, 'high': {'P': 33.5, 'N': 37.7}}[corner]   # single_leg: P 16.1 / 33.5 (same REPORT table)
rs = json.load(open(resf))['nets']
R = lambda net, pair: rs[net]['corners'][corner]['resistance_ohm'][pair]
lines = re.sub(r'\n\+\s*', ' ', open(src).read()).splitlines()
hdr = next(l for l in lines if l.startswith('.subckt')); ports = hdr.split()[2:]
body, cnt = [], {L: 0 for L in legs}
for l in lines:
    if l.startswith(('.subckt', '.ends', '*')) or not l.strip(): continue
    t = l.split()
    if t[0][0] == 'D':
        a, k, m = t[1], t[2], t[3]
        L = (a if a.startswith('PAD_') else k)[-1] if (a.startswith('PAD_') or k.startswith('PAD_')) else None
        if 'pd2nw' in m and k == 'DVDD': t[1], t[2] = f'{a}__up', f'DVDD__k{a[-1]}'
        elif 'pd2nw' in m and k == 'ESD_RAIL' and a.startswith('PAD_'): t[1], t[2] = f'{a}__core', f'ESD_RAIL__k{a[-1]}'
        elif 'nd2ps' in m and a == 'VSS' and k.startswith('PAD_'):
            if cnt[k[-1]] < ndn: t[1], t[2] = f'VSS__a{k[-1]}', f'{k}__dn'; cnt[k[-1]] += 1
            else: t[1], t[2] = 'VSS__net', f'{k}__core'
        elif 'nd2ps' in m and a == 'VSS': t[1] = 'VSS__net'; t[2] = 'VSS__net' if k == 'VSS' else k
        elif 'pd2nw' in m and a == 'VSS' and k == 'ESD_RAIL': t[1] = 'VSS__net'      # single_leg: the network's PADN side is tied to VSS
        else: raise SystemExit('unclassified diode: ' + l)
    elif t[0][0] in 'XR':
        t = [('VSS__net' if w == 'VSS' else w) for w in t]
    body.append(' '.join(t))
for L in legs:
    if cnt[L] != ndn: raise SystemExit(f'leg {L}: {cnt[L]} site down-diodes found, expected {ndn}')
for L in legs:
    p = f'PAD_{L}'
    body += [f'RBD{L} {p} {p}__dn {R(p, "bond|dn"):.4f}', f'RCORE{L} {p} {p}__core {R(p, "bond|cdn"):.4f}', f'RAS{L} VSS__a{L} VSS {R(f"VSS_SITE_{L}", "land|anodes"):.4f}',
             f'RER{L} ESD_RAIL__k{L} ESD_RAIL {ER[L]}']
    if any(f'{p}__up' in b for b in body):
        body += [f'RBU{L} {p} {p}__up {R(p, "bond|up"):.4f}', f'RKD{L} DVDD__k{L} DVDD {R(f"DVDD_{L}", "land|cath"):.4f}']
body.append(f'RNET VSS__net VSS {R("VSS_NET", "land|clampsrc"):.4f}')
wports = [p for p in ['PAD_P', 'PAD_N', 'VSS', 'DVDD', 'ATB_ESD_RAIL'] if p in ports]
txt = [f'* {out}: lumped R+C model, corner {corner}, from {src} + {resf}', f'.subckt rf_pad ' + ' '.join(wports),
       'Xphysical ' + ' '.join(p if p in wports else p for p in ports) + ' physical', '.ends rf_pad',
       '.subckt physical ' + ' '.join(ports)] + body + ['.ends physical']
open(out, 'w').write('\n'.join(txt) + '\n')
print(out, 'site dn per leg', cnt, 'lines', len(body))
