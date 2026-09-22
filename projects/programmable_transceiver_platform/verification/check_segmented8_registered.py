#!/usr/bin/env python3
"""Capture, isolation, latency and output audit for actual DAC register bank."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-dac-segmented-registered';B=R/'scratch/transceiver-dac-segmented-dynamic';S=R/'scratch/transceiver-dac-segmented-dc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
coverage='--coverage' in sys.argv
if coverage:W=R/'scratch/transceiver-dac-segmented-coverage'
dual='--dual' in sys.argv
isolated='--isolated' in sys.argv or dual
variant='dual' if dual else 'isolated'
if isolated:W=R/f'scratch/transceiver-dac-segmented-{variant}';B=R/'scratch/transceiver-dac-segmented-registered'
m=json.loads((W/'manifest.json').read_text());bm=json.loads((B/'manifest.json').read_text());complete=(W/'result.json').exists();p=W/('result.json' if complete else 'progress.json');raw=json.loads(p.read_text()) if p.exists() else {'cases':[]}
for path,h in m['source_sha256_before'].items():
 if path.startswith('/screen/'):assert sha(P/'analog'/path.removeprefix('/screen/'))==h
sr=json.loads((S/'result.json').read_text());assert sha(S/'segmented.dat')==sr['artifacts_sha256']['.dat'];s=np.loadtxt(S/'segmented.dat',skiprows=1);target={k:float(s[k,2]-s[k,1]) for k in (127,128)};lsb=(s[-1,2]-s[-1,1]-s[0,2]+s[0,1])/255
vectors=(bm['vectors']+m['extra_vectors']) if not isolated else (json.loads((R/'scratch/transceiver-dac-segmented-dynamic/manifest.json').read_text())['vectors']+bm['extra_vectors']+m['extra_vectors'])
cols={v.lower():i+1 for i,v in enumerate(vectors)}
def ix(v):return cols[v.lower()]
def rises(t,v):
 i=np.flatnonzero((v[:-1]<1.65)&(v[1:]>=1.65));return t[i]+(1.65-v[i])*(t[i+1]-t[i])/(v[i+1]-v[i])
rows=[]
for c in raw['cases']:
 name=c['name'];assert sha(B/(name+'.spice'))==c['baseline_deck_sha256']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 assert sha(W/(name+'.spice'))==c['deck_sha256_before']
 d=(W/(name+'.spice')).read_text();add='.include /screen/pll/pfd.spice\nVCLK CLK 0 PULSE(0 3.3 6n 100p 100p 5n 25n)\nVRN RN 0 PWL(0 0 2n 0 2.1n 3.3)\n'
 restored=d.replace(add,'').replace('/screen/dac/segmented8_registered.spice','/screen/dac/segmented8.spice').replace('XD OP ON BN VDRV 0 CLK RN D0','XD OP ON BN VDRV 0 D0').replace(' pt_dac_segmented8_registered\n',' pt_dac_segmented8\n').replace(' '+' '.join(m['extra_vectors'])+'\n.endc','\n.endc')
 if isolated:
  restored=d.replace(f'segmented8_{variant}.spice','segmented8_registered.spice').replace(f'pt_dac_segmented8_{variant}','pt_dac_segmented8_registered').replace(' '+' '.join(m['extra_vectors'])+'\n.endc','\n.endc')
 assert restored==(B/(name+'.spice')).read_text()
 wave=W/(name+'.dat');row=dict(name=name,returncode=c['returncode'],completed=False)
 if not wave.exists():rows.append(row);continue
 with wave.open() as f:assert f.readline().lower().split()==['time']+[v.lower() for v in vectors]
 a=np.loadtxt(wave,skiprows=1);assert a.shape[1]==len(vectors)+1 and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
 row['completed']=bool(c['returncode']==0 and not c['timed_out'] and a[-1,0]>=79.9e-9 and 'aborted' not in (W/(name+'.log')).read_text().lower())
 if not row['completed']:rows.append(row);continue
 t=a[:,0];tn=t*1e9;v=a[:,2]-a[:,1];regcols=[ix(f'v(XD.RL{i})') for i in range(4)]+[ix(f'v(XD.RH{k})') for k in range(1,16)]
 captures=[]
 for lo,hi,code in ((20,25,127),(45,50,128),(70,75,127)):
  mask=(tn>=lo)&(tn<=hi);expected=np.array([(code>>i)&1 for i in range(4)]+[int(code//16>=k) for k in range(1,16)])
  captures.append(dict(window_ns=[lo,hi],code=code,max_register_rail_error_v=float(np.max(abs(a[mask][:,regcols]-3.3*expected))),output_error_mv=float(np.max(abs(v[mask]-target[code]))*1e3)))
 if dual:
  qbcols=[ix(f'v(XD.RLB{i})') for i in range(4)]+[ix(f'v(XD.RHB{k})') for k in range(1,16)]
  for capture in captures:
   lo,hi=capture['window_ns'];code=capture['code'];mask=(tn>=lo)&(tn<=hi)
   expected=np.array([(code>>i)&1 for i in range(4)]+[int(code//16>=k) for k in range(1,16)])
   capture['max_complement_register_rail_error_v']=float(np.max(abs(a[mask][:,qbcols]-3.3*(1-expected))))
 clock=rises(t,a[:,ix('v(XD.CK)')])*1e9;events=[]
 for command,old,new in ((30,127,128),(55,128,127)):
  edge=clock[(clock>command)&(clock<command+3)];assert len(edge)==1;edge=float(edge[0]);w=(tn>=command-.5)&(tn<=edge+10)
  error=v[w]-np.where(tn[w]<edge,target[old],target[new]);pre=(tn>=command-.3)&(tn<edge)
  oldstates=np.array([(old>>i)&1 for i in range(4)]+[int(old//16>=k) for k in range(1,16)])
  events.append(dict(command_ns=command,buffered_clock_edge_ns=edge,peak_error_mv=float(np.max(abs(error))*1e3),absolute_error_area_mv_ns=float(np.trapezoid(abs(error),t[w])*1e12),pre_capture_output_deviation_mv=float(np.max(abs(v[pre]-target[old]))*1e3),pre_capture_registers_hold=bool(np.all((a[pre][:,regcols]>1.65)==oldstates))))
 row.update(captures=captures,events=events,clock_rising_edges_ns=clock.tolist(),total_logic_peak_current_ma=float(np.max(-a[:,4])*1e3),external_clock_peak_source_current_ma=float(np.max(-a[:,ix('i(VCLK)')])*1e3))
 rows.append(row)
if complete:assert raw['source_sha256_before']==raw['source_sha256_after']==m['source_sha256_before'] and {c['name'] for c in rows}==set(m['planned_cases'])
r=dict(status='complete_registered_diagnostic' if complete else 'partial_registered_diagnostic',cases=rows,manifest=m,limitations=['Clock-based ideal transition includes real clock-to-output delay; no individual cell realignment.', 'Fixed nominal capture interval, two cases; not setup/hold, clock jitter, noise/mismatch or full load qualification.', 'Supply is ideal; added clock and logic currents do not yet have a shared physical supply network.'])
(P/(f'evidence/dac-segmented8-{variant}.json' if isolated else ('evidence/dac-segmented8-coverage.json' if coverage else 'evidence/dac-segmented8-registered.json'))).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,indent=2))
