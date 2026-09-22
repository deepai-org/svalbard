#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-compensation';B=R/'scratch/transceiver-reference-driver-impedance'
r=json.loads((W/'result.json').read_text());base=json.loads((B/'result.json').read_text());names={c['name'] for c in base['cases'] if c['reservoir']=='mim2048'}
assert {(c['baseline_name'],c['cc_unit_pf'],c['rz_unit_ohm']) for c in r['cases']}=={(n,cc,rz) for n in names for cc in (.5,1,2,4) for rz in (100,500,2000)}
for path,digest in r['source_sha256'].items():assert hashlib.sha256((P/'analog'/path.removeprefix('/screen/')).read_bytes()).hexdigest()==digest
for kind in ('scaled','complement'):
 d=(P/f'analog/reference/buffer_{kind}_tune.spice').read_text().replace(f'pt_reference_buffer_{kind}_tune',f'pt_reference_buffer_{kind}').replace('params: CC=1p S=1 RZ=100','params: CC=1p S=1').replace('{RZ/S}','{100/S}')
 assert d==(P/f'analog/reference/buffer_{kind}.spice').read_text()
for c in r['cases']:
 name=c['name'];src=B/(c['baseline_name']+'.spice');assert hashlib.sha256(src.read_bytes()).hexdigest()==c['baseline_deck_sha256']
 for ext,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+ext)).read_bytes()).hexdigest()==digest
 d=(W/(name+'.spice')).read_text()
 for kind in ('scaled','complement'):
  d=d.replace(f'buffer_{kind}_tune.spice',f'buffer_{kind}.spice').replace(f"pt_reference_buffer_{kind}_tune S=4 CC={c['cc_unit_pf']}p RZ={c['rz_unit_ohm']}",f'pt_reference_buffer_{kind} S=4')
 assert d.replace(f'/work/{name}.dat',f"/work/{c['baseline_name']}.dat")==src.read_text()
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==3 and np.isfinite(a).all();z=np.hypot(a[:,1],a[:,2]);i=int(np.argmax(z))
 c.update(peak_impedance_ohm=float(z[i]),peak_frequency_hz=float(a[i,0]),impedance_at_200mhz_ohm=float(np.interp(200e6,a[:,0],z)))
 if c['cc_unit_pf']==1 and c['rz_unit_ohm']==100:assert np.allclose(a,np.loadtxt(B/(c['baseline_name']+'.dat'),skiprows=1),rtol=1e-8,atol=1e-10)
summary=[]
for cc in (.5,1,2,4):
 for rz in (100,500,2000):
  cases=[c for c in r['cases'] if c['cc_unit_pf']==cc and c['rz_unit_ohm']==rz]
  summary.append(dict(cc_unit_pf=cc,rz_unit_ohm=rz,physical_cc_pf=4*cc,physical_rz_ohm=rz/4,worst_peak_ohm=max(c['peak_impedance_ohm'] for c in cases),worst_200mhz_ohm=max(c['impedance_at_200mhz_ohm'] for c in cases)))
r.update(status='internal_compensation_AC_audited',baseline_reproduction_checked=True,summary=summary,limitations=['Ideal compensation R/C; no physical element sizing or parasitics.', 'Closed-loop output impedance at selected DC loads; not return-ratio or stability proof.', 'No connected ADC, transient settling, noise/mismatch or startup qualification for changed settings.'])
(P/'evidence/reference-compensation-screen.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(sorted(summary,key=lambda c:c['worst_peak_ohm']),indent=2))
