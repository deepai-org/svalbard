#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-driver-impedance'
r=json.loads((W/'result.json').read_text());assert len(r['cases'])==12
assert {(c['rail'],c['reservoir'],c['dc_load_a']) for c in r['cases']}=={(rail,cap,load) for rail,loads in (('high',(-.003,0,.015)),('low',(-.015,0,.003))) for cap in ('ideal10p','mim2048') for load in loads}
for path,digest in r['source_sha256'].items():assert hashlib.sha256((P/'analog'/path.removeprefix('/screen/')).read_bytes()).hexdigest()==digest
for c in r['cases']:
 name=c['name']
 for ext,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+ext)).read_bytes()).hexdigest()==digest
 d=(W/(name+'.spice')).read_text();assert f"ILOAD OUT 0 DC {c['dc_load_a']} AC 1" in d
 assert ('CRES OUT 0 10p' if c['reservoir']=='ideal10p' else 'XRES OUT 0 pt_ref_reservoir_2048') in d
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==3 and np.isfinite(a).all() and a[0,0]<=1e3 and a[-1,0]>=1e10
 z=np.hypot(a[:,1],a[:,2]);i=int(np.argmax(z));c.update(low_frequency_impedance_ohm=float(z[0]),peak_impedance_ohm=float(z[i]),peak_frequency_hz=float(a[i,0]),impedance_at_200mhz_ohm=float(np.interp(200e6,a[:,0],z)))
r['status']='reference_output_impedance_measured';r['phase_margin_verified']=False;r['limitations']=['Closed-loop impedance at selected fixed DC loads; no return-ratio or pole stability proof.', 'Linearization excludes large switching excursions, coupled reference paths and periodic operating points.', 'Ideal supply/target/current biases and compensation; nominal FET/MIM only.']
(P/'evidence/reference-driver-impedance.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps([{k:c[k] for k in ('name','low_frequency_impedance_ohm','peak_impedance_ohm','peak_frequency_hz')} for c in r['cases']],indent=2))
