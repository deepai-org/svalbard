"""Top-level performance-gate floorplan rules (MANDATE.md "Top-level performance gate").

Evaluated on floorplan.json; writes floorplan-rules.json:
  chains      signal-flow chains pad -> ... -> digital (hop lengths, direction reversals,
              crossings between different chains)
  isolation   edge-to-edge distance from every aggressor to every victim
  symmetry    I/Q pairs: mirrored orientation and mirror-image position about their axis
  pads        block-to-pad distance for every pad-facing block
  digital     which macro edge each digital consumer faces versus the macro pin plan
Each rule has a negative control: a deliberately broken copy of the floorplan must fail.
"""
import copy
import json
import sys
from pathlib import Path

# Chain hops: instance / fixed names; 'digital.S' etc. = macro edge midpoints; pads use the
# core-side end of the pad family.
# '@x,y' hops are routing waypoints (the planned corridor), so a chain is drawn along its route, not a straight
# line through other blocks. Pads use the family's signal port (floorplan.json port_xy).
CHAINS = [
    ('rf_rx', ['pad_rf_rx', 'lna', 'rxmix_q', 'bbfilter_q', 'adc_q', '@2280,600', '@2280,3000', 'digital.S'],
     'Q half: adc_q (MX) outputs face south -> corridor -> macro S edge'),
    ('rf_rx', ['pad_rf_rx', 'lna', '@1239,1330', '@1239,1905', 'rxmix_i', 'bbfilter_i', 'adc_i', 'digital.S'],
     'I half: LNA output up the 40 um channel (Q path length-matched); adc_i outputs abut the macro'),
    ('rf_tx', ['digital.S', '@2280,3000', '@2280,527', '@789,527', 'dac_i', '@1239,1180', '@1239,1799', 'bbfilter_i',
               '@1239,1799', '@1239,2500', 'txmix_i', 'txsum',
               'rfdriver', 'pad_rf_tx'], 'DAC data via the corridor and the south strip; bbfilter shared (TX dir)'),
    ('wired_rx', ['pad_wire_rx', 'ctle', 'rxselect', 'slicer', 'cdr', '@2300,1720', '@2300,3000', 'digital.S'],
     'bond-end CTLE, then west to the samplers/CDR, corridor north to the macro'),
    ('wired_tx', ['digital.S', 'wiredtx', 'pad_wire_tx'], 'serializer and CML driver are one block'),
    ('clock', ['pad_aux_clk', '@948,4305', '@1374,4305', '@1374,3052', '@1239,3052', '@1239,1798', 'lo_ext', 'rxmix_i'],
     'external LO-Q (B3): north around core_bias, bundled with REF (LO-I), down the 40 um channel to the LO hub'),
    ('clock', ['pad_ref', '@1374,4305'], 'external LO-I joins the bundle'),
    ('clock', ['pll_host', '@1239,2740', '@1239,2310', 'polyphase', 'lo_ext'], 'on-chip RF ring -> polyphase -> LO hub'),
    ('clock', ['pll_cdr', 'slicer'], 'CDR ring phases -> samplers'),
    ('clock', ['pll_tx', 'wiredtx'], 'TX ring phases -> serializer'),
    ('clock', ['pad_wclk_in', 'rx_wclk_in', 'cdr'], 'forwarded clock (S6) -> CDR reference'),
    ('host', ['digital.S', '@2280,3000', '@2280,527', 'rsv_d2h_gearbox'], 'D2H: word/4 bus via the corridor'),
    ('host', ['digital.N', 'rsv_h2d_gearbox'], 'H2D: macro north edge, 40 um escape channel'),
]
AGGRESSORS = ['digital', 'rfdriver', 'pll_tx', 'pll_cdr', 'pll_host', 'ring_osc', 'vco_replica', 'wiredtx', 'clk_obs',
              'wclk_obs']
VICTIMS = ['lna', 'rxmix_i', 'rxmix_q', 'pll_host', 'pll_tx', 'pll_cdr', 'core_bias', 'adc_i', 'adc_q', 'refbuf']
# Driver/load pairs that rule 1 requires to be adjacent (PLL phases -> their own samplers/serializer); their
# coupling is part of the block-pair design and is checked by the coupling simulation, not by distance.
DESIGNED_NEIGHBOURS = {('pll_tx', 'wiredtx'), ('wiredtx', 'pll_tx'), ('pll_cdr', 'slicer'), ('pll_cdr', 'cdr')}
IQ_PAIRS = [('rxmix_i', 'rxmix_q'), ('bbfilter_i', 'bbfilter_q'), ('adc_i', 'adc_q'), ('txmix_i', 'txmix_q'),
            ('dac_i', 'dac_q')]
PAD_BLOCKS = [('lna', 'pad_rf_rx'), ('rfdriver', 'pad_rf_tx'), ('ctle', 'pad_wire_rx'),
              ('wiredtx', 'pad_wire_tx'), ('rx_wclk_in', 'pad_wclk_in'),
              ('rx_aux_clk', 'pad_aux_clk'), ('lo_ext', 'pad_aux_clk'), ('lo_ext', 'pad_ref'), ('bb_tap_i', 'pad_bb_i'),
              ('bb_tap_q', 'pad_bb_q'), ('rx_wtx_ext', 'pad_wtx_ext'), ('bb_tap_wmon', 'pad_wmon')]
# Macro pin plan REQUESTED by integration for floorplan v3 (interface-changes.md I6); consumer group -> edge.
PIN_PLAN = {'D2H/SPI/host clock': ('S', ['rsv_d2h_gearbox']), 'H2D/debug_cfg': ('N', ['rsv_h2d_gearbox']),
            'RF/converter data': ('S', ['adc_i', 'adc_q', 'dac_i', 'dac_q']),
            'wired data and clocks': ('S', ['wiredtx', 'cdr', 'slicer']),
            'clock tree/ref': ('W', ['clockmux', 'prescale', 'wordclk']),
            'analog_cfg/island/ATB': ('W', ['core_bias'])}
# Consumers reached through the corridor: its top end is the effective point the S-edge pin faces.
VIA_CORRIDOR = {'adc_q', 'dac_i', 'dac_q', 'rsv_d2h_gearbox', 'cdr', 'slicer'}
LIMITS = dict(max_pad_gap_um=150.0, max_port_gap_um=600.0, min_aggressor_victim_um={'digital': 100.0, 'rfdriver': 500.0, 'default': 50.0},
              lna_vs_digital_um=1000.0, lna_vs_rfdriver_um=1000.0, sym_tol_um=1.0)


# ----------------------------------------------------------------------------------------------- floorplan v4
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventory as _inv   # noqa: E402
V4 = _inv.FLOORPLAN == 'v4'
MODE_EXCLUSIVE = set()      # chain-pair crossings that can never be active together (documented per pair)
if V4:
    _mb = _inv.DIGITAL_ORIGIN[1]
    CHAINS = [
        ('rf_rx', ['pad_rf_rx', 'lna', 'rxmix_q', 'bbfilter_q', 'adc_q', '@2278,481', f'@2278,{_mb-10:.0f}', 'digital.S'],
         'Q half: adc_q outputs -> corridor (x 2255-2302) -> macro S edge'),
        ('rf_rx', ['pad_rf_rx', 'lna', 'rxmix_i', 'bbfilter_i', 'adc_i', 'digital.S'],
         'I half: LNA on the I/Q axis, adc_i data across the isolation band to the macro S edge'),
        ('rf_tx', ['digital.W', 'dac_q', 'txmix_i', 'txsum', '@946,3016', '@946,4310', 'rfdriver', 'pad_rf_tx'],
         'DAC data on the macro W edge; DAC -> TX mixers (direct, or via the shared bbfilter in TX dir); txsum -> PA '
         'in the 30 um channel west of the DACs'),
        ('wired_rx', ['pad_wire_rx', 'ctle', 'rxselect', 'slicer', 'cdr', '@2278,1400', f'@2278,{_mb-10:.0f}', 'digital.S'],
         'bond-end CTLE, samplers/CDR in band A, corridor north to the macro'),
        ('wired_tx', ['digital.S', 'wiredtx', 'pad_wire_tx'], 'serializer and CML driver are one block'),
        ('clock', ['pad_ref', '@981,2653', 'lo_ext'], 'external LO-I leg: P7 pins north to the hub (rsv_lo_legs)'),
        ('clock', ['pad_aux_clk', '@981,2653', 'lo_ext'], 'external LO-Q leg: P5 pins south to the hub'),
        ('clock', ['lo_ext', '@1239,2551', '@1239,1731', 'rxmix_i'], 'hub -> RX mixers down channel A, split on the axis'),
        ('clock', ['lo_ext', 'txmix_q'], 'hub -> TX mixers (adjacent)'),
        ('clock', ['pll_host', 'polyphase', 'lo_ext'], 'internal LO (mode-exclusive with the external legs)'),
        ('clock', ['pll_cdr', 'slicer'], 'CDR ring phases -> samplers'),
        ('clock', ['pll_tx', 'wiredtx'], 'TX ring phases -> serializer'),
        ('clock', ['pad_wclk_in', 'rx_wclk_in', 'cdr'], 'forwarded clock (S6) -> CDR reference'),
        ('host', ['digital.S', f'@2278,{_mb-10:.0f}', '@2278,481', 'rsv_d2h_gearbox'], 'D2H: word/4 bus via the corridor'),
        ('host', ['digital.E', 'rsv_h2d_gearbox'], 'H2D: macro E edge north end (and N rows under the H2D pads)'),
    ]
    # The internal-LO chain (pll_host -> polyphase -> lo_ext) and the external LO-I leg are never active together.
    MODE_EXCLUSIVE = {frozenset((5, 9)), frozenset((6, 9)),
                      # Designed right-angle crossing (not mode-exclusive): the forwarded WCLK_IN clock reaches the CDR
                      # across the CTLE->samplers data path; different layers, both shielded (wired mode only).
                      frozenset((3, 12))}
    AGGRESSORS = ['digital', 'rfdriver', 'pll_tx', 'pll_cdr', 'pll_host', 'ring_osc', 'vco_replica', 'wiredtx', 'clk_obs',
                  'wclk_obs', 'aosc', 'clockmux', 'prescale', 'wordclk', 'cdr']
    VICTIMS = ['lna', 'rxmix_i', 'rxmix_q', 'pll_host', 'pll_tx', 'pll_cdr', 'core_bias', 'adc_i', 'adc_q', 'refbuf',
               'bbfilter_i', 'bbfilter_q', 'lo_ext', 'polyphase', 'por']
    DESIGNED_NEIGHBOURS |= {('pll_cdr', 'cdr'), ('cdr', 'pll_cdr'), ('pll_host', 'polyphase'), ('polyphase', 'pll_host'),
                            ('cdr', 'slicer'), ('clockmux', 'pll_tx'), ('pll_tx', 'clockmux')}
    PAD_BLOCKS = [('lna', 'pad_rf_rx'), ('rfdriver', 'pad_rf_tx'), ('ctle', 'pad_wire_rx'), ('wiredtx', 'pad_wire_tx'),
                  ('rx_wclk_in', 'pad_wclk_in'), ('rx_aux_clk', 'pad_aux_clk'), ('lo_ext', 'pad_aux_clk'),
                  ('lo_ext', 'pad_ref'), ('bb_tap_i', 'pad_bb_i'), ('bb_tap_q', 'pad_bb_q'), ('rx_wtx_ext', 'pad_wtx_ext'),
                  ('bb_tap_wmon', 'pad_wmon')]
    PIN_PLAN = {'D2H/SPI/host clock': ('S', ['rsv_d2h_gearbox']), 'H2D/debug_cfg': ('E', ['rsv_h2d_gearbox']),
                'ADC data': ('S', ['adc_i', 'adc_q']), 'DAC data': ('W', ['dac_i', 'dac_q']),
                'wired data and clocks': ('S', ['wiredtx', 'cdr', 'slicer']),
                'clock tree': ('S', ['wordclk', 'clockmux']),
                'analog_cfg/island/ATB': ('S', ['core_bias', 'lo_ext'])}
    VIA_CORRIDOR = {'adc_q', 'rsv_d2h_gearbox', 'cdr', 'slicer', 'core_bias'}
    REGISTER_DISTANCES = _inv.REGISTER_DISTANCES if hasattr(_inv, 'REGISTER_DISTANCES') else []
    # Extracted pad-node C (pads owner, C-only, compact candidates; fF, P/N). IQ-03: |dC| <= 50 fF on the LO legs.
    PAD_C_FF = {'pad_refpad': (430.0, 397.0), 'pad_rf_pair': (465.0, 431.0), 'pad_refpad_old': (317.0, 315.0),
                'pad_rf_pair_old': (412.0, 389.0)}
    LIMITS.update(lo_leg_match_um=20.0, lo_leg_max_um=1100.0, mixer_hub_max_um=500.0, lo_leg_vs_rfin_um=100.0,
                  corridor_vs_adc_um=20.0, strip_vs_vref_um=5.0)


def _manh(p, q):
    return abs(p[0]-q[0])+abs(p[1]-q[1])


def v4_checks(fp):
    """Register-driven v4 rules: distances (cited IDs), LO legs (XT-01/A4/IQ-03), isolation band, XT-04, RA-6."""
    r = rects(fp)
    out = {}
    dist = []
    for a, v, lim, rid, basis in REGISTER_DISTANCES:
        if a in r and v in r:
            g = gap(r[a], r[v])
            dist.append(dict(aggressor=a, victim=v, gap_um=round(g, 1), limit_um=lim, register=rid, basis=basis,
                             ok=g >= lim-1e-6))
    floor = [d for d in dist if d['register'] == 'SUB-01']
    out['register_distances'] = dict(pairs=dist, ok=all(d['ok'] for d in dist if d['register'] != 'SUB-01'),
                                     sub01_floor_210_ok=all(d['gap_um'] >= 210.0 for d in floor),
                                     sub01_target_300_ok=all(d['gap_um'] >= 300.0 for d in floor),
                                     sub01_shortfall_to_300_um=round(max([300.0-d['gap_um'] for d in floor]+[0.0]), 1))
    out['register_distances']['ok'] = out['register_distances']['ok'] and out['register_distances']['sub01_floor_210_ok']
    # LO legs: pad inner-edge port -> hub west-edge midpoint, Manhattan
    pads = {f['name']: f for f in fp['fixed'] if f['kind'] == 'pad_family'}
    hub = r['lo_ext']
    hub_in = (hub[0], (hub[1]+hub[3])/2)
    legs = {}
    for pn in ('pad_ref', 'pad_aux_clk'):
        legs[pn] = round(_manh(tuple(pads[pn]['port_xy']), hub_in), 1)
    cI = PAD_C_FF.get(pads['pad_ref']['master']); cQ = PAD_C_FF.get(pads['pad_aux_clk']['master'])
    dc = max(abs(cI[0]-cQ[0]), abs(cI[1]-cQ[1])) if cI and cQ else None
    rfin = tuple(pads['pad_rf_rx']['port_xy'])
    lna = r['lna']
    rf_seg = (min(rfin[0], lna[0]), min(rfin[1], lna[1]), max(rfin[0], lna[0]), max(rfin[1], lna[1]))
    legs_rect = next(f['rect'] for f in fp['fixed'] if f['name'] == 'rsv_lo_legs')
    vs_rfin = gap(legs_rect, rf_seg)
    mix = {m: round(gap(r[m], hub), 1) for m in ('rxmix_i', 'rxmix_q', 'txmix_i', 'txmix_q') if m in r}
    out['lo_legs'] = dict(leg_um=legs, mismatch_um=round(abs(legs['pad_ref']-legs['pad_aux_clk']), 1),
                          pad_masters=[pads['pad_ref']['master'], pads['pad_aux_clk']['master']], pad_dc_ff=dc,
                          legs_vs_rf_input_um=round(vs_rfin, 1), mixer_to_hub_edge_um=mix,
                          ok=abs(legs['pad_ref']-legs['pad_aux_clk']) <= LIMITS['lo_leg_match_um']
                          and max(legs.values()) <= LIMITS['lo_leg_max_um'] and dc is not None and dc <= 50.0
                          and vs_rfin >= LIMITS['lo_leg_vs_rfin_um'],
                          mixers_within_500_um=[m for m, g in mix.items() if g <= LIMITS['mixer_hub_max_um']],
                          mixers_beyond_500_um=[m for m, g in mix.items() if g > LIMITS['mixer_hub_max_um']])
    # isolation band: MIM decap only (no active block, no MOS tile with substrate taps)
    band = next((f['rect'] for f in fp['fixed'] if f['name'] == 'rsv_isolation_band'), None)
    intr = []
    if band:
        for p in fp['placed']:
            q = p['rect']
            if min(q[2], band[2]) > max(q[0], band[0]) and min(q[3], band[3]) > max(q[1], band[1]):
                intr.append(p['name'])
        for d in fp['decaps']:
            q = d['rect']
            if d.get('kind') == 'mos' and min(q[2], band[2]) > max(q[0], band[0]) and min(q[3], band[3]) > max(q[1], band[1]):
                intr.append(d['name'])
    out['isolation_band'] = dict(rect=band, intruders=intr, ok=band is not None and not intr)
    # XT-04: D2H strip vs refbuf / adc_q bottom; RA-6/XT-05: corridor vs ADC east edges
    d2h = next(f['rect'] for f in fp['fixed'] if f['name'] == 'rsv_d2h_gearbox')
    cor = next(f['rect'] for f in fp['fixed'] if f['name'] == 'rsv_corridor_s')
    dac_south = [n for n in ('dac_i', 'dac_q') if r[n][1] < 1500.0]
    xt04 = dict(refbuf_gap_um=round(gap(r['refbuf'], d2h), 1), adc_q_gap_um=round(gap(r['adc_q'], d2h), 1),
                dac_bus_on_south_strip=bool(dac_south))
    xt04['ok'] = xt04['refbuf_gap_um'] >= LIMITS['strip_vs_vref_um'] and xt04['adc_q_gap_um'] >= LIMITS['strip_vs_vref_um']
    out['xt04_south_strip'] = xt04
    ra6 = dict(adc_i_um=round(gap(r['adc_i'], cor), 1), adc_q_um=round(gap(r['adc_q'], cor), 1))
    ra6['ok'] = min(ra6.values()) >= LIMITS['corridor_vs_adc_um']
    out['ra6_corridor_keepout'] = ra6
    return out


def rects(fp):
    out = {f['name']: f['rect'] for f in fp['fixed']}
    out.update({p['name']: p['rect'] for p in fp['placed']})
    return out


def orient(fp):
    return {p['name']: p.get('orient', 'R0') for p in fp['placed']}


def center(fp, name):
    r = rects(fp)
    if name.startswith('digital.'):
        d = r['digital']
        e = name.split('.')[1]
        return {'S': ((d[0]+d[2])/2, d[1]), 'N': ((d[0]+d[2])/2, d[3]), 'W': (d[0], (d[1]+d[3])/2),
                'E': (d[2], (d[1]+d[3])/2)}[e]
    if name.startswith('@'):
        x, y = name[1:].split(',')
        return (float(x), float(y))
    if name not in r:
        return None
    x = r[name]
    if name.startswith('pad_'):
        f = next(f for f in fp['fixed'] if f['name'] == name)
        if f.get('port_xy'):
            return tuple(f['port_xy'])
        return (x[2] if f['edge'] == 'west' else x[0], (x[1]+x[3])/2)
    return ((x[0]+x[2])/2, (x[1]+x[3])/2)


def gap(a, b):
    """Edge-to-edge distance between rects (0 when they touch or overlap)."""
    dx = max(b[0]-a[2], a[0]-b[2], 0.0)
    dy = max(b[1]-a[3], a[1]-b[3], 0.0)
    return (dx*dx+dy*dy)**0.5


def _cross(p1, p2, q1, q2):
    def ccw(a, b, c):
        return (c[1]-a[1])*(b[0]-a[0]) - (b[1]-a[1])*(c[0]-a[0])
    d1, d2 = ccw(q1, q2, p1), ccw(q1, q2, p2)
    d3, d4 = ccw(p1, p2, q1), ccw(p1, p2, q2)
    return d1*d2 < 0 and d3*d4 < 0


def evaluate(fp):
    r = rects(fp)
    o = orient(fp)
    res = {}
    # chains
    segs, chains = [], []
    for k, (name, hops, why) in enumerate(CHAINS):
        pts = [center(fp, h) for h in hops]
        missing = [h for h, p in zip(hops, pts) if p is None]
        hop = [abs(a[0]-b[0])+abs(a[1]-b[1]) for a, b in zip(pts, pts[1:])] if not missing else []
        chains.append(dict(chain=name, hops=hops, note=why, missing=missing, hop_manhattan_um=[round(h) for h in hop],
                           total_um=round(sum(hop)), max_hop_um=round(max(hop)) if hop else None))
        if not missing:
            segs += [(k, name, a, b) for (ha, a), (hb, b) in zip(zip(hops, pts), zip(hops[1:], pts[1:]))
                     if not (ha.startswith('@') and hb.startswith('@'))]   # waypoint-waypoint = shared corridor bus
    crossings = []
    for i in range(len(segs)):
        for j in range(i+1, len(segs)):
            if frozenset((segs[i][0], segs[j][0])) in MODE_EXCLUSIVE:
                continue
            if segs[i][1] != segs[j][1] and _cross(segs[i][2], segs[i][3], segs[j][2], segs[j][3]):
                crossings.append(f'{segs[i][1]}:{CHAINS[segs[i][0]][1]} x {segs[j][1]}:{CHAINS[segs[j][0]][1]} '
                                 f'at segs {tuple(round(v) for v in segs[i][2]+segs[i][3])} / '
                                 f'{tuple(round(v) for v in segs[j][2]+segs[j][3])}')
    res['chains'] = dict(chains=chains, crossings_between_chains=crossings,
                         ok=not crossings and all(not c['missing'] for c in chains))
    # isolation
    iso = []
    for a in AGGRESSORS:
        for v in VICTIMS:
            if a == v or a not in r or v not in r or (a, v) in DESIGNED_NEIGHBOURS:
                continue
            lim = LIMITS['min_aggressor_victim_um'].get(a, LIMITS['min_aggressor_victim_um']['default'])
            g = gap(r[a], r[v])
            iso.append(dict(aggressor=a, victim=v, gap_um=round(g, 1), limit_um=lim, ok=g >= lim))
    key = dict(lna_vs_digital=round(gap(r['lna'], r['digital'])), lna_vs_rfdriver=round(gap(r['lna'], r['rfdriver'])))
    res['isolation'] = dict(pairs=sorted(iso, key=lambda d: d['gap_um']), key=key,
                            fails=[f"{d['aggressor']}->{d['victim']} {d['gap_um']} < {d['limit_um']}" for d in iso if not d['ok']],
                            ok=all(d['ok'] for d in iso) and key['lna_vs_digital'] >= LIMITS['lna_vs_digital_um']
                            and key['lna_vs_rfdriver'] >= LIMITS['lna_vs_rfdriver_um'])
    # symmetry: I/Q mirrored (one MX, other R0) and mirror images about the axis between them
    sym = []
    for i_, q_ in IQ_PAIRS:
        a, b = r[i_], r[q_]
        mirrored = {o.get(i_), o.get(q_)} in ({'R0', 'MX'}, {'R90', 'M135'})
        lo, hi = (b, a) if b[1] < a[1] else (a, b)
        axis = (lo[3]+hi[1])/2
        # same column: left edges aligned (I/Q cells of one block family share the port corner), or centres aligned
        # for pairs whose I and Q masters differ in size (dac_i 275 vs dac_q 283 um)
        same_x = abs(a[0]-b[0]) < LIMITS['sym_tol_um'] or abs((a[0]+a[2])-(b[0]+b[2]))/2 < LIMITS['sym_tol_um']
        sym.append(dict(pair=f'{i_}/{q_}', orient=[o.get(i_), o.get(q_)], mirrored=mirrored, axis_y=round(axis, 2),
                        same_x=same_x, size_match=abs((a[3]-a[1])-(b[3]-b[1])) < 3.0, ok=mirrored and same_x))
    axes = {s['pair']: s['axis_y'] for s in sym}
    rx_axis_spread = max(axes[p] for p in ('rxmix_i/rxmix_q', 'bbfilter_i/bbfilter_q', 'adc_i/adc_q')) - \
        min(axes[p] for p in ('rxmix_i/rxmix_q', 'bbfilter_i/bbfilter_q', 'adc_i/adc_q'))
    res['symmetry'] = dict(pairs=sym, rx_chain_axis_spread_um=round(rx_axis_spread, 2),
                           ok=all(s['ok'] for s in sym) and rx_axis_spread <= 12.0)
    # pads
    def port_gap(b, p):
        q = center(fp, p)
        return gap(r[b], (q[0], q[1], q[0], q[1]))
    pads = [dict(block=b, pad=p, port_gap_um=round(port_gap(b, p), 1), family_gap_um=round(gap(r[b], r[p]), 1),
                 ok=port_gap(b, p) <= LIMITS['max_port_gap_um'])
            for b, p in PAD_BLOCKS if b in r and p in r]
    res['pads'] = dict(pairs=pads, ok=all(x['ok'] for x in pads))
    # digital pin facing
    d = r['digital']
    dig = []
    for group, (edge, consumers) in PIN_PLAN.items():
        for c in consumers:
            if c not in r:
                continue
            cx, cy = (r[c][0]+r[c][2])/2, (r[c][1]+r[c][3])/2
            if c in VIA_CORRIDOR and 'rsv_corridor_s' in r:
                cx, cy = (r['rsv_corridor_s'][0]+r['rsv_corridor_s'][2])/2, r['rsv_corridor_s'][3]
            # Manhattan route length from the consumer to each edge; a route cannot cross the macro, so reaching an
            # edge from the far side adds the shorter way around.
            lat_x = max(d[0]-cx, 0, cx-d[2]); lat_y = max(d[1]-cy, 0, cy-d[3])
            in_x = d[0] < cx < d[2]; in_y = d[1] < cy < d[3]
            around_x = min(cx-d[0], d[2]-cx) if in_x else 0.0
            around_y = min(cy-d[1], d[3]-cy) if in_y else 0.0
            dist = {'S': abs(cy-d[1])+lat_x+(0 if cy <= d[1] else 2*around_x),
                    'N': abs(cy-d[3])+lat_x+(0 if cy >= d[3] else 2*around_x),
                    'W': abs(cx-d[0])+lat_y+(0 if cx <= d[0] else 2*around_y),
                    'E': abs(cx-d[2])+lat_y+(0 if cx >= d[2] else 2*around_y)}
            dist = {k: max(v, 0.0) for k, v in dist.items()}
            near = min(dist, key=dist.get)
            dig.append(dict(group=group, consumer=c, planned_edge=edge, nearest_edge=near,
                            extra_um_via_planned=round(dist[edge]-dist[near]), ok=near == edge))
    res['digital_pin_facing'] = dict(pairs=dig, ok=all(x['ok'] for x in dig))
    if V4:
        res.update(v4_checks(fp))
    res['ok'] = all(v['ok'] for v in res.values() if isinstance(v, dict))
    return res


def negative_controls(fp):
    """Each rule must fail on a deliberately broken floorplan."""
    out = {}
    b = copy.deepcopy(fp)
    for p in b['placed']:
        if p['name'] == 'rxmix_q':
            p['orient'] = 'R0'
    out['symmetry_unmirrored_q_detected'] = not evaluate(b)['symmetry']['ok']
    b = copy.deepcopy(fp)
    for p in b['placed']:
        if p['name'] == 'lna':
            p['rect'] = [p['rect'][0]+1500, p['rect'][1], p['rect'][2]+1500, p['rect'][3]]
    out['pad_far_lna_detected'] = not evaluate(b)['pads']['ok']
    b = copy.deepcopy(fp)
    for p in b['placed']:
        if p['name'] == 'pll_host':
            dg = next(f['rect'] for f in b['fixed'] if f['name'] == 'digital')
            w, h = p['rect'][2]-p['rect'][0], p['rect'][3]-p['rect'][1]
            p['rect'] = [dg[0]-w-5, dg[1]+10, dg[0]-5, dg[1]+10+h]
    out['isolation_vco_at_macro_detected'] = not evaluate(b)['isolation']['ok']
    b = copy.deepcopy(fp)
    for p in b['placed']:            # swap the TX DAC across the RX chain -> crossing
        if p['name'] == ('dac_q' if V4 else 'dac_i'):
            p['rect'] = [2300.0, 600.0, 2310.0, 610.0]
    out['chain_crossing_detected'] = bool(evaluate(b)['chains']['crossings_between_chains'])
    if V4:
        b = copy.deepcopy(fp)
        for p in b['placed']:
            if p['name'] == 'adc_i':
                p['rect'] = [p['rect'][0], p['rect'][1]+120.0, p['rect'][2], p['rect'][3]+120.0]
        out['v4_sub01_floor_detected'] = not v4_checks(b)['register_distances']['sub01_floor_210_ok']
        b = copy.deepcopy(fp)
        for p in b['placed']:
            if p['name'] == 'lo_ext':
                p['rect'] = [p['rect'][0], p['rect'][1]+300.0, p['rect'][2], p['rect'][3]+300.0]
        out['v4_lo_leg_mismatch_detected'] = not v4_checks(b)['lo_legs']['ok']
        b = copy.deepcopy(fp)
        for f in b['fixed']:
            if f['name'] == 'pad_aux_clk':
                f['master'] = 'pad_refpad_old'
        out['v4_lo_pad_dc_detected'] = not v4_checks(b)['lo_legs']['ok']
        b = copy.deepcopy(fp)
        band = next(f['rect'] for f in b['fixed'] if f['name'] == 'rsv_isolation_band')
        for p in b['placed']:
            if p['name'] == 'wordclk':
                p['rect'] = [band[0]+50, band[1]+20, band[0]+250, band[1]+144]
        out['v4_isolation_band_intruder_detected'] = not v4_checks(b)['isolation_band']['ok']
        b = copy.deepcopy(fp)
        for p in b['placed']:
            if p['name'] == 'aosc':
                lna = next(q['rect'] for q in b['placed'] if q['name'] == 'lna')
                p['rect'] = [lna[0], lna[1]-80, lna[0]+200, lna[1]-15]
        out['v4_aosc_near_lna_detected'] = not v4_checks(b)['register_distances']['ok']
    out['ok'] = all(out.values())
    return out


if __name__ == '__main__':
    work = Path(sys.argv[1])
    fp = json.loads((work/'floorplan.json').read_text())
    res = evaluate(fp)
    res['negative_controls'] = negative_controls(fp)
    (work/'floorplan-rules.json').write_text(json.dumps(res, indent=1)+'\n')
    print(json.dumps({k: v['ok'] for k, v in res.items() if isinstance(v, dict)}),
          'crossings', res['chains']['crossings_between_chains'][:12])
    print('isolation fails', res['isolation']['fails'], res['isolation']['key'])
    print('pads', [(x['block'], x['pad'], x['port_gap_um']) for x in res['pads']['pairs'] if not x['ok']])
    print('symmetry', [(s['pair'], s['orient'], s['axis_y'], s['ok']) for s in res['symmetry']['pairs']],
          res['symmetry']['rx_chain_axis_spread_um'])
    print('digital', [(x['consumer'], x['planned_edge'], x['nearest_edge'], x['extra_um_via_planned']) for x in
                      res['digital_pin_facing']['pairs'] if not x['ok']])
    for c in res['chains']['chains']:
        print(c['chain'], c['total_um'], c['hop_manhattan_um'], c['missing'])
