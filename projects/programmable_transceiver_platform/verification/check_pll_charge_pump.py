#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'scratch/transceiver-pll-charge-pump';r=json.loads((W/'result.json').read_text())
assert len(r['cases'])==28
summary=[]
for voltage in sorted({c['output_v'] for c in r['cases']}):
 currents={}
 for c in [x for x in r['cases'] if x['output_v']==voltage]:
  p=W/f"{c['state']}_{voltage}.spice";assert hashlib.sha256(p.read_bytes()).hexdigest()==c['deck_sha256']
  currents[c['state']]=c['measurements']['i(vout)']
 assert currents['up']>0 and currents['down']<0 and abs(currents['off'])<1e-9
 assert abs(currents['both']-currents['up']-currents['down'])<1e-9
 summary.append(dict(output_v=voltage,source_a=currents['up'],sink_a=-currents['down'],both_on_residual_a=currents['both'],relative_imbalance=currents['both']/((currents['up']-currents['down'])/2)))
r['summary']=summary;r['dc_polarity_and_kcl_checks_pass']=True
(ROOT/'projects/programmable_transceiver_platform/evidence/pll-charge-pump-dc.json').write_text(json.dumps(r,indent=2)+'\n')
print('28 nominal DC cases checked; current polarity and branch consistency pass.')
