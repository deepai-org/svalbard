"""Compare the two-resistor RF candidate with its qualified recorded replay."""
import hashlib,json
from pathlib import Path
import numpy as np
from analyze_lo_common_mode_cycles import diagnostic,controls
from compare_lo_rf_cycles import nodes
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
controls()
B=R/'scratch/transceiver-lo-bias-restoration-prepared'
PB=R/'scratch/transceiver-lo-common-mode-recorded-prepared'
W=R/'scratch/transceiver-lo-bias-restoration'
PW=R/'scratch/transceiver-lo-common-mode-recorded'
m=json.loads((B/'manifest.json').read_text())
assert sha(PB/'manifest.json')==m['parent_preparation_sha256']
e=P/'evidence/lo-common-mode-reproduction.json'
assert sha(e)==m['reproduction_report_sha256']
assert json.loads(e.read_text())['reproduction_pass']
for name,h in m['artifacts_sha256'].items():assert sha(B/name)==h
s=(B/'replay.spice').read_text()
for old,new in m['changes'].items():
 assert s.count(new)==1;s=s.replace(new,old)
assert s==(PB/'replay.spice').read_text()
assert sha(B/'ring_pwl.spice')==sha(PB/'ring_pwl.spice')
if not (W/'result.json').exists():
 print('Exact two-resistor change and unchanged input checks pass; terminal result pending.')
else:
 results={};hashes={};provenance={}
 for name,work,prepared in [('recorded',PW,PB),('candidate',W,B)]:
  r=json.loads((work/'result.json').read_text())
  assert r['returncode']==0 and not r['timed_out'] and r['sources_before']==r['sources_after']
  for ext,h in r['artifacts_sha256'].items():assert sha(work/('replay'+ext))==h
  assert sha(work/'replay.spice')==sha(prepared/'replay.spice')
  with (work/'replay.dat').open() as f:header=f.readline().lower().split()
  data=np.loadtxt(work/'replay.dat',skiprows=1,usecols=[0]+[header.index(n) for n in nodes])
  assert np.isfinite(data).all() and np.all(np.diff(data[:,0])>0)
  assert abs(data[-1,0]-1001e-9)<1e-15
  window=data[data[:,0]>=799e-9]
  results[name]={node:diagnostic(window[:,0],window[:,i+1]) for i,node in enumerate(nodes)}
  hashes[name]=sha(work/'replay.dat');provenance[name]=r['sources_before']
 assert hashes['recorded']==m['parent_waveform_sha256']
 assert provenance['recorded']==provenance['candidate']
 report=dict(completed=True,results=results,waveform_hashes=hashes,
  preparation_sha256=sha(B/'manifest.json'),checker_sha256=sha(Path(__file__)),
  metric_source_hashes={name:sha(Path(__file__).with_name(name)) for name in ('analyze_lo_common_mode_cycles.py','compare_lo_rf_cycles.py')},
  physical_qualification=False,limitations=[
   'Recorded source fixes oscillator waveform despite changed receiver loading; autonomous validation is required.',
   'Diagnostic amplitude/duty metrics are not mixer EVM or phase-noise specifications.',
   'Lumped resistor values do not qualify physical resistor parasitics or variation.'])
 (P/'evidence/lo-bias-restoration.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
 for name,legs in results.items():
  for node,row in legs.items():print(name,node,{k:v for k,v in row.items() if k!='cycles'})
