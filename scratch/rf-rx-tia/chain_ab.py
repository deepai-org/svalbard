"""Chain NF, old TIA (x1) vs new TIA (x2), same bench: lna_close.chain_point (extracted LNA extpr/extpp, real channel, LO = tb.LO_REAL)
with flow.GENERATED pointed at a copy whose only difference is rxmix_[iq].ext.spice.  Usage: chain_ab.py old|new IDX"""
import sys, json, hashlib
RX = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/rf_rx'
sys.path.insert(0, RX)
from pathlib import Path
S = Path('/home/ubuntu/svalbard/scratch/rf-rx-tia')
v, idx = sys.argv[1], int(sys.argv[2])
import rfrx_flow as flow
flow.GENERATED = S / f'gen_{v}'
import tb, lna_close as LC
tb.flow.GENERATED = flow.GENERATED
LC.OUT = S / 'w' / f'chain_{v}'
assert tb.HIBP == ''
# tb.chain_det takes the OTA noise from the SCHEMATIC analog/rf_rx/rxmix_i.spice (now x2): for the old row use the x1 schematic
if v == 'old':
    tb.SELFTEST_NETLIST['rxmix_i'] = S / 'rxmix_i_x1.spice'
    _nl = tb.netlist
    tb.netlist = lambda work, block, view: _nl(work, block, 'selftest' if (block == 'rxmix_i' and view == 'sch') else view)
view, c, lo = LC.CHAIN_POINTS[idx]
assert lo in tb.LO_REAL
r = LC.chain_point(view, c, lo)
r['tia'] = v
import os
assert os.environ.get('RFRX_LNA_SRC') is None
r['lna_src_in_workdir_sha'] = {str(q): hashlib.sha256(q.read_bytes()).hexdigest() for q in LC.OUT.rglob('lna_*_src.spice')}
r['rxmix_i_ext_sha'] = hashlib.sha256((flow.GENERATED / 'rxmix_i.ext.spice').read_bytes()).hexdigest()
r['lna_ext_sha'] = hashlib.sha256((flow.GENERATED / 'lna.ext.spice').read_bytes()).hexdigest()
with open(S / 'chain_ab.jsonl', 'a') as f:
    f.write(json.dumps(r, default=str) + '\n')
print(json.dumps(r, default=str))
