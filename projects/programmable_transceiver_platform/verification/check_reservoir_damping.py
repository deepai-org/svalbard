#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-reservoir-damping';B=R/'scratch/transceiver-reference-driver-impedance'
r=json.loads((W/'result.json').read_text());base=json.loads((P/'evidence/reference-driver-impedance.json').read_text());assert len(r['cases'])==24
assert {(c['baseline_name'],c['resistance_ohm']) for c in r['cases']}=={(c['name'],v) for c in base['cases'] if c['reservoir']=='mim2048' for v in (.5,2,10,50)}
for path,digest in r['source_sha256'].items():assert hashlib.sha256((P/'analog'/path.removeprefix('/screen/')).read_bytes()).hexdigest()==digest
for c in r['cases']:
 name=c['name'];original=B/(c['baseline_name']+'.spice');assert hashlib.sha256(original.read_bytes()).hexdigest()==c['baseline_deck_sha256']
 for ext,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+ext)).read_bytes()).hexdigest()==digest
 d=(W/(name+'.spice')).read_text().replace(f"RDAMP OUT RES {c['resistance_ohm']}\nXRES RES 0 pt_ref_reservoir_2048",'XRES OUT 0 pt_ref_reservoir_2048').replace(f'/work/{name}.dat',f"/work/{c['baseline_name']}.dat")
 assert d==original.read_text()
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==3 and np.isfinite(a).all() and a[0,0]<=1e3 and a[-1,0]>=1e10
 z=np.hypot(a[:,1],a[:,2]);i=int(np.argmax(z));ref=next(x for x in base['cases'] if x['name']==c['baseline_name'])
 c.update(peak_impedance_ohm=float(z[i]),peak_frequency_hz=float(a[i,0]),baseline_peak_ohm=ref['peak_impedance_ohm'],impedance_at_200mhz_ohm=float(np.interp(200e6,a[:,0],z)),impedance_at_1ghz_ohm=float(np.interp(1e9,a[:,0],z)))
r['status']='controlled_reservoir_series_damping_audit';r['qualified_reference']=False;r['limitations']=['Series resistors are ideal exploratory elements, not sized PDK resistors.', 'AC at fixed DC loads; no phase-margin, nonlinear settling, startup/noise/mismatch or ADC accuracy proof.', 'Damping changes high-frequency bypass impedance; lower resonance peaks alone do not select a design.']
(P/'evidence/reference-reservoir-damping.json').write_text(json.dumps(r,indent=2)+'\n')
for resistance in (.5,2,10,50):
 rows=[c for c in r['cases'] if c['resistance_ohm']==resistance];print(resistance,'worst peak',max(c['peak_impedance_ohm'] for c in rows),'worst 200MHz',max(c['impedance_at_200mhz_ohm'] for c in rows),'worst1GHz',max(c['impedance_at_1ghz_ohm'] for c in rows))
