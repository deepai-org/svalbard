#!/usr/bin/env python3
"""Weighted multitone fits; no-tone controls, no noise or broadband IRR claim."""
import hashlib,json,sys
LNA="--lna" in sys.argv
FINAL="--final-stage" in sys.argv
assert not FINAL or LNA
ACCOUPLED="--ac-coupled" in sys.argv
assert not ACCOUPLED or (LNA and FINAL)
HALF="--half-mixer" in sys.argv
assert not HALF or (LNA and FINAL and not ACCOUPLED)
FILTER="--filter" in sys.argv
assert not FILTER or (LNA and FINAL and not ACCOUPLED and not HALF)
SETTLING="--settling" in sys.argv
assert not SETTLING or FILTER
BYPASS="--bypass" in sys.argv
LEVEL10="--level10" in sys.argv
assert not LEVEL10 or BYPASS
assert not BYPASS or SETTLING
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-bb-connected-level10' if LEVEL10 else 'scratch/transceiver-bb-connected-bypass' if BYPASS else 'scratch/transceiver-bb-connected-settling' if SETTLING else 'scratch/transceiver-bb-connected' if FILTER else 'scratch/transceiver-quadrature-interface-half' if HALF else 'scratch/transceiver-quadrature-lna-ac' if ACCOUPLED else 'scratch/transceiver-quadrature-lna-final' if FINAL else 'scratch/transceiver-quadrature-lna' if LNA else 'scratch/transceiver-quadrature-mixers')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
from rf_tone_fit import fit
# Known noncoherent low-frequency component with independent DC/drift/RF tones.
t=np.linspace(40e-9,200e-9,16001);freqs=[20e6,2.5e9,2.52e9]
y=.4+.01*(t-t.mean())/(t[-1]-t[0])+.003*np.cos(2*np.pi*freqs[0]*t)+.004*np.sin(2*np.pi*freqs[0]*t)+.1*np.cos(2*np.pi*freqs[1]*t)+.02*np.sin(2*np.pi*freqs[2]*t)
z,res=fit(t,y,freqs);assert abs(z-(.003-.004j))<1e-12 and res<1e-12
audit_path=P/('evidence/bb-connected-level10.json' if LEVEL10 else 'evidence/bb-connected-bypass.json' if BYPASS else 'evidence/bb-connected-settling.json' if SETTLING else 'evidence/bb-connected.json' if FILTER else 'evidence/quadrature-interface-half.json' if HALF else 'evidence/quadrature-lna-ac.json' if ACCOUPLED else 'evidence/quadrature-lna-final.json' if FINAL else 'evidence/quadrature-lna.json' if LNA else 'evidence/quadrature-mixers.json');audit=json.loads(audit_path.read_text())
out=dict(completed=False,status='pending',audit_sha256=sha(audit_path),measurement_contract_verified=True,cases=[],limitations=['Finite-record deterministic tone fitting; residual is not noise and no ENOB/EVM/receiver sensitivity claim.','Ideal RF source and baseband loads; no LNA/filter/ADC, actual bias generation or autonomous PLL.','Fit-order and window comparisons test leakage sensitivity, not complete distortion or broadband image rejection.'])
if audit['completed']:
 manifest=json.loads((W/'manifest.json').read_text());rf=2.51542263e9 if HALF else manifest['rf_hz']
 if HALF:
  for case in audit['provenance']['cases']:
   assert f"VRF RFS 0 SIN(0 {case['amplitude_v']} 2.51542263g)" in (W/(case['name']+'.spice')).read_text()
 for c in audit['provenance']['cases']:
  for ext,h in c['artifacts_sha256'].items():assert sha(W/(c['name']+ext))==h
  with (W/(c['name']+'.dat')).open() as f:header=f.readline().lower().split()
  a=np.loadtxt(W/(c['name']+'.dat'),skiprows=1);results=[]
  for lo,hi in (((40,200),(120,200),(240,320),(320,400),(240,400)) if SETTLING else ((40,200),(80,200),(120,200))):
   w=a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)];t=w[:,0]
   def v(n):return w[:,header.index('v('+n.lower()+')')]
   signal=v('P')-v('N');k=np.flatnonzero((signal[:-1]<0)&(signal[1:]>=0));e=t[k]-signal[k]*np.diff(t)[k]/np.diff(signal)[k];assert len(e)>100
   flo=float((len(e)-1)/(e[-1]-e[0]));fif=rf-flo;assert fif>0
   for order in (4,8):
    frequencies=[fif]+[n*flo for n in range(1,order+1)]+[rf,rf+flo]
    zi,ri=fit(t,v('MIP')-v('MIN'),frequencies);zq,rq=fit(t,v('MQP')-v('MQN'),frequencies)
    zr,_=fit(t,v('RF'),[rf]+[f for f in frequencies if f!=rf])
    lna_metrics={}
    if LNA:
     zg,_=fit(t,v('LG'),[rf]+[f for f in frequencies if f!=rf])
     lna_metrics=dict(lna_gate_tone_peak_v=float(abs(zg)),drain_over_gate_tone_gain=float(abs(zr/zg)) if c["amplitude_v"] and abs(zg)>0 else None,i_if_over_drain_tone=float(abs(zi/zr)) if c["amplitude_v"] and abs(zr)>0 else None,q_if_over_drain_tone=float(abs(zq/zr)) if c["amplitude_v"] and abs(zr)>0 else None)
    if ACCOUPLED:
     zm,_=fit(t,v('MRFIN'),[rf]+[f for f in frequencies if f!=rf])
     lna_metrics.update(mixer_input_tone_peak_v=float(abs(zm)),mixer_input_mean_v=float(np.trapezoid(v('MRFIN'),t)/(t[-1]-t[0])))
    if FILTER:
     fi,fri=fit(t,v('FIP')-v('FIN'),frequencies);fq,frq=fit(t,v('FQP')-v('FQN'),frequencies)
     lna_metrics.update(filter_i_peak_v=float(abs(fi)),filter_q_peak_v=float(abs(fq)),filter_i_residual_rms_v=fri,filter_q_residual_rms_v=frq,filter_i_gain_from_source=float(abs(fi)/c['amplitude_v']) if c['amplitude_v'] else None,filter_q_gain_from_source=float(abs(fq)/c['amplitude_v']) if c['amplitude_v'] else None,filter_q_over_i=float(abs(fq/fi)) if c['amplitude_v'] and abs(fi)>0 else None,filter_q_phase_deg=float(np.angle(fq/fi,deg=True)) if c['amplitude_v'] and abs(fi)>0 else None)
    results.append(dict(**lna_metrics,window_ns=[lo,hi],lo_frequency_hz=flo,if_frequency_hz=fif,if_cycles=float((t[-1]-t[0])*fif),lo_harmonic_fit_order=order,i_peak_v=float(abs(zi)),q_peak_v=float(abs(zq)),rf_node_tone_peak_v=float(abs(zr)),rf_node_time_mean_v=float(np.trapezoid(v('RF'),t)/(t[-1]-t[0])),i_gain_from_source=float(abs(zi)/c['amplitude_v']) if c['amplitude_v'] else None,q_gain_from_source=float(abs(zq)/c['amplitude_v']) if c['amplitude_v'] else None,q_over_i=float(abs(zq/zi)) if c["amplitude_v"] and abs(zi)>0 else None,q_relative_phase_deg=float(np.angle(zq/zi,deg=True)) if c["amplitude_v"] and abs(zi)>0 else None,i_residual_rms_v=ri,q_residual_rms_v=rq))
  out['cases'].append(dict(name=c['name'],fits=results))
 out.update(completed=True,status='terminal_analysis')
if LNA:out['limitations'][1]='Actual prebiased LNA, seeded ring and I/Q mixers; ideal input source/passive bias and supplies, no filter/ADC or PLL qualification.'
if FILTER:out['limitations'][1]='Actual prebiased LNA, seeded ring, I/Q mixers and two filters; ideal supplies/bias/passives, no ADC or PLL qualification.'
(P/('evidence/bb-connected-level10-conversion.json' if LEVEL10 else 'evidence/bb-connected-bypass-conversion.json' if BYPASS else 'evidence/bb-connected-settling-conversion.json' if SETTLING else 'evidence/bb-connected-conversion.json' if FILTER else 'evidence/quadrature-interface-half-conversion.json' if HALF else 'evidence/quadrature-lna-ac-conversion.json' if ACCOUPLED else 'evidence/quadrature-lna-final-conversion.json' if FINAL else 'evidence/quadrature-lna-conversion.json' if LNA else 'evidence/quadrature-conversion.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
for c in out['cases']:
 print(c['name'],c['fits'][0],c['fits'][-1])
