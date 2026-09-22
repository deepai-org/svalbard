#!/usr/bin/env python3
"""Localize actual register/driver delays and measure update supply cost."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-dac-segmented-registered';B=R/'scratch/transceiver-dac-segmented-dynamic'
dual='--dual' in sys.argv
isolated='--isolated' in sys.argv or dual
variant='dual' if dual else 'isolated'
if isolated:W=R/f'scratch/transceiver-dac-segmented-{variant}'
complete=(W/'result.json').exists();r=json.loads((W/('result.json' if complete else 'progress.json')).read_text());m=json.loads((W/'manifest.json').read_text());bm=json.loads((B/'manifest.json').read_text())
if complete:assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
vectors=bm['vectors']+((m['baseline_manifest']['extra_vectors']+m['extra_vectors']) if isolated else m['extra_vectors']);columns={v.lower():i+1 for i,v in enumerate(vectors)}
def col(v):return columns[v.lower()]
def crossing(t,v,up):
 i=np.flatnonzero(((v[:-1]<1.65)&(v[1:]>=1.65)) if up else ((v[:-1]>1.65)&(v[1:]<=1.65)))
 assert len(i)==1
 j=i[0];return float(t[j]+(1.65-v[j])*(t[j+1]-t[j])/(v[j+1]-v[j]))
rows=[]
for c in r['cases']:
 if c['returncode']!=0 or c.get('timed_out',False):continue
 name=c['name'];wave=W/(name+'.dat');assert hashlib.sha256(wave.read_bytes()).hexdigest()==c['artifacts_sha256']['.dat']
 with wave.open() as f:assert f.readline().lower().split()==['time']+[v.lower() for v in vectors]
 a=np.loadtxt(wave,skiprows=1);t=a[:,0];events=[]
 for command,reverse in ((30,False),(55,True)):
  mask=(t>(command+.8)*1e-9)&(t<(command+4)*1e-9);w=a[mask];tw=w[:,0];clock=crossing(tw,w[:,col('v(XD.CK)')],True);cells=[]
  for label in ['L0','L1','L2','L3','H8']:
   up=(label=='H8')!=reverse
   reg=crossing(tw,w[:,col(f'v(XD.R{label})')],up)
   gate=crossing(tw,w[:,col(f'v(XD.{label})')],up)
   comp=crossing(tw,w[:,col(f'v(XD.{label}B)')],not up)
   cells.append(dict(cell=label,register_clock_to_q_ps=(reg-clock)*1e12,true_gate_after_clock_ps=(gate-clock)*1e12,complement_gate_after_clock_ps=(comp-clock)*1e12,register_to_true_gate_delay_ps=(gate-reg)*1e12,complement_minus_true_ps=(comp-gate)*1e12))
  if dual:
   for cell in cells:
    label=cell['cell'];qb=f'R{label[0]}B{label[1:]}'
    up=(label=='H8')!=reverse
    qbtime=crossing(tw,w[:,col(f'v(XD.{qb})')],not up)
    cell['complement_register_after_clock_ps']=(qbtime-clock)*1e12
    cell['qb_minus_q_ps']=cell['complement_register_after_clock_ps']-cell['register_clock_to_q_ps']
  events.append(dict(command_ns=command,cells=cells,register_crossing_spread_ps=max(c['register_clock_to_q_ps'] for c in cells)-min(c['register_clock_to_q_ps'] for c in cells),true_gate_crossing_spread_ps=max(c['true_gate_after_clock_ps'] for c in cells)-min(c['true_gate_after_clock_ps'] for c in cells)))
 supplies=[]
 for lo,hi in ((0,10),(20,25),(29,40),(54,65)):
  mask=(t>=lo*1e-9)&(t<=hi*1e-9);tw=t[mask];current=-a[mask,col('i(VDRV)')];external=-a[mask,col('i(VCLK)')]
  supplies.append(dict(window_ns=[lo,hi],logic_peak_ma=float(current.max()*1e3),logic_average_ma=float(np.trapezoid(current,tw)/(tw[-1]-tw[0])*1e3),logic_energy_pj=float(3.3*np.trapezoid(current,tw)*1e12),external_clock_peak_ma=float(external.max()*1e3)))
 rows.append(dict(name=name,events=events,supply_windows=supplies))
out=dict(status='registered_DAC_timing_and_supply_diagnostic',cases=rows,matrix_complete=complete,limitations=['Only five intentionally changing cells measured at mid-supply; crossings do not establish transistor current partition.', 'Spread combines polarity, device loading and path delay; no mismatch/process variation included.', 'Supply-window energy includes all logic activity in that interval, without idle subtraction; ideal supplies.', 'Nominal recorded cases only; no numerical convergence or setup/hold boundary qualification.'])
(P/(f'evidence/dac-{variant}-timing.json' if isolated else 'evidence/dac-registered-timing.json')).write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(rows[0],indent=2))
