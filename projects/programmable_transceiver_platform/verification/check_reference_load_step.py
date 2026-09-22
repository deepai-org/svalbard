#!/usr/bin/env python3
import hashlib,json,sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-load-step';B=R/'scratch/transceiver-reference-compensation'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
output2='--output2' in sys.argv
if output2:W=R/'scratch/transceiver-reference-output2-step';B=R/'scratch/transceiver-reference-load-step'
m=json.loads((W/'manifest.json').read_text());complete=(W/'result.json').exists();f=W/('result.json' if complete else 'progress.json');raw=json.loads(f.read_text()) if f.exists() else {'cases':[]};rows=[]
for c in raw['cases']:
 name=c['name'];source=B/(name+'.spice') if output2 else B/f"{c['rail']}_mim2048_i0_cc2_rz2000.spice";assert sha(source)==c['baseline_deck_sha256']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 d=(W/(name+'.spice')).read_text();pulse=f"ILOAD OUT 0 PWL(0 0 20n 0 20.1n {c['load_ma']}m 30n {c['load_ma']}m 30.1n 0)";restored=d
 if output2:
  for kind in ('scaled','complement'):restored=restored.replace(f'buffer_{kind}_output2.spice',f'buffer_{kind}_tune.spice').replace(f'pt_reference_buffer_{kind}_output2',f'pt_reference_buffer_{kind}_tune')
  assert restored==source.read_text()
 else:assert d.split('.control')[0].replace(pulse,'ILOAD OUT 0 DC 0 AC 1')==source.read_text().split('.control')[0]
 assert c['returncode']==0 and sha(W/(name+'.spice'))==c['deck_sha256_before']
 with (W/(name+'.dat')).open() as stream:assert stream.readline().lower().split()==['time','v(out)','v(xbuf.x)','v(xbuf.t)','i(vdd)','v(target)']
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==6 and np.isfinite(a).all() and a[-1,0]>=200e-9
 t=a[:,0]*1e9;pre=(t>=10)&(t<=19);baseline=float(a[pre,1].mean());active=t>=20;res=a[:,1]-baseline;late=(t>=180)&(t<=200);post=t>=30.1;bad=np.flatnonzero(post&(abs(res)>.001))
 rows.append(dict(name=name,baseline_v=baseline,baseline_error_mv=float((baseline-a[0,5])*1e3),max_deviation_from_preload_mv=float(np.max(abs(res[active]))*1e3),late_max_deviation_mv=float(np.max(abs(res[late]))*1e3),last_outside_1mv_after_release_ns=float(t[bad[-1]]-30.1) if len(bad) else None,peak_supply_ma=float(np.max(-a[:,4])*1e3)))
if complete:assert raw['source_sha256_before']==raw['source_sha256_after']==m['source_sha256_before'] and len(rows)==4
out=dict(status='complete_load_step_diagnostic' if complete else 'partial_load_step_diagnostic',cases=rows,manifest=m,limitations=['Signed2mA10ns pulses are selected scenarios, not maximum ADC demand or qualified source/sink capacity.', 'Unloaded OP initialization, no cold startup or input-history/mismatch variation.', '1mV recovery band is diagnostic; absolute target offset reported separately.', '20ps step, no numerical convergence or full-loop stability qualification.'])
(P/('evidence/reference-output2-step.json' if output2 else 'evidence/reference-load-step.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
