"""Reproducible layout generator for pt_lna (Magic PCells + routed M2-M5, see rfrx_flow.py).

Writes generated/lna.gds, generated/lna.mag (flat view), generated/lna.ext.spice
(extracted, parasitic C), generated/lna-lvs.txt and generated/lna-layout.json.
"""
import rfrx_flow

if __name__ == '__main__':
    r = rfrx_flow.generate('lna')
    print('lna', 'DRC', r['drc_count'], 'LVS', r['lvs']['final_result'], 'area_um2', r['area_um2'])
