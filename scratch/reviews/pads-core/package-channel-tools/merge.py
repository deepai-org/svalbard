"""Merge generator outputs into the spec/package-channel.json schema (this step was manual on 2026-11-10).
  merge.py check -> rebuild from the OLD generator outputs in scratch/cob and compare with the current spec file (regression)
  merge.py       -> build package-channel.new.json from the outputs in this directory.  Never writes into the project tree."""
import json, sys
R = '/home/ubuntu/svalbard/'
SPEC = R + 'projects/programmable_transceiver_platform/spec/package-channel.json'
OUT = R + 'scratch/pads-core/spec/'
def build(src, cur):
    L = lambda n: json.load(open(src + n))
    ch, pl, lo, lt, bc = L('channel.json'), L('placement.json'), L('lo_sweep.json'), L('lo_term_skew.json'), L('lo_bigC.json')
    g = ch['geometry']; nh = ch['bond_L_nH_per_mm']; ps = lt['ps_per_mm']; z0 = ch['microstrip']['z0_ohm']
    pins = {}
    for s in sorted(g, key=lambda s: g[s]['bond_pad']):
        p = g[s]
        pins[s] = dict(site=p['site'], cls=p['cls'], bond_pad=p['bond_pad'], board_net=p['board_net'],
                       connector_contact=p['connector_contact'], bond_mm=p['bond_mm'], bond_nH_0p83=round(p['bond_mm'] * nh, 2),
                       bond_nH_1p0=p['bond_mm'], trace_F_mm=p['f_mm'], trace_B_mm=p['b_mm'], trace_w_mm=p['trace_w_mm'], z0_ohm=z0,
                       vias=p['vias'], via_nH=p['via_nH'], connector_nH=p['conn_nH'], connector_dist_to_gnd_mm=p['conn_dist_gnd_mm'],
                       cob_delay_ps=round((p['f_mm'] + p['b_mm']) * ps, 1), min_spacing_F_mm=p['minsp_F_mm'],
                       min_spacing_B_mm=p['minsp_B_mm'], sparams=ch['sparams'][s], xtalk_dB=ch['xtalk_dB'][s])
    out = {}
    for k in cur:                                   # keep every top-level key, in the same order
        if k == 'pins': out[k] = pins
        elif k == 'supplies_grounds': out[k] = ch['supplies_grounds']
        elif k == 'pulse_2p5G_and_312M': out[k] = ch['pulse']
        elif k == 'intra_pair_and_group_skew': out[k] = lt['skew']
        elif k == 'placement_sweep':
            out[k] = dict(definition=cur[k]['definition'], rf_rx_match=pl['rf_rx_match'], rf_tx_match=pl['rf_tx_match'],
                          carrier_line_IL_dB_1p25G=pl['carrier_line_IL_dB_1p25G'], wired_rx_RL_vs_termination=pl['wired_rx_RL_vs_term'])
        elif k == 'lo': out[k] = dict(diff_gain_vs_padC_unterminated=lo, termination_effect=lt['lo_term'], larger_padC=bc)
        else: out[k] = cur[k]                       # status, date, sources, board, pdn, host_ssn, thermal: not map dependent
    return out
cur = json.load(open(SPEC))
if sys.argv[1:] == ['check']:
    old = build(R + 'scratch/cob/', cur)
    bad = [k for k in cur if old[k] != cur[k]]
    if 'pins' in bad:
        for s in cur['pins']:
            for f in cur['pins'][s]:
                if old['pins'][s].get(f) != cur['pins'][s][f]: print('  diff', s, f, old['pins'][s].get(f), cur['pins'][s][f])
    print('regression: merge of the old generator outputs == current spec file:', not bad, bad, list(old) == list(cur))
else:
    new = build(OUT, cur)
    new['date'] = '2026-11-14'
    new['sources'] = dict(cur['sources'], local_copy='scratch/cob/repo (clone), scratch/cob/raw.json; generator and merge of the 2026-11-14 '
                          'regeneration: scratch/pads-core/spec/{channel_model,placement,lo_sweep,lo_term,lo_bigc,merge,north_proof}.py')
    new['bond_map_notes'] = {
        'map': 'contract bond_map_current + decisions of 2026-11-14 (commit e995ce5): option L1 (REF_IN/REF_IN_N on inputs[3]/[2], '
               'BB_Q_P/BB_Q_N on inputs[7]/[6]); WCLK_IN pair deleted; LNA_SRC pads deleted',
        'POR_BYPASS': 'strap, east bidir[16].pad, bond 22, contact 58, provider gf180mcu_fd_io__in_c; static, the sparams/xtalk rows are '
                      'geometry bookkeeping only',
        'SPARE_E17': 'east bidir[17].pad, bond 23, contact 57: spare, HELD (candidate: receive one south-edge signal, option P2)',
        'TLP_TEST': 'TLP/ESD test site, east bidir[25].pad, bond 33, contact 47',
        'AGND_RX': 'two west extra openings beside RF_RX (gaps vss_pads[1]..RF_RX_P and RF_RX_N..BB_I_P): no board finger, no contact, '
                   'not one of the 74 bonds; not modelled here',
        'retired_names': ['WCLK_IN_P', 'WCLK_IN_N', 'WCLK_OBS', 'WDBG_OBS', 'ESD_TEST', 'LNA_SRC_P', 'LNA_SRC_N'],
        'north_edge_correction': 'the 2026-11-10 file listed all 16 north signals (H2D_D[0..9], H2D_CLK, CLK_OBS, DBG_OBS0/1, ATB0/1) on '
                                 'the mirror bond pad (n -> 92-n) with its net, contact and traces; corrected here (north_proof.py)',
        'bond_mm': "generator's own pad-centre estimate (211 um pitch on all edges), not the GDS openings; see BOND-AUDIT.md for audited lengths",
    }
    json.dump(new, open(OUT + 'package-channel.new.json', 'w'), indent=1)
    print('wrote', OUT + 'package-channel.new.json', 'keys', list(new), 'pins', len(new['pins']))
