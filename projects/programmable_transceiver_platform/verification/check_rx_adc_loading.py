#!/usr/bin/env python3
"""Connected loading completion and bias-window diagnostics, not ADC qualification."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--preflight',action='store_true');args=ap.parse_args()
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
name='rx-adc-loading-preflight-v2' if args.preflight else 'rx-adc-loading';W=R/'scratch'/('transceiver-'+name);horizon=1 if args.preflight else 610
B=R/'scratch/transceiver-rx-adc-preflight-dedup/connected.spice'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for case in ('loaded','isolated'):
 root=W/case;row=dict(case=case,status='pending',completed=False);rows.append(row)
 if not (root/'result.json').exists():continue
 m=json.loads((root/'manifest.json').read_text());r=json.loads((root/'result.json').read_text())
 assert m['requested_horizon_ns']==horizon and m['parent_sha256']==sha(B)
 assert sha(root/'connected.spice')==m['deck_sha256']
 assert r['sources_before']==r['sources_after']==m['sources_before']
 for ext,h in r['artifacts_sha256'].items():assert sha(root/('connected'+ext))==h
 log=(root/'connected.log').read_text();errors=[l.strip() for l in log.splitlines() if any(x in l.lower() for x in ('warning','error','aborted'))]
 row.update(status='terminal',returncode=r['returncode'],timed_out=r['timed_out'],errors=errors,artifacts_sha256=r['artifacts_sha256'])
 if errors or r['returncode']!=0 or r['timed_out']:continue
 with (root/'connected.dat').open() as f:h=f.readline().lower().split()
 a=np.loadtxt(root/'connected.dat',skiprows=1);t=a[:,0]
 wr=next(l for l in (root/'connected.spice').read_text().splitlines() if l.startswith('wrdata ')).lower().split()[2:]
 assert h==['time']+wr and a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(t)>0)
 row.update(actual_stop_s=float(t[-1]),rows=len(a),columns=len(h),completed=bool(t[-1]+1e-21>=horizon*1e-9))
 if not row['completed']:continue
 def v(n):return a[:,h.index(n)]
 def stats(y,lo,hi):
  lo*=1e-9;hi*=1e-9
  assert lo>=t[0] and hi<=t[-1]+1e-21
  tt=np.r_[lo,t[(t>lo)&(t<hi)],hi];yy=np.interp(tt,t,y)
  return dict(mean=float(np.trapezoid(yy,tt)/(hi-lo)),min=float(yy.min()),max=float(yy.max()),end_minus_start=float(yy[-1]-yy[0]))
 windows=[(.5,1)] if args.preflight else [(350,400),(420,450),(450,469),(500,519),(550,569),(590,609)]
 biases={}
 for node in ('BN','BP','Q_BN','Q_BP','RBN','RBP'):
  biases[node]=[dict(window_ns=[lo,hi],**stats(v(f'v(xadc.{node.lower()})'),lo,hi)) for lo,hi in windows]
 row['bias_windows_v']=biases
 row['filter_windows']=[]
 for prefix in ('i','q'):
  pos=v(f'v(f{prefix}p)');neg=v(f'v(f{prefix}n)')
  for lo,hi in windows:row['filter_windows'].append(dict(channel=prefix,window_ns=[lo,hi],differential_v=stats(pos-neg,lo,hi),common_mode_v=stats((pos+neg)/2,lo,hi)))
 if not args.preflight:
  row['held_windows']=[]
  for hold in (470,520,570):
   for prefix in ('','q_'):
    row['held_windows'].append(dict(hold_ns=hold,channel=prefix or 'i',differential_v=stats(v(f'v(xadc.{prefix}hp)')-v(f'v(xadc.{prefix}hn)'),hold+.2,hold+.35)))
 row['qualification']='Diagnostic measurements only; no bias-settling threshold allocated or conversion qualification.'
out=dict(cases=rows,matrix_terminal=all(x['status']=='terminal' for x in rows),completed=all(x['completed'] for x in rows),limitations=['Ideal isolation is a loading control, not implemented hardware.','Bias window stability alone does not establish device headroom, gain, or full startup.','Seeded RF UIC and ideal clock/bias sources remain.','No code/ENOB claim; physical bias must be assessed first.'])
(P/'evidence'/(name+'-check.json')).write_text(json.dumps(out,indent=2)+'\n')
print([(x['case'],x['status'],x['completed']) for x in rows])
