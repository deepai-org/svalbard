#!/usr/bin/env python3
"""Decap of one chip against the full 5.4 nF plan (spec/power-delivery.md 4.2; split decision D9: full plan on both chips).
    CHIP=rf|wired python3 decap.py         (after a first ledger.py pass; ledger.py then books the tiles)
Per scenario (as built / targets / lower bounds): grid MIM over the block outlines (Metal4/Metal5-free area of the measured
layouts, same method as overheads.py section 3: plates on 55 % of the usable free area at 1.9 fF/um2, half of the
sensitive blocks' area unused, spirals excluded), macro row fill scaled with the chip's macro outline (0.45 nF at
2.814 mm2), bond-site tiles scaled with the chip's custom pad sites (0.45 nF for 24 sites), the 1.5 nF macro-edge bank;
the rest of 5.4 nF as stacked MOS + MIM tiles at 4 fF/um2. Output: decap.json (both chips kept)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__)); CHIP = os.environ['CHIP']
L = json.load(open(f'{HERE}/{CHIP}/ledger.json')); MSD = json.load(open(f'{HERE}/meas/measured.json'))
SPIRAL = {'pt_lc_qvco5', 'pt_lna_ind', 'pt_lna_deg'}
SENS = {'pt_adc_i', 'pt_adc_q', 'pt_bbfilter_i', 'pt_bbfilter_q', 'pt_lna', 'pt_rxmix_i', 'pt_rxmix_q', 'pt_lo_lf', 'pt_lo_pfdcp', 'pt_refbuf'}
PLAN, BANK, ROW_NF, ROW_MACRO, BOND_NF, BOND_SITES, TILE_FF_UM2 = 5.4, 1.5, 0.45, 2.814e6, 0.45, 24, 4.0
macro = next(r for r in L['rows'] if r['master'] == 'pt_digital_macro')
sites = sum(2 if r['master'] in ('pad_rf_pair', 'pad_rftxpad', 'pad_refpad', 'pad_hspad', 'pad_wirepad', 'pad_txpad') else 1
            for r in L['rows'] if r['kind'] == 'pad' or r['master'] in ('pad_single_leg', 'pad_tlp'))
out = dict(chip=CHIP, plan_nF=PLAN, custom_pad_sites=sites, scenarios={})
tiles = {}
for scen, key in (('asbuilt', 'asbuilt_um2'), ('target', 'target_um2'), ('lb', 'lb_um2')):
    usable = 0.0; nodata = 0.0
    for r in L['rows']:
        m = r['master']; a = r[key]
        if a <= 0 or r['kind'] in ('pad', 'booked') or m.startswith(('pad_', 'prov', 'atb_provider', 'pt_host', 'pt_debug')) or m == 'pt_digital_macro': continue
        v = MSD.get(r['mkey']) if r['mkey'] else None
        if v is None: nodata += a; continue
        free = max(0.0, v['m45free20'] - (r['asbuilt_um2'] - a))
        if m not in SPIRAL: usable += free*(0.5 if m in SENS else 1.0)
    grid = usable*0.55*1.9/1e6                      # nF
    row = ROW_NF*macro[key]/ROW_MACRO
    bond = BOND_NF*sites/BOND_SITES
    rest = max(0.0, PLAN-BANK-grid-row-bond)
    tiles[scen] = round(rest*1e6/TILE_FF_UM2)
    out['scenarios'][scen] = dict(grid_mim_nF=round(grid, 2), row_fill_nF=round(row, 2), bond_site_nF=round(bond, 2), bank_nF=BANK,
                                  tiles_nF=round(rest, 2), tiles_mm2=round(tiles[scen]/1e6, 3), blocks_without_m45_data_mm2=round(nodata/1e6, 3))
out['tiles_um2'] = tiles
D = json.load(open(f'{HERE}/decap.json')) if os.path.exists(f'{HERE}/decap.json') else {}
D[CHIP] = out; json.dump(D, open(f'{HERE}/decap.json', 'w'), indent=1)
print(json.dumps(out, indent=1))
