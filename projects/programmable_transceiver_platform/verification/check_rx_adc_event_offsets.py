#!/usr/bin/env python3
"""Preserve failures, verify declared perturbation and compare pre-event behavior."""
import argparse,hashlib,json,re
from pathlib import Path
import numpy as np
ap=argparse.ArgumentParser();ap.add_argument('--baseline-audit',action='store_true');ap.add_argument('--separated',action='store_true');args=ap.parse_args()
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-rx-adc-event-offsets';B=R/'scratch/transceiver-rx-adc-loading/loaded';V=R/'scratch/transceiver-rx-adc-event-offsets-prepared'
if args.separated:
 W=R/'scratch/transceiver-rx-adc-separated-events-v2';V=R/'scratch/transceiver-rx-adc-separated-events-prepared-v2'
compare_end=473.3e-9 if args.separated else 478.3e-9
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(root):
 r=json.loads((root/'result.json').read_text());assert r['sources_before']==r['sources_after']
 for ext,h in r['artifacts_sha256'].items():assert sha(root/('connected'+ext))==h
 log=(root/'connected.log').read_text();errors=[x.strip() for x in log.splitlines() if any(k in x.lower() for k in ('warning','error','aborted','timestep too small'))]
 row=dict(returncode=r['returncode'],timed_out=r['timed_out'],errors=errors,artifacts_sha256=r['artifacts_sha256'],completed=False)
 if not (root/'connected.dat').exists():return row,None,None
 with (root/'connected.dat').open() as f:h=f.readline().lower().split()
 a=np.loadtxt(root/'connected.dat',skiprows=1);t=a[:,0];assert a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(t)>=0)
 expected=next(l for l in (root/'connected.spice').read_text().splitlines() if l.startswith('wrdata ')).lower().split()[2:];assert h==['time']+expected
 row.update(actual_stop_ns=float(t[-1]*1e9),rows=len(a),repeated_times=int((np.diff(t)==0).sum()),completed=bool(r['returncode']==0 and not r['timed_out'] and not errors and t[-1]+1e-21>=610e-9))
 return row,h,a
base,bh,b=read(B);assert not base['completed'] and b is not None
prep=json.loads((V/'manifest.json').read_text());assert sha(B/'connected.spice')==prep['parent_deck_sha256']
rows=[]
for c in prep['cases']:
 name=c['case'];root=W/name;row=dict(case=name,status='pending',completed=False);rows.append(row)
 if args.baseline_audit:root=B
 elif not (root/'result.json').exists():continue
 if not args.baseline_audit:
  m=json.loads((root/'manifest.json').read_text());assert sha(root/'connected.spice')==m['deck_sha256'];assert sha(V/(name+'.spice'))==c['deck_sha256']
  restored=(root/'connected.spice').read_text().replace(f'/work/{name}/connected.dat','/work/loaded/connected.dat').replace(c['changed_line'],c['original_line']);assert restored==(B/'connected.spice').read_text()
 result,h,a=read(root);row.update(result,status='terminal')
 if a is None:continue
 row['pre_event_comparison_window_ns']=[350,compare_end*1e9]
 assert h==bh
 # Restrict comparison well before the earliest changed edge; avoid repeated failure timestamps.
 mask=(a[:,0]>=350e-9)&(a[:,0]<=compare_end);bm=(b[:,0]>=349e-9)&(b[:,0]<=compare_end+.1e-9)
 if mask.any() and bm.any() and a[mask,0][-1]<=b[bm,0][-1]:
  assert np.all(np.diff(a[mask,0])>0) and np.all(np.diff(b[bm,0])>0)
  names=['v(fip)','v(fin)','v(fqp)','v(fqn)','v(xadc.vh)','v(xadc.vl)','v(xadc.hp)','v(xadc.hn)']
  row['pre_event_max_errors_v']={n:float(abs(a[mask,h.index(n)]-np.interp(a[mask,0],b[bm,0],b[bm,bh.index(n)])).max()) for n in names}
  if args.baseline_audit:assert max(row['pre_event_max_errors_v'].values())==0
out=dict(mode='failed_baseline_self_check' if args.baseline_audit else 'schedule_wide_edge_comparison' if args.separated else 'signed_edge_comparison',cases=rows,matrix_terminal=all(x['status']=='terminal' for x in rows),completed=all(x['completed'] for x in rows),limitations=['Successful simulation would establish event sensitivity, not a physical fix.','Pre-event interpolation is diagnostic without a new acceptance threshold.','No ADC quality/noise claim from this inherited aliasing stimulus.'])
path=P/'evidence'/(('rx-adc-separated-checker-self-audit.json' if args.separated else 'rx-adc-event-checker-self-audit.json') if args.baseline_audit else 'rx-adc-separated-events.json' if args.separated else 'rx-adc-event-offsets.json');path.write_text(json.dumps(out,indent=2)+'\n');print([(r['case'],r['status'],r['completed']) for r in rows])
