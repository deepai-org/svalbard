#!/usr/bin/env python3
"""Die-fit study: supply / routing / decap overheads DERIVED from the connectivity and from the packed floorplans.
Inputs: pt_chip.conn, run/fit-<tag>.json (placement), m45free.json (published) + m45free_staged.json (staged), ledger.json.
Output: overheads.json + printed tables.   python3 overheads.py [tagB tagC]"""
import sys, os, re, json, math, collections
R = '/home/ubuntu/svalbard'; P = f'{R}/projects/programmable_transceiver_platform'; HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, f'{P}/integration/top')
import check_top
inst, ports, waive, err = check_top.parse(open(f'{P}/integration/top/pt_chip.conn').read())
tags = sys.argv[1:] or ['b', 'c']
L = json.load(open(f'{HERE}/ledger.json'))
out = {}

# ---- 1. net counts from the conn ------------------------------------------------------------------------------------------
nets = collections.defaultdict(set)
for n, d in inst.items():
    for p, (k, net) in d['pins'].items():
        if net != '-': nets[net].add(n)
def is_supply(n): return re.match(r'VDD|VSS|RAIL_|AGND|VISL|VR\b|VR_|ESD_RAIL', n) is not None
ctl = [n for n in nets if n.startswith('c_')]; sts = [n for n in nets if n.startswith('s_')]
dig = {net for p, (k, net) in inst['digital']['pins'].items() if net not in ('-', 'VDD', 'VSS')}
direct = [n for n in dig if not n.startswith(('c_', 's_'))]
pad_side = {'host', 'debug_pads', 'pad_por_bypass', 'atb0_io', 'atb1_io'}
direct_host = [n for n in direct if nets[n] & pad_side]; direct_an = [n for n in direct if not (nets[n] & pad_side)]
ana = [n for n in nets if n not in dig and not n.startswith(('c_', 's_')) and not is_supply(n) and len(nets[n]) >= 2]
cls = collections.Counter()
for n in ana:
    b = re.sub(r'[\[\]\d]+$', '', n)
    k = ('ring phases (CDRPH/CKP/SLS/TXPH)' if re.match(r'CDRPH|CKP|SLS|TXPH', n) else 'bias currents (BIAS_*)' if n.startswith('BIAS_') else
         'ATB tree (ATB*)' if n.startswith('ATB') else 'LO / RF differential (LO_*, RFA_*, LNA_*)' if re.match(r'LO_|RFA_|LNA_|BBI_|BBQ_', n) else
         'CDR votes (CDR_UP/DN, WRX_UP/DN)' if re.match(r'CDR_|WRX_UP|WRX_DN', n) else 'other analog / local')
    cls[k] += 1
out['nets'] = dict(control_bits=len(ctl), status_bits=len(sts), macro_direct_to_analog=len(direct_an), macro_to_pads=len(direct_host),
                   analog_multi_instance=len(ana), analog_classes=dict(cls), supply_nets=sorted(n for n in nets if is_supply(n)))
print('NETS', json.dumps(out['nets'], indent=0)[:1500])

# ---- 2. routing demand from the placements ------------------------------------------------------------------------------
PITCH_MIN = 0.56      # GF180 Metal2-4: 0.28 width + 0.28 space
PITCH_REAL = 1.12     # double pitch: hand-routed analog top, shields on clocks/data, via landing
def mg(r1, r2): return max(r2[0]-r1[2], r1[0]-r2[2], 0.0)+max(r2[1]-r1[3], r1[1]-r2[3], 0.0)
def ctr(r): return ((r[0]+r[2])/2, (r[1]+r[3])/2)
for tag in tags:
    f = f'{HERE}/run/fit-{tag}.json'
    if not os.path.exists(f): continue
    J = json.load(open(f)); pr = {n: d['rect'] for n, d in J['placed_rects'].items()}; dg = J['fixed']['digital']
    pads = {n: rs[0] for n, rs in J['pads'].items()}; allr = dict(pr); allr.update(pads); allr['digital'] = dg
    # macro <-> block: every control/status/direct bit, Manhattan edge-to-edge
    ctl_len = 0.0; fast_len = 0.0; missing = collections.Counter()
    for net in ctl+sts+direct_an:
        ends = [i for i in nets[net] if i != 'digital']
        for i in ends:
            if i in allr:
                d = mg(allr[i], dg)
                if net in direct_an: fast_len += d
                else: ctl_len += d
            else: missing[i] += 1
    # analog multi-instance nets: half-perimeter of the bounding box of the instance centres
    an_len = collections.Counter(); an_n = collections.Counter()
    for net in ana:
        pts = [ctr(allr[i]) for i in nets[net] if i in allr]
        if len(pts) >= 2:
            hp = (max(p[0] for p in pts)-min(p[0] for p in pts))+(max(p[1] for p in pts)-min(p[1] for p in pts))
            k = ('ring' if re.match(r'CDRPH|CKP|SLS|TXPH', net) else 'bias' if net.startswith('BIAS_') else 'atb' if net.startswith('ATB') else
                 'lo_rf' if re.match(r'LO_|RFA_|LNA_|BBI_|BBQ_', net) else 'other')
            an_len[k] += hp; an_n[k] += 1
    # fixed long routes that the conn does not show as lengths
    d2h = 11*(dg[1]-452.0+300)          # D2H[9:0]+clk from the macro south edge to the south pad row (corridor)
    fwd = 2*3100.0                      # forwarded wire clock on the AUX_CLK pair: 3.1 mm differential (CP4-3)
    # track area: static control at min pitch; fast digital (data/clock words) and analog at double pitch (shield/space);
    # ring phases and LO as shielded pairs: 3 x double pitch per wire
    def area(p_ctl, p_fast):
        return (ctl_len*p_ctl + (fast_len+d2h)*p_fast + (an_len['bias']+an_len['atb']+an_len['other'])*p_fast
                + (an_len['ring']+an_len['lo_rf']+fwd)*3*p_fast)/1e6
    a_min = area(PITCH_MIN, PITCH_MIN); a_real = area(PITCH_MIN, PITCH_REAL); a_wide = area(PITCH_REAL, PITCH_REAL)
    # channel supply: the halo band of the placed blocks. Layers a channel offers along its length: Metal2 or Metal3 in the
    # preferred direction (1 layer) + 30 % of Metal4/Metal5 (the rest of those is power: grid, island straps, plates);
    # routable fraction 60 % (vias, jogs, pin access)
    chan = J['halo_area_mm2']; cap = chan*(1.0+0.3)*0.6
    corr = sum((r[2]-r[0])*(r[3]-r[1]) for n, r in J['fixed'].items() if n.endswith('_rsv') and 'corridor' in n or n == 'lo_legs_rsv')/1e6
    out[f'routing_{tag}'] = dict(control_wire_mm=round(ctl_len/1e3, 1), fast_digital_wire_mm=round(fast_len/1e3, 1), d2h_wire_mm=round(d2h/1e3, 1),
        analog_wire_mm={k: round(v/1e3, 1) for k, v in an_len.items()}, analog_net_count=dict(an_n), fwd_clk_mm=fwd/1e3,
        endpoints_on_unplaced_blocks=sum(missing.values()), unplaced_with_nets=dict(missing.most_common(8)),
        track_area_mm2=dict(min_pitch=round(a_min, 3), control_min_fast_double=round(a_real, 3), all_double=round(a_wide, 3)),
        channel_area_mm2=chan, channel_track_capacity_mm2=round(cap, 3), corridor_and_lo_legs_mm2=round(corr, 3),
        channel_need_mm2={k: round(v/(1.3*0.6), 3) for k, v in dict(min_pitch=a_min, control_min_fast_double=a_real, all_double=a_wide).items()},
        ten_pct_allowance_mm2=0.855, strap_m5_area_mm2=J['strap_m5_area_mm2'])
    print(f'ROUTING {tag}', json.dumps(out[f'routing_{tag}'], indent=0))

# ---- 3. M4/M5 over blocks: grid + plates vs what the outlines leave free --------------------------------------------------
pub = json.load(open(f'{R}/scratch/area-pass-4/m45free.json')); stg = json.load(open(f'{HERE}/m45free_staged.json'))
SPIRAL = {'pt_lc_qvco5', 'pt_lna_ind', 'pt_lna_deg'}
SENS = {'pt_adc_i', 'pt_adc_q', 'pt_bbfilter_i', 'pt_bbfilter_q', 'pt_lna', 'pt_rxmix_i', 'pt_rxmix_q', 'pt_lo_lf', 'pt_lo_pfdcp', 'pt_refbuf'}   # no plate over inputs / loop filter: half usable
STG_ALIAS = {'pt_adc_q': 'pt_adc_i', 'pt_dac_q': 'pt_dac_i', 'pt_rxmix_q': 'pt_rxmix_i'}
tot = {s: dict(outline=0.0, free=0.0, free_nospiral=0.0, free_usable=0.0, grid_displaced=0.0, nodata=0.0) for s in 'ABC'}
rowsm = []
for r in L['rows']:
    m = r['master']; n = r['item']
    if m.startswith(('pad_', 'prov', 'atb_provider', 'pt_host', 'pt_debug')) or m == 'pt_digital_macro' or n == 'decap_macro_edge_bank': continue
    mm = m if r['kind'] == 'conn' else {'r8arch_slicer_b': 'pt_slicer', 'r8arch_capture_b': 'pt_wrx_cap'}.get(n, n)
    for s, key in (('A', 'pub_um2'), ('B', 'staged_um2'), ('C', 'target_um2')):
        a = r[key]
        if a <= 0: continue
        p_ = pub.get(mm); s_ = stg.get(STG_ALIAS.get(mm, mm))
        if s == 'A':
            src = p_ if (p_ and abs(p_['outline']-a) < 0.03*a) else (s_ if (s_ and 'outline' in s_ and abs(s_['outline']-a) < 0.03*a) else None)
            free = src['free_m45_20um'] if src else None
        else:
            if s_ and 'outline' in s_ and abs(s_['outline']-a) < 0.03*a: free = s_['free_m45_20um']
            elif p_ and abs(p_['outline']-a) < 0.03*a: free = p_['free_m45_20um']
            elif s_ and 'outline' in s_: free = max(0.0, s_['free_m45_20um']-(s_['outline']-a))     # outline shrinks further: free shrinks one for one
            elif p_: free = max(0.0, p_['free_m45_20um']-(p_['outline']-a))
            else: free = None
        t = tot[s]; t['outline'] += a
        if free is None:
            t['nodata'] += a; free = 0.0
        t['free'] += free
        if mm not in SPIRAL:
            t['free_nospiral'] += free; t['free_usable'] += free*(0.5 if mm in SENS else 1.0)
        # G1: 30 % of Metal4 and Metal5 over the block must be grid; what the block cannot give goes into the channels
        t['grid_displaced'] += max(0.0, 0.30*a-free)
        if s == 'B': rowsm.append((n, mm, a, free))
out['m45'] = {s: {k: round(v/1e6, 3) for k, v in t.items()} for s, t in tot.items()}
for s in 'ABC':
    t = out['m45'][s]
    # plates: PD2 needs 1.05 mm2 of plate for 2.0 nF and 1.58 mm2 for 3.0 nF (1.9 fF/um2). The grid already needs 30 % of the same layers.
    t['plate_capacity_nF_all_usable'] = round(t['free_usable']*1.9, 2)
    t['after_grid_30pct_mm2'] = round(max(0.0, t['free_usable']-0.30*(t['outline']-t['nodata'])+t['grid_displaced']*0), 3)
    t['plate_capacity_nF_after_grid'] = round(max(0.0, t['free_usable']-0.30*t['free_usable'])*1.9, 2)   # grid straps take 30 % of the free area they cross
    t['fraction_of_free_for_2nF'] = round(1.05/max(t['free_usable'], 1e-9), 2); t['fraction_of_free_for_3nF'] = round(1.58/max(t['free_usable'], 1e-9), 2)
print('M45', json.dumps(out['m45'], indent=0))
rowsm.sort(key=lambda x: -x[3]); print('B: largest free M4/M5 areas:', [(n, round(f/1e3)) for n, m, a, f in rowsm[:14]])
out['m45_B_top'] = [(n, round(a), round(f)) for n, m, a, f in rowsm[:20]]
json.dump(out, open(f'{HERE}/overheads.json', 'w'), indent=1)
