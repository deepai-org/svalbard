"""Generate rxmix_i / rxmix_q with the HEAD lna_layout.py (the working-tree copy carries the LNA owner's in-progress WIDE routing)."""
import sys; sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx/../../scratch/rf-rx-tia/headlib'); sys.path.insert(1, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx')
import lna_layout; assert 'headlib' in lna_layout.__file__
import rfrx_flow
for b in sys.argv[1:]:
    r = rfrx_flow.generate(b)
    print(b, 'DRC', r['drc_count'], 'LVS', r['lvs']['final_result'], 'area_um2', r['area_um2'], 'klayout', r.get('klayout_drc'), r.get('klayout_precheck'), flush=True)
