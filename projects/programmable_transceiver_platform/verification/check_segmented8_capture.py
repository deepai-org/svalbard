#!/usr/bin/env python3
"""Preserve failed captures in the signed clock-phase diagnostic."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-dac-segmented-capture';B=R/'scratch/transceiver-dac-segmented-registered'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());src=B/'c32_skew0.spice';assert sha(src)==m['baseline_deck_sha256']
for path,h in m['source_sha256_before'].items():
 if path.startswith('/screen/'):assert sha(P/'analog'/path.removeprefix('/screen/'))==h
vectors=json.loads((R/'scratch/transceiver-dac-segmented-dynamic/manifest.json').read_text())['vectors']+json.loads((B/'manifest.json').read_text())['extra_vectors'];cols={v.lower():i+1 for i,v in enumerate(vectors)}
complete=(W/'result.json').exists();p=W/('result.json' if complete else 'progress.json');raw=json.loads(p.read_text()) if p.exists() else {'cases':[]};rows=[]
for c in raw['cases']:
 name=c['name'];offset=c['capture_offset_ns'];assert offset in m['capture_offsets_ns']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 assert sha(W/(name+'.spice'))==c['deck_sha256_before']
 d=(W/(name+'.spice')).read_text();old='VCLK CLK 0 PULSE(0 3.3 6n 100p 100p 5n 25n)';new=f'VCLK CLK 0 PULSE(0 3.3 {6+offset:g}n 100p 100p 5n 25n)';assert d.replace(new,old).replace(f'/work/{name}.dat','/work/c32_skew0.dat')==src.read_text()
 row=dict(name=name,offset_ns=offset,completed=False);wave=W/(name+'.dat')
 if not wave.exists():rows.append(row);continue
 with wave.open() as f:assert f.readline().lower().split()==['time']+[v.lower() for v in vectors]
 a=np.loadtxt(wave,skiprows=1);assert np.isfinite(a).all() and a.shape[1]==len(vectors)+1 and np.all(np.diff(a[:,0])>0)
 row['completed']=bool(c['returncode']==0 and not c['timed_out'] and a[-1,0]>=79.9e-9 and 'aborted' not in (W/(name+'.log')).read_text().lower())
 if row['completed']:
  t=a[:,0]*1e9;captures=[];qcols=[cols[f'v(xd.rl{i})'] for i in range(4)]+[cols[f'v(xd.rh{k})'] for k in range(1,16)]
  for lo,hi,code in ((20,25,127),(45,50,128),(70,75,127)):
   w=a[(t>=lo)&(t<=hi)];expected=np.array([(code>>i)&1 for i in range(4)]+[int(code//16>=k) for k in range(1,16)]);states=w[:,qcols]>1.65
   weighted=states[:,:4]@np.array([1,2,4,8])+16*states[:,4:].sum(axis=1)
   captures.append(dict(window_ns=[lo,hi],intended_code=code,observed_weighted_code_range=[int(weighted.min()),int(weighted.max())],all_register_bits_correct=bool(np.all(states==expected)),max_register_rail_error_v=float(np.max(abs(w[:,qcols]-3.3*expected))),mean_output_v=float(np.mean(w[:,2]-w[:,1]))))
  row['captures']=captures
 rows.append(row)
if complete:assert raw['source_sha256_before']==raw['source_sha256_after']==m['source_sha256_before'] and len(rows)==3
out=dict(status='complete_capture_phase_diagnostic' if complete else 'partial_capture_phase_diagnostic',cases=rows,manifest=m,limitations=['Fixed nominal code/load/input-skew; signed clock offsets are scenarios, not setup/hold bounds.', 'Late capture correctness does not establish absence of metastability or bounded resolution time.', 'Output glitches and repeated arbitrary data remain separate quality requirements.'])
(P/'evidence/dac-capture-phase.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
