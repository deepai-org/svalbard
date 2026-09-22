#!/usr/bin/env python3
"""Diagnostic hard-disabled receiver BOOST; generator output load changes explicitly."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import numpy as np
BASE=Path('/case'); OUT=Path('/work'); SRC=Path('/src')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
parent=json.loads((BASE/'result.json').read_text())
assert sha(BASE/'changing.spice')==parent['source_sha256']['deck']
for k,p in dict(pulse=Path('/baseline/pex/clock_pulse_generator.pex.spice'),bridge=SRC/'capture_clock_bridge/capture_clock_bridge.pex.spice',lane=SRC/'lane_rx_regenerative_capture/lane_rx_regenerative_capture.pex.spice').items():
    assert sha(p)==parent['baseline_source_sha256'][k]
deck=(BASE/'changing.spice').read_text()
match=re.search(r'^XREGENCAP .*?(?=\n[^+])',deck,re.M|re.S); assert match
instance=match[0]
assert instance.count('E_SENSE_BOOST')==1 and instance.count('O_SENSE_BOOST')==1
replacement=instance.replace('E_SENSE_BOOST','0').replace('O_SENSE_BOOST','0')
deck=deck[:match.start()]+replacement+deck[match.end():]
(OUT/'changing.spice').write_text(deck)
with (OUT/'changing.log').open('w') as log:
    subprocess.run(['ngspice','-b',str(OUT/'changing.spice')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
x=np.loadtxt(OUT/'changing.dat',skiprows=1); t=x[:,0]
assert x.shape[1]==24 and t[-1]>=16.999e-9 and np.isfinite(x).all()
result=dict(status='boost_disabled_diagnostic_not_qualified_fix',environment=parent['environment'],
    source_sha256=dict(runner=sha(Path(__file__)),baseline_record=sha(BASE/'result.json'),baseline_deck=sha(BASE/'changing.spice'),deck=sha(OUT/'changing.spice'),waveform=sha(OUT/'changing.dat')),
    macro_sha256={k:parent['baseline_source_sha256'][k] for k in ('pulse','bridge','lane')},
    change='Only the two receiver BOOST input ports are wired to ground; pulse-generator BOOST outputs remain present but lose their receiver gate loads.',
    limitations=['Not timing-identical to baseline: real pulse generator sees changed loads.',
                 'Hardwired diagnostic, not an implemented programmable disable circuit.',
                 'Ideal upstream clock, pin data and DC biases; one pattern and nominal environment.'],
    appended_columns=parent['appended_columns'])
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print('BOOST-disabled transient completed')
