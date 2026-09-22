"""Saved control-node excursion diagnostic; not a transistor saturation test."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
e=P/'evidence/sar-reservoir-full.json';d=json.loads(e.read_text());assert d['completed'];rows=[]
for label,folder,name in [('baseline','adc-sar8-reference-reservoir','typical_first1'),('double','sar-reservoir-full','baseline')]:
 p=R/('scratch/transceiver-'+folder)/(name+'.dat');digest=sha(p)
 expected=d['waveform_sha256'] if label=='double' else json.loads((R/'scratch/transceiver-sar-reservoir-full-prepared/manifest.json').read_text())['donor_artifacts_sha256']['.dat'];assert digest==expected
 with p.open() as f:h=f.readline().lower().split()
 a=np.loadtxt(p,skiprows=1);t=a[:,0];frames=[]
 for hold in (70,120,170):
  mask=(t>=hold*1e-9)&(t<=(hold+39)*1e-9);tt=t[mask];nodes={}
  for rail in ('high','low'):
   y=a[:,h.index(f'v(xref.x{rail}.x)')];v=y[mask]
   near=(v<.1)|(v>3.2)
   nodes[rail]=dict(min_v=float(v.min()),max_v=float(v.max()),min_time_ns=float(tt[np.argmin(v)]*1e9),max_time_ns=float(tt[np.argmax(v)]*1e9),fraction_time_within_100mv_of_supply=float(np.trapezoid(near.astype(float),tt)/(tt[-1]-tt[0])),at_bit1_v=float(np.interp((hold+30.5)*1e-9,t,y)))
  frames.append(dict(hold_ns=hold,control_nodes=nodes))
 rows.append(dict(variant=label,waveform_sha256=digest,frames=frames))
out=dict(source_sha256=sha(e),results=rows,limitations=['100mV proximity is an explicit diagnostic marker, not device compliance or saturation criterion.','Saved X nodes omit tail/mirror internal nodes, bias voltages, device currents and VDSAT; internal headroom remains unproven.','No rail contact does not rule out current limiting, insufficient loop gain or large-signal slew.'])
(P/'evidence/reference-control-nodes.json').write_text(json.dumps(out,indent=2)+'\n')
for r in rows:
 for f in r['frames']:print(r['variant'],f['hold_ns'],f['control_nodes'])
