import json
R='/home/ubuntu/svalbard/'
o=json.load(open(R+'projects/programmable_transceiver_platform/spec/package-channel.json')); n=json.load(open('package-channel.new.json'))
m=json.load(open('site_to_bond.json'))['site_to_bond']
assert all(m[p['site']]==p['bond_pad'] for p in n['pins'].values())
ren={'POR_BYPASS':'WCLK_IN_P','SPARE_E17':'WCLK_IN_N','USB_DN':'WCLK_OBS','USB_DP':'WDBG_OBS','TLP_TEST':'ESD_TEST'}
L=[]
L.append('| Signal | Old: site / bond / contact | New: site / bond / contact | Old F+B mm (delay ps) | New F+B mm (delay ps) | bond mm old -> new | cls old -> new | Change |')
L.append('|---|---|---|---|---|---|---|---|')
for s,p in n['pins'].items():
    q=o['pins'].get(s) or o['pins'].get(ren.get(s,''))
    f=lambda x:f"{x['site'].replace('.pad','')} / {x['bond_pad']} / {x['connector_contact']}"
    t=lambda x:f"{x['trace_F_mm']}+{x['trace_B_mm']}={x['trace_F_mm']+x['trace_B_mm']:.2f} ({x['cob_delay_ps']})"
    geo_same = q and all(q[k]==p[k] for k in ('site','bond_pad','connector_contact','trace_F_mm','trace_B_mm','bond_mm'))
    if s in ren: ch='renamed from '+ren[s]+('' if q['cls']==p['cls'] else '; class and sparams change')
    elif geo_same: ch='none' if q['sparams']==p['sparams'] and set(q['xtalk_dB'])==set(p['xtalk_dB']) else 'xtalk partner names only'
    elif q['site']==p['site']: ch='NORTH FIX: site kept, bond/net/contact/traces corrected'
    else: ch='site moved (map)'
    L.append(f"| {s} | {f(q)} | {f(p)} | {t(q)} | {t(p)} | {q['bond_mm']} -> {p['bond_mm']} | {q['cls']} -> {p['cls']} | {ch} |")
open('diff_pins.md','w').write('\n'.join(L)+'\n')
print(len(L)-2,'rows'); 
print('\n'.join(l for l in L if 'none' not in l.split('|')[-2])[:6000])
print('SKEW'); 
for k in sorted(set(o['intra_pair_and_group_skew'])|set(n['intra_pair_and_group_skew'])):
    a=o['intra_pair_and_group_skew'].get(k); b=n['intra_pair_and_group_skew'].get(k)
    if a!=b: print(k,a,'->',b)
for k in o:
    if k not in ('pins','intra_pair_and_group_skew') and o[k]!=n.get(k): print('top-level changed:',k)
print('rf_tx strip', o['placement_sweep']['rf_tx_match']['strip'], n['placement_sweep']['rf_tx_match']['strip'])
print('rf_tx car30', o['placement_sweep']['rf_tx_match']['car30mm'], n['placement_sweep']['rf_tx_match']['car30mm'])
print('rf_rx same', o['placement_sweep']['rf_rx_match']==n['placement_sweep']['rf_rx_match'])
for k in ('C1.0pF_car30mm','C1.5pF_car30mm'): print(k, o['lo']['diff_gain_vs_padC_unterminated'][k]['2.45'], n['lo']['diff_gain_vs_padC_unterminated'][k]['2.45'], o['lo']['diff_gain_vs_padC_unterminated'][k]['bond_pm0p3_dB'], n['lo']['diff_gain_vs_padC_unterminated'][k]['bond_pm0p3_dB'])
print(o['lo']['termination_effect'],'\n',n['lo']['termination_effect'])
print(o['lo']['larger_padC']['C2.5pF R5000'], n['lo']['larger_padC']['C2.5pF R5000'])
print('pulse', {k:(o['pulse_2p5G_and_312M'].get(k)==n['pulse_2p5G_and_312M'].get(k)) for k in set(o['pulse_2p5G_and_312M'])|set(n['pulse_2p5G_and_312M'])})
print(o['pulse_2p5G_and_312M']['H2D_CLK'], n['pulse_2p5G_and_312M']['H2D_CLK'])
for s in ('H2D_CLK','H2D_D[0]','H2D_D[9]','CLK_OBS','ATB0','ATB1','RF_TX_P','RF_TX_N','REF_IN','REF_IN_N','BB_Q_P','AUX_CLK_N','SPARE_E17','RESET_N','HOST_MISO','HOST_CS_N','D2H_D[9]'):
    p=n['pins'][s]; print(s, p['bond_pad'],p['connector_contact'],p['trace_F_mm'],p['trace_B_mm'],p['cob_delay_ps'],p['bond_mm'],p['connector_dist_to_gnd_mm'],p['connector_nH'],p['min_spacing_F_mm'],p['min_spacing_B_mm'], list(p['xtalk_dB']), p['sparams']['156.25MHz'])
