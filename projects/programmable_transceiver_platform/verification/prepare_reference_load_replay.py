#!/usr/bin/env python3
"""Retain actual reference pair/reservoir, replace ADC with recorded signed current history."""
import hashlib,json,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-adc-reference-current';O=R/'scratch/transceiver-reference-load-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=P/'evidence/adc-reference-reproduction-scope.json';audit=json.loads(e.read_text());assert audit['scoped_current_diagnostic_valid']
replay=P/'evidence/adc-reference-current-replay.json';assert sha(replay)==audit['replay_evidence_sha256'];r=json.loads(replay.read_text())
for ext,h in r['provenance']['artifacts_sha256'].items():assert sha(B/('frames'+ext))==h
with (B/'frames.dat').open() as f:header=f.readline().lower().split()
a=np.loadtxt(B/'frames.dat',skiprows=1);t=a[:,0];assert np.all(np.diff(t)>0) and np.isfinite(a).all()
O.mkdir(exist_ok=True);sources=[];metrics={}
for rail in ['h','l']:
 current=a[:,header.index('i(vref'+rail+'_del)')]-a[:,header.index('i(vref'+rail+'_res)')]
 ts=t if t[0]==0 else np.r_[0.,t];ys=current if t[0]==0 else np.r_[current[0],current]
 lines=[f'ILOAD{rail.upper()} V{rail.upper()} 0 PWL(']
 for i in range(0,len(ts),4):lines.append('+ '+' '.join(f'{x:.17e} {y:.17e}' for x,y in zip(ts[i:i+4],ys[i:i+4])))
 lines.append('+ )');source='\n'.join(lines)
 # Preserve plus signs in exponents while checking serialized waveform samples.
 numbers=re.findall(r'-?\d+\.\d+e[+-]\d+',source)
 parsed=np.array(list(map(float,numbers))).reshape(-1,2)
 assert np.array_equal(parsed[:,0],ts) and np.array_equal(parsed[:,1],ys)
 sources.append(source);metrics[rail]=dict(points=len(ts),signed_charge_c=float(np.trapezoid(ys,ts)),current_range_a=[float(ys.min()),float(ys.max())])
(O/'demand.spice').write_text('\n'.join(sources)+'\n')
base=(B/'frames.spice').read_text();lines=base.splitlines()
reference=base[base.index('VHR HR'):base.index('VRST RN')]
sensors='\n'.join(x for x in lines if x.startswith(('VREFH_DEL ','VREFL_DEL ','VREFH_RES ','VREFL_RES ')))
d='\n'.join(['* Measured-load diagnostic; ADC voltage-dependent feedback removed',lines[1],lines[2],'.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical','.temp 27',reference,sensors,'.include /baseline/demand.spice','.control','set wr_singlescale','set wr_vecnames','set numdgt=15','tran 5p 209.9n 0 5p','wrdata /work/load.dat v(VH) v(VL) i(VREFSUP) i(VREFH_DEL) i(VREFL_DEL) i(VREFH_RES) i(VREFL_RES) v(XREF.XHIGH.X) v(XREF.XLOW.X)','.endc','.end',''])
(O/'load.spice').write_text(d)
m=dict(deck_sha256=sha(O/'load.spice'),demand_sha256=sha(O/'demand.spice'),scoped_audit_sha256=sha(e),baseline_artifacts_sha256=r['provenance']['artifacts_sha256'],source_sha256_before=r['provenance']['source_sha256_before'],load_metrics=metrics,reference_block_preserved=True,limitations=['Recorded current waveform freezes load voltage dependence and both-channel switching history.','Reduced baseline must reproduce reference behavior before candidate use; changed reference may change real ADC demand.','Initial current before first saved sample held constant; no cold-start qualification.','Interpolation of saved current samples is not an exact continuous-time current source.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');(P/'evidence/reference-load-preparation.json').write_text(json.dumps(m,indent=2)+'\n');print(metrics)
