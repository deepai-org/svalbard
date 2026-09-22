#!/usr/bin/env python3
"""Observe internal reset nodes without modifying the failing extracted circuit."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import numpy as np
BASE=Path('/case'); OUT=Path('/work'); SRC=Path('/src')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((BASE/'result.json').read_text())
assert sha(BASE/'changing.spice')==r['source_sha256']['shifted_deck']
assert sha(BASE/'changing.dat')==r['shifted']['waveform_sha256']
pex=SRC/'lane_rx_regenerative_capture/lane_rx_regenerative_capture.pex.spice'
assert sha(pex)==r['source_sha256']['lane']
assert sha(Path('/baseline/pex/clock_pulse_generator.pex.spice'))==r['source_sha256']['pulse']
assert sha(SRC/'capture_clock_bridge/capture_clock_bridge.pex.spice')==r['source_sha256']['bridge']
lines=[line.split() for line in pex.read_text().splitlines() if line.startswith('X')]
def tail_gate(stem):
    candidates=[p for p in lines if len(p)>5 and p[1].startswith('XFRONT.XFE_E.NTAIL.') and p[2].startswith(stem+'.') and p[3].startswith('VSS') and p[5]=='nfet_03v3']
    assert candidates,stem
    return candidates[0]
tail=tail_gate('E_SENSE_CLK'); boost=tail_gate('E_SENSE_BOOST')
nodes=['E_SENSE_BOOST']+['XREGENCAP.XFRONT.XFE_E.'+s+'.t0' for s in ('XP','XN','NIP','NIN','NTAIL')]+['XREGENCAP.'+tail[2],'XREGENCAP.'+boost[2]]
for node in nodes[1:]:
    assert node.removeprefix('XREGENCAP.') in pex.read_text().split()
deck=(BASE/'changing.spice').read_text()
oldline=next(line for line in deck.splitlines() if line.startswith('wrdata '))
newline=oldline+' '+' '.join('v('+n+')' for n in nodes)
deck=deck.replace(oldline,newline)
(OUT/'changing.spice').write_text(deck)
with (OUT/'changing.log').open('w') as log:
    subprocess.run(['ngspice','-b',str(OUT/'changing.spice')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
x=np.loadtxt(OUT/'changing.dat',skiprows=1)
y=np.loadtxt(BASE/'changing.dat',skiprows=1)
assert x.shape[1]==24 and x.shape[0]==y.shape[0]
assert np.isfinite(x).all() and np.array_equal(x[:,:16],y), 'Observation changed original waveform'
result=dict(status='internal_observation_not_lane_qualification',baseline_source_sha256=r['source_sha256'],
    source_sha256=dict(runner=sha(Path(__file__)),baseline_case=sha(BASE/'result.json'),deck=sha(OUT/'changing.spice'),waveform=sha(OUT/'changing.dat')),
    appended_columns={str(16+i):node for i,node in enumerate(nodes)},
    selected_tail_devices=dict(sense=tail,boost=boost),
    original_waveform_columns_bitwise_identical=True,baseline_wrong_bits=6,
    note='XP/XN/NIP/NIN/NTAIL t0 are named extracted observation points, not a claim of identical voltage over every parasitic segment.',
    environment=r['environment'])
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
