"""Reproducible layout generator for pt_rxmix_q (Magic PCells + routed M2-M5, see rfrx_flow.py).

Writes generated/rxmix_q.gds, generated/rxmix_q.mag (flat view), generated/rxmix_q.ext.spice
(extracted, parasitic C), generated/rxmix_q-lvs.txt and generated/rxmix_q-layout.json.
"""
import rfrx_flow

if __name__ == '__main__':
    r = rfrx_flow.generate('rxmix_q')
    print('rxmix_q', 'DRC', r['drc_count'], 'LVS', r['lvs']['final_result'], 'area_um2', r['area_um2'])
