#!/usr/bin/env python3
"""Retain completion/failure evidence from active reduced PLL circuits."""
import hashlib,json,re
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-pfd-pump-breakpoint'
file=W/'result.json';complete=file.exists()
if not complete:file=W/'progress.json'
r=json.loads(file.read_text());rows=[]
for c in r['cases']:
 name=c['name']
 for ext,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+ext)).read_bytes()).hexdigest()==digest
 d=(W/(name+'.spice')).read_text();log=(W/(name+'.log')).read_text()
 for line in ('XPFD REF FB RN UP DN VDIV 0 pt_pfd','XCP UP DN PUMP BPCP BNCP VDIV 0 pt_charge_pump','VSENSE PUMP CTRL 0','XFILT CTRL 0 pt_loop_filter','tran 2p 3201n 0 2p uic'):assert line+'\n' in d
 source=R/'scratch'/('transceiver-closed-loop-gear' if c['kind']=='pulse' else 'transceiver-closed-loop-pwl-reference')/'closed.spice'
 assert next(x for x in source.read_text().splitlines() if x.startswith('VREF ')) in d
 assert f"VFB FB 0 PULSE(0 3.3 {100+c['feedback_skew_ns']}n 100p 100p 25.5n 51.2n)" in d
 c['completed_requested_horizon']=c['returncode']==0 and 'aborted' not in log and bool(re.search(r'final_control\s*=\s*[0-9.e+-]+',log,re.I))
 if c['completed_requested_horizon']:
  for key in ('final_control','min_control','max_control'):c[key+'_v']=float(re.search(key+r'\s*=\s*([0-9.e+-]+)',log,re.I).group(1))
 else:
  m=re.search(r'Timestep too small; time = ([0-9.e+-]+)',log);c['failure_time_ns']=float(m.group(1))*1e9 if m else None
 c['first_feedback_edge_interval_ns']=[100+c['feedback_skew_ns'],100.1+c['feedback_skew_ns']]
 c['reset_release_interval_ns']=[90,90.1]
 c['first_feedback_overlaps_reset_release']=c['feedback_skew_ns']==-10
 rows.append(c)
if complete:
 assert {(c['kind'],c['feedback_skew_ns']) for c in rows}=={(k,s) for k in ('pulse','pwl') for s in (-10,0,10)}
 for path,digest in r['source_sha256'].items():assert hashlib.sha256((P/'analog'/path.removeprefix('/screen/')).read_bytes()).hexdigest()==digest
out=dict(status='complete_reduced_active_diagnostic' if complete else 'partial_reduced_active_diagnostic',cases=rows,full_PLL_qualified=False,limitations=['Ideal feedback clocks replace divider/VCO, removing their loading and supply activity.', 'Completion only diagnoses numerical behavior; no closed-loop dynamics, lock, jitter, phase-noise or startup proof.', 'Fixed phase offsets, precharged filter, ideal bias currents and supplies; no physical uncertainty coverage.', 'The -10ns first feedback rising edge overlaps reset release. Its phase branch is not a clean lead/lag polarity test.'])
(P/'evidence/pfd-pump-breakpoint-screen.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps([dict(name=c['name'],completed=c['completed_requested_horizon'],failure_ns=c.get('failure_time_ns'),final_control_v=c.get('final_control_v')) for c in rows],indent=2))
