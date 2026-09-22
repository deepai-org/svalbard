"""Validate signed load sweeps; report compliance loss without adoption."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--tight",action="store_true");args=ap.parse_args()
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-hybrid-load-dc'
if args.tight:W=R/'scratch/transceiver-reference-hybrid-load-tolerance'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());rows=[];arrays={}
for c in r['cases']:
 name=c['name'];assert c['returncode']==0 and c['sources_before']==c['sources_after']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 log=(W/(name+'.log')).read_text().lower();assert not any(k in log for k in ('error','warning','aborted'))
 parent=R/'scratch'/('transceiver-reference-pair-device-dc' if name.startswith('baseline') else 'transceiver-reference-pair-hybrid-dc')/'VH.spice';assert sha(parent)==c['parent_sha256']
 d=(W/(name+'.spice')).read_text()
 if args.tight:
  original=(R/'scratch/transceiver-reference-hybrid-load-dc'/(name+'.spice')).read_text()
  assert d.replace('.options reltol=1e-5 vntol=1e-8 abstol=1e-14\n','')==original
  d=d.replace('.options reltol=1e-5 vntol=1e-8 abstol=1e-14\n','')
 assert d.split('.control')[0]==parent.read_text().split('.control')[0]+'ILOAD OH 0 DC 0\n'
 with (W/(name+'.dat')).open() as stream:assert stream.readline().lower().split()==['i-sweep','v(oh)','v(ol)','v(xdut.xhigh.x)','i(vdd)']
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape==(81,5) and np.isfinite(a).all()
 if name.endswith('down'):a=a[::-1]
 assert np.allclose(a[:,0],np.linspace(-.01,.01,81),rtol=0,atol=1e-15);arrays[name]=a
 selected=[]
 for current in (-.01,-.005,-.003,-.001,0,.001,.003,.005,.01):
  i=int(abs(a[:,0]-current).argmin());assert abs(a[i,0]-current)<1e-15
  selected.append(dict(load_current_a=current,high_v=float(a[i,1]),high_target_error_v=float(a[i,1]-2.15),output_gate_v=float(a[i,3]),supply_power_w=float(-3.3*a[i,4])))
 rows.append(dict(name=name,artifacts_sha256=c['artifacts_sha256'],selected=selected,rail_excursions=int(((a[:,1]<0)|(a[:,1]>3.3)).sum())))
out=dict(completed=True,cases=rows,direction_max_difference_v={v:float(abs(arrays[v+'_up'][:,1:4]-arrays[v+'_down'][:,1:4]).max()) for v in ('baseline','hybrid')},limitations=['Static ideal-current stress, not actual CDAC pulse response or safe operating area qualification.', 'Positive current withdraws charge from high rail; negative injects it. Rail excursions are failures, not usable operating points.', 'No physical supply sink behavior, current limiting, protection or real bias/startup demonstrated.'])
(P/'evidence'/('reference-hybrid-load-tolerance.json' if args.tight else 'reference-hybrid-load-dc.json')).write_text(json.dumps(out,indent=2)+'\n')
for row in rows:
 if row['name'].endswith('up'):print(row['name'],[(x['load_current_a'],round(x['high_v'],6)) for x in row['selected']])
print('direction differences',out['direction_max_difference_v'])
