#!/usr/bin/env python3
"""Conditional fundamental port loading with preserved current direction."""
import hashlib,json,sys
HALF="--half" in sys.argv
from pathlib import Path
import numpy as np
from rf_tone_fit import fit
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-quadrature-interface-half' if HALF else 'scratch/transceiver-quadrature-interface-current')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# Independent sign/scale contract: current INTO a known parallel RC.
f=2.5e9;t=np.linspace(40e-9,80e-9,10001);v=.001*np.cos(2*np.pi*f*t);i=v/400-.001*2*np.pi*f*100e-15*np.sin(2*np.pi*f*t)
zv,_=fit(t,v,[f]);zi,_=fit(t,i,[f]);assert abs(zi/zv-(1/400+1j*2*np.pi*f*100e-15))<1e-12
ap=P/('evidence/quadrature-interface-half.json' if HALF else 'evidence/quadrature-interface-current.json');audit=json.loads(ap.read_text())
out=dict(status='pending',completed=False,audit_sha256=sha(ap),phasor_sign_contract_verified=True,cases=[],limitations=['Fundamental current/voltage ratio for this driven periodically switching port with fixed sideband terminations, not a standalone LTI impedance model.','No-tone fitted leakage is reported but not divided into a physical admittance.','Single small input tone at nominal process, seeded ring/prebiased LNA; no noise, mismatch or broadband qualification.'])
if audit['completed']:
 rf=2.51542263e9
 for c in audit['provenance']['cases']:
  name=c['name']
  for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
  with (W/(name+'.dat')).open() as stream:header=stream.readline().lower().split()
  a=np.loadtxt(W/(name+'.dat'),skiprows=1);rows=[]
  for lo,hi in ((40,200),(80,200),(120,200)):
   w=a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)];t=w[:,0];sig=w[:,header.index('v(p)')]-w[:,header.index('v(n)')]
   k=np.flatnonzero((sig[:-1]<0)&(sig[1:]>=0));e=t[k]-sig[k]*np.diff(t)[k]/np.diff(sig)[k];assert len(e)>100
   flo=(len(e)-1)/(e[-1]-e[0]);fif=rf-flo
   for order in (4,8):
    fs=[rf,fif]+[j*flo for j in range(1,order+1)]+[rf+flo]
    v=w[:,header.index('v(mixrf)')];i=w[:,header.index('i(vsense)')];pv,rv=fit(t,v,fs);pi,ri=fit(t,i,fs)
    row=dict(window_ns=[lo,hi],lo_harmonic_fit_order=order,voltage_peak_v=float(abs(pv)),current_peak_a=float(abs(pi)),voltage_residual_rms_v=rv,current_residual_rms_a=ri)
    if name=='tone':
     y=pi/pv;z=1/y
     row.update(admittance_real_s=float(y.real),admittance_imag_s=float(y.imag),impedance_real_ohm=float(z.real),impedance_imag_ohm=float(z.imag),impedance_magnitude_ohm=float(abs(z)),current_lead_deg=float(np.angle(y,deg=True)))
    rows.append(row)
  out['cases'].append(dict(name=name,fits=rows))
 out.update(status='terminal_analysis',completed=True)
(P/('evidence/quadrature-interface-half-loading.json' if HALF else 'evidence/quadrature-interface-loading.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
for c in out['cases']:print(c['name'],c['fits'][0],c['fits'][-1])
