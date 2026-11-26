#!/usr/bin/env python3
"""draw.py <eval_tag.json> <use_tag.npy|-> <out.svg> [G] [chan.json]: blocks, macro pins, channels and routing utilisation heat"""
import json, sys, numpy as np
E = json.load(open(sys.argv[1])); out = sys.argv[3]; G = float(sys.argv[4]) if len(sys.argv) > 4 else 20
S = 0.2   # px per um
W, H = 3932 * S, 5122 * S
o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H + 30:.0f}" viewBox="0 0 {W:.0f} {H + 30:.0f}" font-family="sans-serif">',
     f'<rect x="0" y="0" width="{W:.0f}" height="{H:.0f}" fill="#fafafa" stroke="#333"/>']
def R(x0, y0, x1, y1, **a):
    s = ' '.join(f'{k.replace("_", "-")}="{v}"' for k, v in a.items())
    return f'<rect x="{x0 * S:.1f}" y="{(5122 - y1) * S:.1f}" width="{(x1 - x0) * S:.1f}" height="{(y1 - y0) * S:.1f}" {s}/>'
if sys.argv[2] != '-':
    uH, uV, cH, cV = np.load(sys.argv[2])
    r = np.maximum(np.where(cH > 0.5, uH / np.maximum(cH, 1e-3), 0), np.where(cV > 0.5, uV / np.maximum(cV, 1e-3), 0))
    for ix in range(r.shape[0]):
        for iy in range(r.shape[1]):
            v = r[ix, iy]
            if v < 0.3: continue
            col = '#fde0a0' if v < 0.5 else '#fdae61' if v < 0.7 else '#f46d43' if v < 1.0 else '#a50026'
            o.append(R(ix * G, iy * G, (ix + 1) * G, (iy + 1) * G, fill=col, stroke='none'))
o.append(R(452, 452, 3480, 4670, fill='none', stroke='#888', stroke_dasharray='4,3'))
for n, q in E.get('channels', {}).items(): o.append(R(*q, fill='#9ecae1', fill_opacity='0.35', stroke='#3182bd', stroke_dasharray='3,2'))
for n, q in E.get('keepouts', []): o.append(R(*q, fill='#ddd', stroke='#aaa'))
for i, q in E['rect'].items():
    x0, y0, x1, y1 = q; a = (x1 - x0) * (y1 - y0)
    if i == 'digital': st = dict(fill='#c6dbef', fill_opacity='0.5', stroke='#08519c', stroke_width='1.5')
    elif i.startswith('decap'): st = dict(fill='#eeeeee', stroke='#bbb', stroke_width='0.4')
    elif a < 15000: st = dict(fill='#ffffff', stroke='#777', stroke_width='0.4')
    else: st = dict(fill='#e5f5e0', fill_opacity='0.6', stroke='#238b45', stroke_width='0.8')
    o.append(R(x0, y0, x1, y1, **st))
    if a >= 15000 and not i.startswith('decap'):
        fs = 7 if a > 100000 else 5.5
        o.append(f'<text x="{(x0 + x1) / 2 * S:.1f}" y="{(5122 - (y0 + y1) / 2) * S + 2:.1f}" font-size="{fs}" text-anchor="middle">{i}</text>')
for n, (s, x, y) in E.get('mpins', {}).items():
    o.append(f'<circle cx="{x * S:.1f}" cy="{(5122 - y) * S:.1f}" r="0.6" fill="#08519c"/>')
t = E['res']['tag']; rr = E['res']['route']
o.append(f'<text x="4" y="{H + 12:.0f}" font-size="9">{t}: gcells over 70 %: H {rr["H_cells_over70"]}, V {rr["V_cells_over70"]}; over 100 %: H {rr["H_cells_over100"]}, V {rr["V_cells_over100"]}; ({rr["G"]:.0f} um gcells, Metal2 V / Metal3 H)</text>')
o.append(f'<text x="4" y="{H + 24:.0f}" font-size="8">heat: yellow 30-50 %, orange 50-70 %, red 70-100 %, dark red &gt;100 % of Metal2/Metal3 tracks</text>')
o.append('</svg>')
open(out, 'w').write('\n'.join(o))
