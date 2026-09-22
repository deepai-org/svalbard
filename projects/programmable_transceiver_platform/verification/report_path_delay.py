"""Separate reported cell arcs from inter-instance net arcs; validate sums."""
import hashlib,json,re,sys
from pathlib import Path
root=Path(sys.argv[1]);project=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-path-delay'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
repair=root/'scratch/transceiver-placement-repair'
evidence=json.loads((project/'evidence/placement-repair-screen.json').read_text())
for name in ['repaired.odb','repaired.v']:assert sha(repair/name)==evidence['artifact_sha256'][name]
v=(repair/'repaired.v').read_text()
def alias(inst):
 m=re.search(r'\s'+re.escape(inst)+r'\s*\((.*?)\);',v,re.S)
 q=re.search(r'\.Q\s*\((.*?)\)',m[1]) if m else None
 return q[1].strip() if q else 'unresolved'
cases=[]
for rc in [0,1]:
 t=(out/f'rc{rc}.log').read_text();assert 'CONSTRAINT_AUDIT_END' in t and '[ERROR' not in t
 paths=[]
 for domain,body in re.findall(r'DOMAIN_BEGIN (\w+)\n(.*?)DOMAIN_END \1',t,re.S):
  seen=set()
  for b in body.split('Startpoint:')[1:]:
   group=re.search(r'Path Group: (\S+)',b)[1]
   if group in seen:continue
   seen.add(group)
   start=b.split()[0];end=re.search(r'Endpoint: (\S+)',b)[1]
   before=b.split('data arrival time')[0]
   rows=re.findall(r'^\s*(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+[\^v] (\S+)/(\S+) \(([^)]+)\)',before,re.M)
   assert rows and rows[0][3]=='CLK'
   arcs=[];previous=rows[0][2]
   for delay,time,inst,pin,cell in rows[1:]:
    arcs.append({'kind':'cell' if inst==previous else 'net','delay_ns':float(delay),'instance':inst,'pin':pin,'cell':cell})
    previous=inst
   arrival=float(re.search(r'(-?\d+\.\d+)\s+data arrival time',b)[1])
   assert abs(sum(x['delay_ns'] for x in arcs)-arrival)<0.0001
   paths.append({'domain':domain,'group':group,'start_Q':alias(start),'end_Q':alias(end),'arrival_ns':arrival,
    'slack_ns':float(re.search(r'(-?\d+\.\d+)\s+slack \(',b)[1]),
    'cell_arc_ns':sum(x['delay_ns'] for x in arcs if x['kind']=='cell'),
    'net_arc_ns':sum(x['delay_ns'] for x in arcs if x['kind']=='net'),
    'cell_arc_count_including_launch':sum(x['kind']=='cell' for x in arcs),'arcs':arcs})
  assert seen
 assert len({p['domain'] for p in paths})==8
 cases.append({'estimated_signal_rc':bool(rc),'paths':paths,'log_sha256':sha(out/f'rc{rc}.log')})
r={'scope':'Worst reported path per domain/group, nominal ideal-clock repaired experimental placement',
 'cases':cases,'input_database_sha256':sha(repair/'repaired.odb'),
 'interpretation':'Cell delay includes load capacitance and incoming slew effects. Small explicit net delay does NOT mean interconnect has negligible impact. Different RC cases may select different paths.',
 'limitations':['No extracted routing, qualified RC bounds, CTS or external interface closure.','Repaired netlist remains experimental pending equivalence and independent geometry checks.'],
 'source_sha256':{f:sha(project/'verification'/f) for f in ['path_delay_screen.tcl','report_path_delay.py','run_path_delay.sh']}}
(project/'evidence/path-delay-screen.json').write_text(json.dumps(r,indent=2)+'\n')
for c in cases:
 for p in c['paths']:
  if p['domain']==p['group']:print(c['estimated_signal_rc'],p['domain'],p['start_Q'],p['end_Q'],p['cell_arc_count_including_launch'],round(p['cell_arc_ns'],4),round(p['net_arc_ns'],4))
