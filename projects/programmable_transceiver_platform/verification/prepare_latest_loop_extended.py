#!/usr/bin/env python3
"""Extend only requested horizon of completed seeded latest-RF autonomous loop."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-latest-rf-loop';O=R/'scratch/transceiver-latest-rf-loop-extended-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=json.loads((P/'evidence/latest-rf-loop.json').read_text());assert e['completed'] and e['actual_stop_ns']>=3201
for ext,h in e['provenance']['artifacts_sha256'].items():assert sha(B/('latest'+ext))==h
base=(B/'latest.spice').read_text();old='tran 2p 3201n 0 2p uic';new='tran 2p 8001n 0 2p uic';assert base.count(old)==1
d=base.replace(old,new);assert d.replace(new,old)==base
O.mkdir(exist_ok=True);(O/'latest.spice').write_text(d)
m=dict(deck_sha256=sha(O/'latest.spice'),baseline_deck_sha256=sha(B/'latest.spice'),receiver_exact_reversal=True,horizon_only_reversal=True,requested_horizon_ns=8001,scope='Only stop time3201ns->8001ns; all circuits, timestep, method and seeded initial conditions unchanged.',comparison_windows_ns=[[3000,3100],[5000,5100],[7000,7100],[7900,8000]],limitations=['Longer seeded zero-RF history does not qualify startup, intrinsic noise or conversion.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');(P/'evidence/latest-loop-extended-preparation.json').write_text(json.dumps(m,indent=2)+'\n');print('horizon-only exact reversal verified')
