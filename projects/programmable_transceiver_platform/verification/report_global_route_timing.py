import hashlib,json,math,re,sys
from pathlib import Path
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-global-route-timing'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
route=json.loads((p/'evidence/pdn-routing-comparison.json').read_text())['cases'][1]
assert sha(out/'routes.guide')==route['guides_sha256']
assert sha(root/'scratch/transceiver-wide-pdn/digital-pdn.odb')==route['input_database_sha256']
repair=json.loads((p/'evidence/current-repair-screen.json').read_text())
v=root/'scratch/transceiver-current-repair/repaired.v';assert sha(v)==repair['artifact_sha256']['repaired.v'];verilog=v.read_text()
def alias(inst):
 m=re.search(r'\s'+re.escape(inst)+r'\s*\((.*?)\);',verilog,re.S)
 q=re.search(r'\.Q\s*\((.*?)\)',m[1]) if m else None
 return q[1].strip() if q else 'unresolved'
t=(out/'timing.log').read_text();assert 'CONSTRAINT_AUDIT_END' in t and '[ERROR' not in t
domains={};critical={}
for name,body in re.findall(r'DOMAIN_BEGIN (\w+)\n(.*?)DOMAIN_END \1',t,re.S):
 groups={}
 for b in body.split('Startpoint:')[1:]:
  g=re.search(r'Path Group: (\S+)',b);s=re.search(r'(-?\d+\.\d+)\s+slack \(',b)
  if g and s:
   groups.setdefault(g[1],[]).append(float(s[1]))
   if g[1]==name and name not in critical:critical[name]={'start_Q':alias(b.split()[0]),'end_Q':alias(re.search(r'Endpoint: (\S+)',b)[1])}
 assert groups;domains[name]={k:min(v) for k,v in groups.items()}
assert len(domains)==len(critical)==8
spef=(out/'estimated.spef').read_text();assert '*C_UNIT 1 PF' in spef and '*R_UNIT 1 OHM' in spef
counts={'nets':0,'resistors':0,'capacitors':0};state=None
for line in spef.splitlines():
 if line.startswith('*D_NET '):counts['nets']+=1
 if line in ['*CAP','*RES','*CONN','*END']:state=line
 elif line and not line.startswith('*') and state in ['*CAP','*RES']:
  value=float(line.split()[-1]);assert math.isfinite(value) and value>=0
  counts['capacitors' if state=='*CAP' else 'resistors']+=1
assert all(counts.values()) and counts['nets']==route['routed_nets']
r={'scope':'Global-route signal-RC estimate on wider-grid candidate with nominal cells and ideal clocks; no extracted signoff',
 'worst_slacks_ns':domains,'critical_register_outputs':critical,
 'electrical_violation_rows':t.split('ELECTRICAL_AUDIT_BEGIN')[1].split('ELECTRICAL_AUDIT_END')[0].count('(VIOLATED)'),
 'spef_component_counts':counts,'previous_placement_slacks_ns':repair['after']['worst_slacks_ns'],
 'input_database_sha256':route['input_database_sha256'],
 'artifact_sha256':{f:sha(out/f) for f in ['timing.log','routes.guide','estimated.spef']},
 'source_sha256':{f:sha(p/'verification'/f) for f in ['global_route_timing.tcl','run_global_route_timing.sh','report_global_route_timing.py']},
 'limitations':['Global-route RC estimates, not detailed routed geometry or coupling/corner extraction.','Nominal TT 25C 3.3V cells do not account for computed spatial supply loss.','Eight clocks defined after routing and kept ideal; no CTS, propagated skew/jitter or clock-current qualification.','External IO remains unconstrained; CDC/reset and protocol latency are not closed.','Zero global overflow or electrical violations does not imply setup/hold closure or full-chip signoff.']}
(p/'evidence/global-route-timing-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print('GLOBAL_ROUTE_TIMING_SCREEN',domains['host_tx_clk'],domains['host_rx_clk'],counts,critical['host_tx_clk'])
