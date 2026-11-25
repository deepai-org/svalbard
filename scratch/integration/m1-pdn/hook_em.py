#!/usr/bin/env python3
"""Hook nets (block VDD / VSS pin -> grid slot, routed.def) of the heavy supply users: resistance, drop and EM.
R: segment length / width x Rs (Metal2-4 0.090, Metal5 0.060 ohm/sq, tech LEF) + 4.5 ohm per via cut (single-cut router vias).
EM: tech LEF DCCURRENTDENSITY (Metal1-4 0.67 mA/um, Metal5 1.5 mA/um, Via 0.18 mA/cut) and the same scaled to 85 C by the
DRM ratio the power spec uses (Metal2 2.09 / 0.67 = 3.1x).   usage: hook_em.py rf|wired"""
import sys, re, json, collections
ch = sys.argv[1]; R = f'../assembly-{ch}/'
RS = {'Metal1': .09, 'Metal2': .09, 'Metal3': .09, 'Metal4': .09, 'Metal5': .06}; JL = {'Metal5': 1.5}; JV = 0.18; K85 = 3.1
NDR = {'Metal2': .56, 'Metal3': .56, 'Metal4': .56, 'Metal5': .56}; DEFW = {'Metal1': .23, 'Metal2': .28, 'Metal3': .28, 'Metal4': .28, 'Metal5': .44}
# currents (mA): island switch VDD = island design current (README / PDS-19); loads > 5 mA on their VSS hooks (worst, README tables)
ISL = {'rf': {'isw_lod': 74.1, 'isw_rf_tx': 28.3, 'isw_rf_tx_b': 28.3, 'isw_rf_rx': 43.6, 'isw_pll': 30.7, 'isw_lo': 28.1, 'isw_conv': 18.7, 'isw_debug': 40.0},
       'wired': {'isw_wired_cap': 72.9, 'isw_wired_tx_a': 65.7, 'isw_wired_tx_b': 65.7, 'isw_wired_rx': 30.9, 'isw_pll': 29.4, 'isw_debug': 40.0}}[ch]
LOADS = {'rf': {'lo_mmd': 34.8, 'lo_vreg': 27.5, 'rfdriver': 24.3, 'lna': 21.4, 'pll_vreg2': 20.9, 'lo_txbuf': 59.3, 'lo_ext': 13.7, 'vco_replica': 11.8,
                'lo_mmd_qdum': 10.0, 'lo_obs': 8.0, 'lo_obs_q': 8.0, 'adc_i': 6.3, 'adc_q': 6.3, 'bbfilter_i': 5.3, 'bbfilter_q': 5.3, 'clk_obs': 5.1, 'rx_aux_clk': 5.1},
         'wired': {'wrx_cap': 46.6, 'wiredtx': 60.0, 'ptrim': 21.0, 'pad_wire_tx': 21.0, 'usb_txdrv': 20.0, 'pll_vreg2': 20.9, 'vco_replica': 11.8, 'slicer': 9.8,
                   'ctle': 5.3, 'clk_obs': 5.1, 'rx_aux_clk': 5.1, 'rx_wtx_ext': 5.1}}[ch]
place = json.load(open(R+'place.json'))
hooks = collections.defaultdict(list)
for h in place['hooks']: hooks[(h['inst'], h['net'].split('__')[0])].append(h['net'])
dl = collections.Counter((d['inst'], d['net']) for d in place.get('direct_landings', []))
segs = collections.defaultdict(list); vias = collections.Counter(); cur = None
for l in open(R+'route/routed.def'):
    m = re.match(r'\s*- (\S+) ', l)
    if m: cur = m.group(1) if '__HK' in m.group(1) else None
    if not cur: continue
    t = re.search(r'(?:ROUTED|NEW)\s+(Metal\d)\s+(TAPER\s+)?(.*)', l)
    if not t: continue
    ln, taper, rest = t.group(1), bool(t.group(2)), t.group(3)
    pts = re.findall(r'\(\s*(\S+)\s+(\S+)(?:\s+\S+)?\s*\)', rest); P = []; px = py = None
    for x, y in pts:
        x = px if x == '*' else int(x); y = py if y == '*' else int(y); P.append((x, y)); px, py = x, y
    for a, b in zip(P, P[1:]): segs[cur].append((ln, (abs(a[0]-b[0])+abs(a[1]-b[1]))/1000, DEFW[ln] if taper else NDR[ln]))
    if re.search(r'\)\s+Via\S*\s*;?\s*$', rest) or re.search(r'Via\d_\S+', rest): vias[cur] += 1
def hook_r(n):
    return sum(RS[ln]*L/max(w, 1e-3) for ln, L, w in segs[n]) + 4.5*vias[n]
def wmin(n):
    return min(((w*JL.get(ln, .67)), ln, w) for ln, L, w in segs[n] if L > 0) if segs[n] else (float('inf'), '-', 0)
rows = []
for (inst, net), lst in sorted(hooks.items()):
    I = ISL.get(inst) if net == 'VDD' else LOADS.get(inst)
    if net == 'VSS' and inst in ISL: continue
    if I is None: continue
    n = len(lst) + dl.get((inst, net), 0)
    rpar = 1/sum(1/max(hook_r(h), 1e-3) for h in lst) if lst else float('inf')
    jw, jl, jwid = min(wmin(h) for h in lst)
    nv = min(vias[h] for h in lst)
    rows.append((inst, net, I, len(lst), dl.get((inst, net), 0), rpar, I*rpar, I/len(lst), jw, jl, jwid, nv))
print(f'{ch}: hooks of the heavy supply users (current split evenly over the hooks of the pin group; direct landings counted separately)')
print('inst | net | mA | hooks | direct | R_par ohm | drop mV | mA per hook | narrowest: limit mA (LEF) / 85C | layer, width um | min via cuts')
for r in sorted(rows, key=lambda r: -r[6]):
    inst, net, I, nh, nd, rp, dv, ih, jw, jl, jwid, nv = r
    print(f'{inst} | {net} | {I:.1f} | {nh} | {nd} | {rp:.2f} | {dv:.0f} | {ih:.1f} | {jw:.2f} / {jw*K85:.2f} | {jl} {jwid} | {nv} (cut {JV:.2f} / {JV*K85:.2f} mA)')
