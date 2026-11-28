#!/usr/bin/env python3
"""Pad reference netlist -> PDK device form for KLayout read-back LVS (PAD-17):   pad_ref_pdk.py <ref.spice> <out.spice> [top]
The pad generators write Magic-style references (X-instances of nfet_03v3 / ppolyf_u..., parasitic C lines, diode pj in
'p'). The KLayout gf180mcu LVS deck compares against M (MOS: w l), R (ppolyf_*: 3 terminals with the substrate, l w), D
(diode: A P) elements. Parasitic C are dropped (net_only extraction has none); sub-circuits are kept and flattened by
the comparer. Nothing else is changed: device count and connectivity stay those of the reference."""
import re, sys
MOS = ('nfet_03v3', 'nfet_06v0', 'nfet_06v0_nvt', 'pfet_03v3', 'pfet_06v0', 'nfet_05v0', 'pfet_05v0')
RES = ('ppolyf_u', 'ppolyf_u_1k', 'ppolyf_u_2k', 'ppolyf_s', 'ppolyf_u_1k_6p0', 'ppolyf_u_2k_6p0', 'nplus_u', 'pplus_u', 'rm1', 'rm2', 'rm3')
def num(v):
    return v
def conv(lines, sub='VSS'):
    out = []; n = 0
    for l in lines:
        t = l.split()
        if not t: out.append(l); continue
        h = t[0][0].upper()
        if h == 'C' and not t[0].upper().startswith('.'): continue
        kv = {a.split('=')[0].lower(): a.split('=')[1] for a in t if '=' in a}
        pos = [a for a in t[1:] if '=' not in a]
        if h == 'X' and pos and pos[-1] in MOS:
            d, gg, s, b = pos[:4]; n += 1
            out.append(f"M{t[0][1:]} {d} {gg} {s} {b} {pos[-1]} W={kv['w']} L={kv['l']}" + ''.join(f" {k.upper()}={kv[k]}" for k in ('as', 'ad', 'ps', 'pd') if k in kv))
        elif h == 'X' and pos and pos[-1] in RES:
            a, b, s = pos[:3] if len(pos) >= 4 else (pos[0], pos[1], sub)
            out.append(f"R{t[0][1:]} {a} {b} {s} {pos[-1]} L={kv.get('r_length', kv.get('l'))} W={kv.get('r_width', kv.get('w'))}")
        elif h == 'D' and len(pos) >= 3:
            p = kv.get('pj', kv.get('p', '0')); p = re.sub(r'p$', 'u', p)          # references wrote pj in pF units by mistake
            out.append(f"D{t[0][1:]} {pos[0]} {pos[1]} {pos[2]} A={kv.get('area', kv.get('a'))} P={p}")
        else: out.append(l)
    return out
if __name__ == '__main__':
    src = open(sys.argv[1]).read().replace('\n+', ' ').splitlines()
    open(sys.argv[2], 'w').write('\n'.join(conv(src)) + '\n')
