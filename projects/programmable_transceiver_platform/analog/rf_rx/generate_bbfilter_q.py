"""Reproducible layout generator for pt_bbfilter_q (Magic PCells + routed M2-M5, see rfrx_flow.py).

Writes generated/bbfilter_q.gds, generated/bbfilter_q.mag (flat view), generated/bbfilter_q.ext.spice
(extracted, parasitic C), generated/bbfilter_q-lvs.txt and generated/bbfilter_q-layout.json.
"""
import rfrx_flow

if __name__ == '__main__':
    r = rfrx_flow.generate('bbfilter_q')
    print('bbfilter_q', 'DRC', r['drc_count'], 'LVS', r['lvs']['final_result'], 'area_um2', r['area_um2'])
