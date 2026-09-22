"""Require exact old vectors before using output-only shared-bias observations."""
import contextlib,io,json,runpy
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;P=HERE.parent;R=P.parents[1]
with contextlib.redirect_stdout(io.StringIO()):
    shared=runpy.run_path(str(HERE/'check_sar_balance_refinement.py'))
sha=shared['sha'];load=shared['load']
B=R/'scratch/transceiver-reference-bias-observation-prepared'
PB=R/'scratch/transceiver-reference-terminal-probe-prepared'
W=R/'scratch/transceiver-reference-bias-observation'
PW=R/'scratch/transceiver-reference-terminal-probe'
m=json.loads((B/'manifest.json').read_text())
assert sha(PB/'manifest.json')==m['parent_preparation_sha256']
assert sha(PW/'result.json')==m['parent_result_sha256']
e=P/'evidence/reference-terminal-probe.json'
assert sha(e)==m['parent_reproduction_sha256'] and json.loads(e.read_text())['reproduction_pass']
for name,h in m['artifacts_sha256'].items():
 assert sha(B/name)==h
 if name!='baseline.spice':assert sha(B/name)==sha(PB/name)
s=(B/'baseline.spice').read_text();extra=' '+' '.join(m['appended_output_vectors'])
line=next(l for l in s.splitlines() if l.startswith('wrdata '))
assert line.endswith(extra)
assert s.replace(line,line[:-len(extra)])==(PB/'baseline.spice').read_text()
if not (W/'result.json').exists():
 print('Exact output-only scope/source checks pass; terminal result pending.')
else:
 original=load('reference-terminal-probe');observed=load('reference-bias-observation')
 assert sha(PW/'baseline.dat')==m['parent_waveform_sha256']
 assert sha(W/'baseline.spice')==sha(B/'baseline.spice')
 assert original[2]['sources_before']==observed[2]['sources_before']
 h,a,_=original;k,b,_=observed
 assert len(k)==len(h)+2 and k[-2:]==['v(rbn)','v(rbp)']
 exact=bool(a.shape==b[:,:len(h)].shape and h==k[:len(h)] and np.array_equal(a,b[:,:len(h)]))
 report=dict(completed=True,reproduction_pass=exact,original_vectors_exact=exact,
   waveform_sha256=sha(W/'baseline.dat'),parent_waveform_sha256=sha(PW/'baseline.dat'),
   preparation_sha256=sha(B/'manifest.json'),checker_sha256=sha(Path(__file__)),
   loader_sha256=sha(HERE/'check_sar_balance_refinement.py'),
   limitations=['Observation of one stimulus; common bias motion alone does not identify causal cross-rail transfer.',
                'Measured endpoint motion is not an autonomous bias-state model.'])
 if exact:
  time=b[:,0];grid=np.r_[70e-9,time[(time>70e-9)&(time<209e-9)],209e-9]
  biases={}
  for node in ('rbn','rbp'):
   values=b[:,k.index('v('+node+')')];window=np.interp(grid,time,values)
   rows=[]
   for hold in (70,120,170):
    for j in range(8):
     for kind,left,right in [('preclock',.3,.5),('switching',2.5,3.6)]:
      lo,hi=(hold+5*j+np.array([left,right]))*1e-9
      start,end=np.interp([lo,hi],time,values)
      rows.append(dict(hold_ns=hold,bit=7-j,window=kind,start_v=float(start),end_v=float(end),delta_v=float(end-start)))
   biases[node]=dict(minimum_v=float(min(window)),maximum_v=float(max(window)),peak_to_peak_v=float(np.ptp(window)),windows=rows)
  report['biases']=biases
 (P/'evidence/reference-bias-observation.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
 print('Exact reproduction:',exact)
 if exact:
  for node,values in report['biases'].items():print(node,{k:v for k,v in values.items() if k!='windows'})
