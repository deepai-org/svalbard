#!/usr/bin/env python3
"""Reject receiver scoring without bias and loaded-clock activity evidence."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'scratch/transceiver-rf-candidate-bias'
a=np.loadtxt(W/'transient.dat',skiprows=1);assert a.shape[1]==11 and np.isfinite(a).all() and a[-1,0]>80e-9
w=a[a[:,0]>=40e-9];t=w[:,0]
mean=lambda c:float(np.trapezoid(w[:,c],t)/(t[-1]-t[0]))
def edges(c,level):
 v=w[:,c];i=np.where((v[:-1]<level)&(v[1:]>=level))[0]
 return t[i]+(t[i+1]-t[i])*(level-v[i])/(v[i+1]-v[i])
e=edges(6,0);lo=edges(4,1.65);lob=edges(5,1.65)
checks=dict(gate_bias_in_diagnostic_range=bool(w[:,1].min()>1.4 and w[:,1].max()<1.6),source_mean_in_diagnostic_range=.15<mean(2)<.5,clock_activity=len(e)>80 and len(lo)>80 and len(lob)>80)
r=dict(status='hierarchical_prebiased_schematic_boundary_check_not_receiver_qualification',checks=checks,all_checks_pass=all(checks.values()),gate_range_v=[float(w[:,1].min()),float(w[:,1].max())],source_mean_v=mean(2),drain_mean_v=mean(3),lo_range_v=[float(w[:,4].min()),float(w[:,4].max())],frequency_hz=float((len(e)-1)/(e[-1]-e[0])) if len(e)>1 else None,rf_current_a=-mean(9),pll_current_a=-mean(10),artifacts_sha256={name:hashlib.sha256((W/name).read_bytes()).hexdigest() for name in ('transient.dat','op.log')},source_sha256={name:hashlib.sha256((ROOT/'projects/programmable_transceiver_platform/analog'/name).read_bytes()).hexdigest() for name in ('rf_rx_candidate.spice','rf_candidate_bias_tb.spice')},limitations=['Explicit gate precharge and oscillator seed: not cold-start or acquisition.', 'Ideal external bias and sampling clocks; no PLL, quadrature or ADC.', 'Bias thresholds are diagnostic guardrails, not qualified design specifications.', 'Short nominal schematic run does not establish gain, noise, mismatch, extraction or package performance.'])
(ROOT/'projects/programmable_transceiver_platform/evidence/rf-candidate-bias-screen.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
assert all(checks.values()),'Boundary check failed; do not score useful receiver performance'
