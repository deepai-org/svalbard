"""Qualify observation-only reference device vectors before interpreting them."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-sar-reference-devices-prepared';W=R/'scratch/transceiver-sar-reference-devices';D=R/'scratch/transceiver-adc-sar8-reference-reservoir'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p):
 with p.open() as f:h=f.readline().lower().split()
 a=np.loadtxt(p,skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
 return h,a
m=json.loads((B/'manifest.json').read_text());assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
for ext in ('.spice','.dat'):assert sha(D/('typical_first1'+ext))==m['donor_artifacts_sha256'][ext]
extra=' '+' '.join(m['probes']);s=(B/'baseline.spice').read_text().replace('save all'+extra+'\n','');lines=s.splitlines()
for l in lines:
 if l.startswith('wrdata '):assert l.endswith(extra)
s='\n'.join(l[:-len(extra)] if l.startswith('wrdata ') else l for l in lines)+'\n'
assert s.replace('/work/baseline.dat','/work/typical_first1.dat')==(D/'typical_first1.spice').read_text()
out=dict(completed=False,status='pending',reproduction_pass=False,preparation_sha256=sha(B/'manifest.json'),limits=m['reproduction'],limitations=m['limitations'])
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after']
 assert sha(W/'baseline.spice')==sha(B/'baseline.spice')
 for ext,d in r['artifacts_sha256'].items():assert sha(W/('baseline'+ext))==d
 errors=[l for l in (W/'baseline.log').read_text().splitlines() if any(x in l.lower() for x in ('error','warning','aborted','timestep too small'))]
 out.update(status='terminal',returncode=r['returncode'],timed_out=r['timed_out'],errors=errors)
 if r['returncode']==0 and not r['timed_out'] and not errors:
  h,a=read(W/'baseline.dat');hb,b=read(D/'typical_first1.dat');t=a[:,0];tb=b[:,0];assert t[-1]>=209.9e-9-1e-20
  assert h[:len(hb)]==hb and h[len(hb):]==[p.lower() for p in m['probes']]
  grid=np.unique(np.r_[70e-9,209e-9,t[(t>70e-9)&(t<209e-9)],tb[(tb>70e-9)&(tb<209e-9)]])
  delta={n:float(np.max(abs(np.interp(grid,t,a[:,h.index(f'v({n})')])-np.interp(grid,tb,b[:,hb.index(f'v({n})')])))) for n in m['reproduction']['analog_nodes']}
  decisions=[]
  for ns in [hold+2.4+5*j for hold in (70,120,170) for j in range(8)]:
   q=float(np.interp(ns*1e-9,t,a[:,h.index('v(qp)')]-a[:,h.index('v(qn)')]));qb=float(np.interp(ns*1e-9,tb,b[:,hb.index('v(qp)')]-b[:,hb.index('v(qn)')]))
   decisions.append(dict(time_ns=ns,match=bool(abs(q)>2.97 and abs(qb)>2.97 and np.sign(q)==np.sign(qb))))
  ranges={p:float(np.ptp(a[:,h.index(p.lower())])) for p in m['probes']}
  dynamic=all(v>0 for v in ranges.values())
  out.update(completed=True,result_sha256=sha(W/'result.json'),waveform_sha256=sha(W/'baseline.dat'),analog_errors_v=delta,decisions=decisions,probe_peak_to_peak=ranges,all_probes_vary=dynamic,reproduction_pass=bool(max(delta.values())<=m['reproduction']['max_error_v'] and all(x['match'] for x in decisions) and dynamic))
(P/'evidence/sar-reference-devices.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'],out['reproduction_pass'])
