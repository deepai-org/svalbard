#!/usr/bin/env python3
"""Signed UPDATE edge offsets around a replicated numerical failure."""
import hashlib,json,re
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-rx-adc-loading';O=R/'scratch/transceiver-rx-adc-event-offsets-prepared';O.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
failures=[]
for case in ('loaded','isolated'):
 root=B/case;r=json.loads((root/'result.json').read_text());assert r['returncode']==1 and not r['timed_out'] and r['sources_before']==r['sources_after']
 for ext,h in r['artifacts_sha256'].items():assert sha(root/('connected'+ext))==h
 m=re.search(r'Timestep too small; time = ([\deE.+-]+).*?trouble with node "([^"]+)"',(root/'connected.log').read_text());assert m
 failures.append(dict(case=case,time_s=float(m.group(1)),node=m.group(2),artifacts_sha256=r['artifacts_sha256']))
assert failures[0]['time_s']==failures[1]['time_s']
base=(B/'loaded/connected.spice').read_text();old=next(l for l in base.splitlines() if l.startswith('VUPDATE '));cases=[]
for name,offset in [('early',-.01),('late',.01)]:
 # Only one falling segment moves; pulse width changes by10ps, not the full clock phase.
 pair='478.5n 3.3 478.6n 0';assert old.count(pair)==1
 replacement=f'{478.5+offset:.2f}n 3.3 {478.6+offset:.2f}n 0'
 new=old.replace(pair,replacement);deck=base.replace(old,new)
 assert deck.replace(new,old)==base
 # Inspect actual pairs independently, not just string reversibility.
 def tokens(line):return re.search(r'PWL\(([^)]*)\)',line).group(1).split()
 before=tokens(old);after=tokens(new);indices=[i for i,(a,b) in enumerate(zip(before,after)) if a!=b];assert len(indices)==2 and all(i%2==0 for i in indices)
 assert all(abs(float(after[i][:-1])-float(before[i][:-1])-offset)<1e-10 for i in indices)
 p=O/(name+'.spice');p.write_text(deck);cases.append(dict(case=name,offset_ns=offset,deck_sha256=sha(p),original_line=old,changed_line=new))
out=dict(status='prepared_not_simulated',failure_comparison=failures,parent_deck_sha256=sha(B/'loaded/connected.spice'),cases=cases,limitations=['Both failures occur without requiring receiver back-loading, but do not prove a simulator-internal cause.','Moving an UPDATE edge changes physical timing; successful completion would establish sensitivity, not repair or full qualification.','No source/circuit removed; targets, loading, all other events,610ns horizon and solver retained.'])
(O/'manifest.json').write_text(json.dumps(out,indent=2)+'\n');(P/'evidence/rx-adc-event-offset-preparation.json').write_text(json.dumps(out,indent=2)+'\n');print([(x['case'],x['time_s'],x['node']) for x in failures])
