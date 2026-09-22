"""Explicit rail-node incidence audit for the qualified reference buffer sources."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parents[1];R=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
result=R/'scratch/transceiver-sar-balance-second-instrumented/result.json'
r=json.loads(result.read_text())
assert r['returncode']==0 and not r['timed_out'] and r['sources_before']==r['sources_after']
rows=[]
for name in ('buffer_scaled.spice','buffer_complement.spice'):
 p=P/'analog/reference'/name
 assert sha(p)==r['sources_before']['/screen/reference/'+name]
 connections=[]
 for line in p.read_text().splitlines():
  words=line.split()
  if not words or words[0].startswith(('*','.')):continue
  if words[0].startswith('X'):
   assert words[5] in ('nfet_03v3','pfet_03v3')
   for terminal,node in zip(('drain','gate','source','body'),words[1:5]):
    if node=='OUT':connections.append(dict(instance=words[0],terminal=terminal,device=words[5]))
  elif words[0][0] in ('R','C'):
   for terminal,node in zip(('positive','negative'),words[1:3]):
    if node=='OUT':connections.append(dict(instance=words[0],terminal=terminal,device=words[0][0]))
  else:raise AssertionError('Unrecognized primitive: '+line)
 assert {(x['instance'],x['terminal']) for x in connections}=={
     ('XIP','gate'),('XOUT','drain'),('XLOAD','drain'),('CC','negative')}
 rows.append(dict(source=name,sha256=sha(p),connections=connections,
     accounted=['XOUT/XLOAD channel conduction with selected-DC probe sign convention',
                'CC branch via current in series RC; internal Z has only RC and CC'],
     not_explicitly_accounted=['XIP feedback gate terminal current/charge',
                             'XOUT and XLOAD drain displacement and junction terms beyond reported channel current']))
out=dict(status='topology_audited',buffers=rows,result_sha256=sha(result),
    analyzer_sha256=sha(Path(__file__)),
    conclusion='The omitted dynamic load includes the input feedback gate, not only output device drains.',
    limitations=['Incidence identifies possible current paths, not their magnitudes or unique cause of the residual.',
                'External reservoir and CDAC branches are accounted separately in reference-refined-balance.json.',
                'PDK MOS wrappers can contain additional internal parasitics; full terminal current is needed for closure.'])
(P/'evidence/reference-rail-connections.json').write_text(json.dumps(out,indent=2)+'\n')
print(out['conclusion'])
