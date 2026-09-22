import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';name='cm1.177_fb20000'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
gain=(P/'analog/bb_pmos_gain.spice').read_text();new=gain.replace('pt_bb_pmos_gain','pt_bb_pmos_gain_large_input')
for line in gain.splitlines():
 if line.startswith(('XIP ','XIN ')):new=new.replace(line,line.replace('w=4u l=0.28u','w=8u l=0.56u'))
cell=(P/'analog/bb_filter_section.spice').read_text().replace('XA GP GN MP MN T1 BIAS VDD pt_bb_pmos_gain','XA GP GN MP MN T1 BIAS VDD pt_bb_pmos_gain_large_input')
rows=[];decks=[];grids=[]
for label,folder in [('baseline','transceiver-bb-feedback-gain'),('candidate','transceiver-bb-large-input-gain')]:
 w=R/'scratch'/folder;r=json.loads((w/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after'];c=next(x for x in r['cases'] if x['name']==name);assert c['returncode']==0
 for ext,h in c['artifacts_sha256'].items():assert sha(w/(name+ext))==h
 log=(w/(name+'.log')).read_text().lower();assert not any(x in log for x in ('warning','error','aborted'))
 decks.append((w/(name+'.spice')).read_text())
 a=np.loadtxt(w/(name+'.dat'),skiprows=1);assert a.shape==(100,5) and np.isfinite(a).all();grids.append(a[:,0]);g=abs(a[:,1]+1j*a[:,2]);inp=abs(a[:,3]+1j*a[:,4])
 with (w/(name+'-op.dat')).open() as f:h=f.readline().lower().split()
 op=np.loadtxt(w/(name+'-op.dat'),skiprows=1);assert len(h)==len(op) and np.isfinite(op).all();v=dict(zip(h,op))
 margins={}
 for stage in ('xa','xb'):
  for dev in ('xip','xin','xtail'):
   stem=f'@m.xdut.{stage}.{dev}.m0';margins[stage+'.'+dev]=float(v[stem+'[vds]']-v[stem+'[vdsat]'])
 points=[]
 for f in (1e6,5e6,10e6,20e6):
  k=int(np.argmin(abs(a[:,0]-f)));assert abs(a[k,0]-f)<1
  points.append(dict(hz=f,source_gain=float(g[k]),terminal_gain=float(g[k]/inp[k]),input_differential_transfer=float(inp[k])))
 rows.append(dict(case=label,points=points,output_cm_v=float((v['v(op)']+v['v(on)'])/2),supply_mw=float(-3.3*v['i(vdd)']*1e3),reported_device_margins_v=margins,peak_gain=float(g.max()),peak_hz=float(a[g.argmax(),0]),artifacts_sha256=c['artifacts_sha256']))
assert np.array_equal(*grids)
assert decks[0].replace('.include /screen/bb_filter_section.spice',new+cell)==decks[1]
out=dict(completed=True,cases=rows,disposition='Unadopted: dynamic loading, stability, swing and connected conversion still required.',limitations=['Nominal stationary small-signal fixture with ideal1kohm source legs, bias and supplies.','Gain curve is not a return-ratio stability measurement; input transfer is not general switched-source impedance.'])
(P/'evidence/bb-large-input-gain.json').write_text(json.dumps(out,indent=2)+'\n');print(rows)
