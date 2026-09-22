"""Full-sequence diagnostic; completion is not converter qualification."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--rzero',action='store_true');ap.add_argument('--divider',action='store_true');ap.add_argument('--clamped',action='store_true');ap.add_argument('--sampler-double',action='store_true');args=ap.parse_args();assert sum((args.rzero,args.divider,args.clamped,args.sampler_double))<=1
name='sar-sampler-double' if args.sampler_double else 'sar-reference-clamped' if args.clamped else 'sar-reference-divider' if args.divider else 'sar-reference-rzero' if args.rzero else 'sar-reservoir-full'
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-'+name);B=R/('scratch/transceiver-'+name+'-prepared')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p):
 with p.open() as f:h=f.readline().lower().split()
 a=np.loadtxt(p,skiprows=1);assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
 return h,a
def measure(h,a):
 t=a[:,0]
 def at(n,ns):return float(np.interp(ns*1e-9,t,a[:,h.index('v('+n+')')]))
 frames=[]
 for hold in (70,120,170):
  steps=[]
  for j in range(8):
   clock=hold+.5+5*j;decision=hold+2.4+5*j;res=at('hp',clock)-at('hn',clock);q=at('qp',decision)-at('qn',decision)
   steps.append(dict(bit=7-j,clock_ns=clock,preclock_residue_v=res,preclock_span_v=at('vh',clock)-at('vl',clock),comparator_v=q,full_swing=bool(abs(q)>2.97),polarity_agrees=bool(np.sign(q)==np.sign(res))))
  final=hold+39;bits=[at('d'+str(k),final) for k in range(8)]
  mask=(t>=hold*1e-9)&(t<=(hold+39)*1e-9)
  span=a[:,h.index('v(vh)')]-a[:,h.index('v(vl)')]
  target=.4 if hold in (70,170) else -.4
  acquisition=[dict(offset_ns=offset,driver_error_v=at('ip',hold+offset)-at('in',hold+offset)-target,held_error_v=at('hp',hold+offset)-at('hn',hold+offset)-target) for offset in (0,.1,.5)]
  frames.append(dict(acquisition=acquisition,max_span_error_v=float(np.max(abs(span[mask]-1))),hold_ns=hold,final_code=sum((v>1.65)*2**k for k,v in enumerate(bits)),final_bits_valid=all(v<.33 or v>2.97 for v in bits),steps=steps))
 return frames
m=json.loads((B/'manifest.json').read_text());assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
out=dict(completed=False,status='pending',adopted=False,preparation_sha256=sha(B/'manifest.json'),limitations=m['limitations']+['Comparator polarity agreement with pre-clock residue is diagnostic, not ideal transfer accuracy.'])
donor=R/'scratch/transceiver-adc-sar8-reference-reservoir'
for ext in ('.spice','.dat'):assert sha(donor/('typical_first1'+ext))==m['donor_artifacts_sha256'][ext]
if args.sampler_double:
 extra='XS_EXTRA IP IN HP HN SC SCB VDD 0 wifi_if_transmission_gate\n'
 assert (B/'baseline.spice').read_text().replace(extra,'')==(R/'scratch/transceiver-sar-reference-clamped-prepared/baseline.spice').read_text()
elif args.clamped:
 extra='VCLH VH 0 2.15\nVCLL VL 0 1.15\n'
 assert (B/'baseline.spice').read_text().replace(extra,'').replace('/work/baseline.dat','/work/typical_first1.dat')==(donor/'typical_first1.spice').read_text()
elif args.divider:
 pair=(P/'analog/reference/adc_reference_pair.spice').read_text();cell=(P/'analog/reference/buffer_complement.spice').read_text()
 addition='RFIN IN INLOW 10k\nRFIG INLOW VSS 30k\nRFFB OUT FBLOW 10k\nRFFG FBLOW VSS 30k\n'
 changed=cell.replace('XIP A OUT T','XIP A FBLOW T').replace('XIN X IN T','XIN X INLOW T').replace('XIP A FBLOW T',addition+'XIP A FBLOW T')
 expanded=pair.replace('.include /screen/reference/buffer_complement.spice',changed.rstrip())
 assert (B/'baseline.spice').read_text().replace(expanded.rstrip(),'.include /screen/reference/adc_reference_pair.spice').replace('/work/baseline.dat','/work/typical_first1.dat')==(donor/'typical_first1.spice').read_text()
elif args.rzero:
 pair=(P/'analog/reference/adc_reference_pair.spice').read_text();changed=pair
 for kind in ('scaled','complement'):
  cell=P/'analog/reference'/f'buffer_{kind}.spice';tuned=P/'analog/reference'/f'buffer_{kind}_tune.spice'
  assert tuned.read_text().replace(f'pt_reference_buffer_{kind}_tune',f'pt_reference_buffer_{kind}').replace(' S=1 RZ=100',' S=1').replace('{RZ/S}','{100/S}')==cell.read_text()
  changed=changed.replace(f'buffer_{kind}.spice',f'buffer_{kind}_tune.spice').replace(f'pt_reference_buffer_{kind} S=4',f'pt_reference_buffer_{kind}_tune S=4 CC=1p RZ=2000')
 assert (B/'baseline.spice').read_text().replace(changed.rstrip(),'.include /screen/reference/adc_reference_pair.spice').replace('/work/baseline.dat','/work/typical_first1.dat')==(donor/'typical_first1.spice').read_text()
else:
 extra='XHR_EXTRA VH 0 pt_ref_reservoir_2048\nXLR_EXTRA VL 0 pt_ref_reservoir_2048\n'
 assert (B/'baseline.spice').read_text().replace(extra,'').replace('/work/baseline.dat','/work/typical_first1.dat')==(donor/'typical_first1.spice').read_text()
if args.sampler_double:
 clamp_e=P/'evidence/sar-reference-clamped.json';ce=json.loads(clamp_e.read_text());assert ce['completed'] and ce['clamps_verified'] and sha(clamp_e)==m['baseline_evidence_sha256']
 reference=R/'scratch/transceiver-sar-reference-clamped/baseline.dat';assert sha(reference)==ce['waveform_sha256']
else:reference=donor/'typical_first1.dat'
hd,ad=read(reference);out['baseline_frames']=measure(hd,ad)
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after']
 for ext,d in r['artifacts_sha256'].items():assert sha(W/('baseline'+ext))==d
 assert sha(W/'baseline.spice')==sha(B/'baseline.spice')
 errors=[l for l in (W/'baseline.log').read_text().splitlines() if any(k in l.lower() for k in ('error','warning','aborted','timestep too small'))]
 out.update(status='terminal',returncode=r['returncode'],timed_out=r['timed_out'],errors=errors)
 if r['returncode']==0 and not r['timed_out'] and not errors:
  h,a=read(W/'baseline.dat');t=a[:,0];assert t[-1]>=209.9e-9-1e-20
  if not (args.rzero or args.divider or args.clamped or args.sampler_double):
   short=R/'scratch/transceiver-sar-reservoir-double';sr=json.loads((short/'result.json').read_text());assert sha(short/'baseline.dat')==sr['artifacts_sha256']['.dat']
   hs,b=read(short/'baseline.dat');assert hs==h
   grid=np.unique(np.r_[t[(t>=70e-9)&(t<=79e-9)],b[(b[:,0]>=70e-9)&(b[:,0]<=79e-9),0],70e-9,79e-9])
   delta={n:float(np.max(abs(np.interp(grid,t,a[:,h.index(n)])-np.interp(grid,b[:,0],b[:,h.index(n)])))) for n in ['v(hp)','v(hn)','v(vh)','v(vl)']}
   out.update(short_reproduction_errors_v=delta,short_reproduction_pass=max(delta.values())<=10e-6)
  if args.clamped or args.sampler_double:
   rail_errors={n:float(np.max(abs(a[:,h.index(f'v({n})')]-target))) for n,target in [('vh',2.15),('vl',1.15)]}
   out.update(clamp_errors_v=rail_errors,clamps_verified=max(rail_errors.values())<=1e-9)
   assert out['clamps_verified']
  frames=measure(h,a)
  out['code_changes']=[c['final_code']-b['final_code'] for b,c in zip(out['baseline_frames'],frames)]
  out.update(completed=True,result_sha256=sha(W/'result.json'),waveform_sha256=sha(W/'baseline.dat'),frames=frames)
(P/'evidence'/(name+'.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
