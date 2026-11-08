"""Reproducible layout generator for pt_rxmix_i (Magic PCells + routed M2-M5, see rfrx_flow.py).

Writes generated/rxmix_i.gds, generated/rxmix_i.mag (flat view), generated/rxmix_i.ext.spice
(extracted, parasitic C), generated/rxmix_i-lvs.txt and generated/rxmix_i-layout.json.
"""
import rfrx_flow

if __name__ == '__main__':
    r = rfrx_flow.generate('rxmix_i')
    print('rxmix_i', 'DRC', r['drc_count'], 'LVS', r['lvs']['final_result'], 'area_um2', r['area_um2'])
