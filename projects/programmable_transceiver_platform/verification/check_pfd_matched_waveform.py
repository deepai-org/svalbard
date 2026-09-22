#!/usr/bin/env python3
"""Audit numerical reproducer outcomes without promoting completion to PLL success."""
import hashlib,json,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-pfd-matched-waveform';B=R/'scratch/transceiver-pfd-pump-breakpoint'
manifest=json.loads((W/'manifest.json').read_text());source=B/'pwl_skew0.spice';original=source.read_text();assert hashlib.sha256(source.read_bytes()).hexdigest()==manifest['baseline_deck_sha256']
for path,digest in manifest['source_sha256_before'].items():
 if path.startswith('/screen/'):assert hashlib.sha256((P/'analog'/path.removeprefix('/screen/')).read_bytes()).hexdigest()==digest
complete=(W/'result.json').exists();file=W/('result.json' if complete else 'progress.json');raw=json.loads(file.read_text()) if file.exists() else {'cases':[]};rows=[]
for c in raw['cases']:
 name=c['name']
 for ext,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+ext)).read_bytes()).hexdigest()==digest
 d=(W/(name+'.spice')).read_text();restored=d.split('.control')[0]
 if name=='matched':
  new=next(x for x in d.splitlines() if x.startswith('VFB '));ref=next(x for x in d.splitlines() if x.startswith('VREF '));assert new.replace('VFB FB ','VREF REF ',1)==ref
  old=next(x for x in original.splitlines() if x.startswith('VFB '));restored=restored.replace(new,old)
 else:assert name=='mixed'
 assert restored==original.split('.control')[0] and 'tran 2p 800n 0 2p uic' in d
 log=(W/(name+'.log')).read_text();a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==7 and np.isfinite(a).all()
 done=c['returncode']==0 and 'aborted' not in log and a[-1,0]>=800e-9
 failure=re.search(r'Timestep too small; time = ([0-9.e+-]+)',log)
 c.update(completed_requested_horizon=bool(done),actual_stop_ns=float(a[-1,0]*1e9),failure_time_ns=float(failure.group(1))*1e9 if failure else None,max_reference_feedback_difference_v=float(np.max(abs(a[:,1]-a[:,2]))),control_range_v=[float(a[:,5].min()),float(a[:,5].max())])
 if not done:
  c['last_saved_state']={key:float(a[-1,col]) for key,col in (('reference_v',1),('feedback_v',2),('up_v',3),('dn_v',4),('control_v',5),('pump_current_a',6))}
 rows.append(c)
if complete:assert raw['source_sha256_before']==raw['source_sha256_after']==manifest['source_sha256_before'] and {c['name'] for c in rows}=={'mixed','matched'}
r=dict(status='complete_clock_representation_diagnostic' if complete else 'partial_clock_representation_diagnostic',cases=rows,source_sha256_before=manifest['source_sha256_before'],limitations=['Reduced actual PFD/pump/filter only; excludes oscillator/divider and RF load.', 'Identical ideal clocks are a diagnostic scenario, not realistic independent clocks or jitter.', 'No simulator-bug attribution, metastability, autonomous lock/noise or silicon qualification.'])
(P/'evidence/pfd-matched-waveform-screen.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,indent=2))
