#!/usr/bin/env python3
"""Compare terminal failure timing against retained ideal reference events."""
import hashlib,json,re
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def unit(x):
 m=re.fullmatch(r'([0-9.]+)([np]?)',x)
 assert m
 return float(m[1])*{'':1,'n':1e-9,'p':1e-12}[m[2]]
for case in ('buffered','follower'):
 e=P/f'evidence/closed-loop-{case}-screen.json';d=json.loads(e.read_text())
 assert d['status']=='failed_full_loop_partial_waveform'
 w=R/f'scratch/transceiver-closed-loop-{case}'
 for ext,h in d['run_record']['artifacts_sha256'].items():assert sha(w/('closed'+ext))==h
 deck=(w/'closed.spice').read_text()
 line=next(x for x in deck.splitlines() if x.startswith('VREF '))
 m=re.search(r'PULSE\(([^)]+)\)',line);v=list(map(unit,m[1].split()));assert len(v)==7
 _,_,delay,rise,fall,width,period=v;t=d['failure_time_ns']*1e-9
 events=[]
 for k in range(max(0,int((t-delay)/period)-1),int((t-delay)/period)+2):
  for label,offset in [('rise_start',0),('rise_end',rise),('fall_start',rise+width),('fall_end',rise+width+fall)]:
   event=delay+k*period+offset
   events.append(dict(kind=label,cycle=k,time_ns=event*1e9,failure_minus_event_ps=(t-event)*1e12))
 nearest=min(events,key=lambda x:abs(x['failure_minus_event_ps']))
 rows.append(dict(case=case,evidence_sha256=sha(e),deck_sha256=sha(w/'closed.spice'),source=line,failure_time_ns=d['failure_time_ns'],nearest_event=nearest,late_phase=d['late_phase_diagnostic']))
out=dict(status='verified_terminal_failure_event_comparison',cases=rows,limitations=['Coincidence with an ideal-source breakpoint is not proof of the solver failure mechanism.','Changed pump topology did not eliminate this failure; this does not establish physical impossibility.','Partial trajectories and deterministic phase residuals do not qualify lock or phase noise.'])
(P/'evidence/loop-failure-event.json').write_text(json.dumps(out,indent=2)+'\n')
for r in rows:print(r['case'],r['nearest_event'])
