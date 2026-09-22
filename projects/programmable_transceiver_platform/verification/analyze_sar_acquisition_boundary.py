"""Localize input/held error around original sampling transition, without causal claims."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';E=P/'evidence/sar-reference-clamped.json';d=json.loads(E.read_text());assert d['completed'] and d['clamps_verified']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for variant,folder,name in [('baseline','adc-sar8-reference-reservoir','typical_first1'),('clamped','sar-reference-clamped','baseline')]:
 p=R/('scratch/transceiver-'+folder)/(name+'.dat')
 expected=d['waveform_sha256'] if variant=='clamped' else json.loads((R/'scratch/transceiver-sar-reference-clamped-prepared/manifest.json').read_text())['donor_artifacts_sha256']['.dat'];assert sha(p)==expected
 with p.open() as f:h=f.readline().lower().split()
 a=np.loadtxt(p,skiprows=1);t=a[:,0]
 def at(n,ns):return float(np.interp(ns*1e-9,t,a[:,h.index('v('+n+')')]))
 for hold,target in [(70,.4),(120,-.4),(170,.4)]:
  samples=[]
  for offset in (-1,-.1,0,.1,.2,.5):
   ns=hold+offset;drive=at('ip',ns)-at('in',ns);held=at('hp',ns)-at('hn',ns)
   samples.append(dict(offset_ns=offset,driver_diff_v=drive,held_diff_v=held,driver_error_v=drive-target,held_minus_driver_v=held-drive,total_held_error_v=held-target))
  rows.append(dict(variant=variant,hold_ns=hold,target_v=target,samples=samples,held_change_open_to_clock_v=samples[-1]['held_diff_v']-samples[2]['held_diff_v']))
out=dict(source_sha256=sha(E),results=rows,limitations=['Sampling control ramps from hold to hold+0.1ns; command mask changes concurrently, so edge-associated error is not uniquely switch injection.','Driver is unloaded as switch opens; later driver-minus-held differences are not tracking errors.','Nominal two-level sequence; no input-frequency/noise/mismatch qualification.'])
(P/'evidence/sar-acquisition-boundary.json').write_text(json.dumps(out,indent=2)+'\n')
for r in rows:print(r['variant'],r['hold_ns'],'before edge',r['samples'][2],'edge to clock',r['held_change_open_to_clock_v'])
