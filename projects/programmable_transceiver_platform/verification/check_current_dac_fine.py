#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-dac-dynamic-fine';B=R/'scratch/transceiver-dac-dynamic'
r=json.loads((W/'result.json').read_text());name=r['name'];assert r['returncode']==0 and r['source_sha256_before']==r['source_sha256_after']
for ext,digest in r['artifacts_sha256'].items():assert hashlib.sha256((W/(name+ext)).read_bytes()).hexdigest()==digest
src=B/(name+'.spice');assert hashlib.sha256(src.read_bytes()).hexdigest()==r['baseline_deck_sha256'];assert (W/(name+'.spice')).read_text().replace('tran 2.5p 79.9n 0 2.5p','tran 5p 79.9n 0 5p')==src.read_text()
base=json.loads((P/'evidence/current-dac-dynamic-screen.json').read_text());old=next(c for c in base['cases'] if c['name']==name);a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==29 and np.isfinite(a).all() and a[-1,0]>=79.9e-9
assert hashlib.sha256((B/(name+'.dat')).read_bytes()).hexdigest()==old['artifacts_sha256']['.dat'];b=np.loadtxt(B/(name+'.dat'),skiprows=1)
t=a[:,0]*1e9;v=a[:,2]-a[:,1];rows=[]
for edge,oldcode,newcode in ((30,127,128),(55,128,127)):
 w=(t>=edge-.5)&(t<=edge+10);ideal=np.where(t[w]<edge+.05,base['dc_targets_v'][str(oldcode)],base['dc_targets_v'][str(newcode)]);error=v[w]-ideal
 peak=float(np.max(abs(error))*1e3);area=float(np.trapezoid(abs(error),a[w,0])*1e12);reference=next(x for x in old['transitions'] if x['edge_ns']==edge)
 rows.append(dict(edge_ns=edge,coarse_peak_mv=reference['peak_error_mv'],fine_peak_mv=peak,peak_change_percent=100*(peak/reference['peak_error_mv']-1),coarse_absolute_area_mv_ns=reference['absolute_error_area_mv_ns'],fine_absolute_area_mv_ns=area,area_change_percent=100*(area/reference['absolute_error_area_mv_ns']-1)))
mask=(b[:,0]>=20e-9)&(b[:,0]<=79e-9);delta=float(np.max(abs(np.interp(b[mask,0],a[:,0],v)-(b[mask,2]-b[mask,1]))))
r.update(status='halved_step_major_carry_sensitivity_audited',transitions=rows,max_interpolated_output_difference_v=delta,limitations=['One selected worst observed case; timestep sensitivity is not complete numerical convergence or silicon validation.', 'No intrinsic noise/mismatch, parasitics or RF spectrum qualification.'])
(P/'evidence/current-dac-dynamic-fine-screen.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,indent=2))
