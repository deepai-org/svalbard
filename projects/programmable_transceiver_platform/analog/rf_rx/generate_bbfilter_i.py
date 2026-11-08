"""Reproducible layout generator for pt_bbfilter_i (Magic PCells + routed M2-M5, see rfrx_flow.py).

Writes generated/bbfilter_i.gds, generated/bbfilter_i.mag (flat view), generated/bbfilter_i.ext.spice
(extracted, parasitic C), generated/bbfilter_i-lvs.txt and generated/bbfilter_i-layout.json.
"""
import rfrx_flow

if __name__ == '__main__':
    r = rfrx_flow.generate('bbfilter_i')
    print('bbfilter_i', 'DRC', r['drc_count'], 'LVS', r['lvs']['final_result'], 'area_um2', r['area_um2'])
