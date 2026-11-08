"""Reproducible layout generator for pt_bb_tap (Magic PCells + routed M2-M5, see rfrx_flow.py).

Writes generated/bb_tap.gds, generated/bb_tap.mag (flat view), generated/bb_tap.ext.spice
(extracted, parasitic C), generated/bb_tap-lvs.txt and generated/bb_tap-layout.json.
"""
import rfrx_flow

if __name__ == '__main__':
    r = rfrx_flow.generate('bb_tap')
    print('bb_tap', 'DRC', r['drc_count'], 'LVS', r['lvs']['final_result'], 'area_um2', r['area_um2'])
