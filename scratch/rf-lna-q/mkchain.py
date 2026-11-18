"""Collect the e15 chain results (same calls as lna_close.chain_point, run from scratch while the slots were shared) into close/chain.json."""
import json, glob, sys
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx')
import tb
C = {'tt': ['typical', 27, 3.3], 'ss': ['ss', 32, 3.15]}
rows = []
for f in sorted(glob.glob('/home/ubuntu/svalbard/scratch/rf-lna-q/e15_*.json')):
    v, c, d, lo = f.split('/')[-1][4:-5].split('_', 3)
    r = json.load(open(f))
    rows.append(dict(view=v, corner=C[c], lo=lo, lo_level=tb.LO_REAL.get(lo), carrier_distance_mm=float(d), nf_dsb_db=r.get('nf_dsb_db'), nf_ssb_db=r.get('nf_ssb_db'),
                     gain_sig_db=r.get('gain_sig_db'), f_parts=r.get('f_parts'), run_by='scratch/rf-lna-q/e15.py (same calls as lna_close.chain_point)'))
json.dump(rows, open('/home/ubuntu/svalbard/scratch/rf_rx/close/chain.json', 'w'), indent=1)
print([(r['view'], r['corner'][0], r['lo'], round(r['nf_dsb_db'], 2)) for r in rows])
