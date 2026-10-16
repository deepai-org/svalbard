"""Retained-network pulse response; no ESD rating or core-survival claim."""
import argparse
from pathlib import Path
from collections import Counter
import sys,os,json,hashlib
import numpy as np
p=Path(__file__).resolve().parent
from screen import control,run_spice
from loading_audit import anchor_floating_conductors
parser=argparse.ArgumentParser()
parser.add_argument('--fixture',type=Path,required=True)
parser.add_argument('--physical',type=Path,required=True)
parser.add_argument('--output-dir',type=Path,required=True)
args=parser.parse_args()
fixture=args.fixture.resolve();physical=args.physical.resolve();text=fixture.read_text()
model=physical.read_text();anchors=[]
if model not in text:
    model,anchors=anchor_floating_conductors(model,1e12)
    if model not in text:raise ValueError('Pulse fixture differs from declared physical model and numerical anchors')
counts=Counter()
for line in physical.read_text().splitlines():
 t=line.split()
 if len(t)>5 and t[0].startswith('X') and t[5]=='nfet_06v0' and {t[1],t[3]}=={'ESD_RAIL','VSS'}:counts[t[2]]+=1
gate,count=counts.most_common(1)[0];assert count>=40
work=args.output_dir.resolve();work.mkdir(exist_ok=False);(work/'.spiceinit').write_text('set ngbehavior=hs\n');os.chdir(work)
# Routed fixtures expose separate bond/core nodes and a finite local return.
# Observe those nodes explicitly; bond-pad voltage alone can hide core stress.
routed='RRETURN LOCAL_PAD_RETURN VSS ' in physical.read_text()
labels=['pad_p_v','pad_n_v','protection_rail_v','clamp_gate_v','supply_current_a','return_current_a']
vectors=f'v(PAD_P) v(PAD_N) v(xpad.ESD_RAIL) v(xpad.xphysical.{gate}) i(VDD) i(VSS)'
if routed:
    labels += ['core_p_v','core_n_v','local_return_v','core_p_to_local_return_v','rail_to_local_return_v']
    vectors += ' v(COREPAD_P) v(COREPAD_N) v(xpad.LOCAL_PAD_RETURN) v(COREPAD_P,xpad.LOCAL_PAD_RETURN) v(xpad.ESD_RAIL,xpad.LOCAL_PAD_RETURN)'
results={}
for name,current in [('baseline',0.),('positive_10mA',.01),('positive_100mA',.1),('negative_100mA',-.1)]:
 deck=text.split('.control')[0]+f'IINJECT VSS PAD_P PULSE(0 {current} 34n .1n .1n 2n 1u)\n'
 deck+=control(work,name,'tran 2p 80n',vectors)
 a=run_spice(work,name,deck,reject_transient_op=True);assert a[-1,0]>=79.99e-9 and np.isfinite(a).all()
 windows={}
 for state,start,end in [('before',32,33.9),('pulse',34,36.2),('after',36.2,39),('recovered',70,79)]:
  v=a[(a[:,0]>=start*1e-9)&(a[:,0]<=end*1e-9)];assert len(v)>1
  windows[state]={label:dict(min=float(v[:,i].min()),max=float(v[:,i].max())) for i,label in enumerate(labels,1)}
 results[name]=dict(injected_current_a=current,transient_complete=True,windows=windows,deck_sha256=hashlib.sha256(deck.encode()).hexdigest())
report=dict(numerical_floating_conductor_anchors=anchors,operating_point_policy='Transient operating-point fallback rejected; anchors are numerical only.',status='retained_network_current_pulse_probe_not_ESD_rating',cases=results,routed_core_observed=routed,clamp_gate_node=gate,parallel_clamp_devices=count,limitations=['Behavioral driver boundary lacks transistor-level reverse junctions.','No package inductance on supply/return; no thermal, current-density or avalanche qualification.','Finite 2ns injected pulse is not a standardized ESD waveform.','No steady-state or pulse survival inferred from transient completion.'],source_sha256={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [fixture,physical,p/'screen.py',p/'loading_audit.py',Path(__file__).resolve()]})
(work/'pulse-screen.json').write_text(json.dumps(report,indent=2)+'\n')
