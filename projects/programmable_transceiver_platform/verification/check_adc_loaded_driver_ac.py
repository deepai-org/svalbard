#!/usr/bin/env python3
"""Audit actual closed-loop AC response without claiming phase margin."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--damping",action="store_true");args=ap.parse_args()
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-adc-loaded-driver-ac'
if args.damping:W=R/'scratch/transceiver-adc-loaded-driver-ac-damping'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']
assert sha(R/'scratch/transceiver-adc-loaded-driver/loaded.spice')==r['baseline_deck_sha256']
assert [c['name'] for c in r['cases']]==['negative','center','positive']
rows=[]
for c in r['cases']:
 if args.damping:
  assert c['compensation_resistor_ohm']==1000
  assert 'RC X Z 1k' in (W/(c['name']+'.spice')).read_text()
 assert c['returncode']==0 and c['exact_reversal']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(c['name']+ext))==h
 p=W/(c['name']+'.dat')
 with p.open() as f:h=f.readline().lower().split()
 assert h==['frequency','dr','di','pr','plate_im']
 a=np.loadtxt(p,skiprows=1);assert a.shape==(701,5) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
 assert np.isclose(a[0,0],1e3) and np.isclose(a[-1,0],1e10)
 metrics={}
 for label,ix in [('driver',1),('plate',3)]:
  gain=np.hypot(a[:,ix],a[:,ix+1]);k=int(np.argmax(gain))
  metrics[label]=dict(low_frequency_gain=float(gain[0]),peak_gain=float(gain[k]),peak_frequency_hz=float(a[k,0]),peaking_db=float(20*np.log10(gain[k]/gain[0])))
 rows.append(dict(case=c['name'],source_voltages_v=c['source_voltages_v'],metrics=metrics))
out=dict(status='completed_loaded_closed_loop_ac_diagnostic',cases=rows,provenance=r,limitations=['AC about each static operating point; does not simulate the large input excursion.','Closed-loop peaking is not a return-ratio measurement, pole audit or phase-margin proof.','Ideal references, static code and always-on sampler remain; not ADC conversion qualification.'])
(P/('evidence/adc-loaded-driver-ac-damping.json' if args.damping else 'evidence/adc-loaded-driver-ac.json')).write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(rows,indent=2))
