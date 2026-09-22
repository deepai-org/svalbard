"""Calibrate device ID/VDS/VGS reporting against explicit voltage-source currents."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');PDK=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources=list(PDK.glob('*.spice'))+list(PDK.glob('*.ngspice'));before={str(p):sha(p) for p in sources}
d='''* Device observation convention only, not circuit performance
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.temp 27
VS S 0 3.3
VGN GN 0 1
VGP GP 0 2.3
''';probes=[]
for kind in ('n','p'):
 for mult in (1,4):
  name=f'{kind}{mult}';drain=1.15 if kind=='n' else 2.15;source='0' if kind=='n' else 'S';gate='GN' if kind=='n' else 'GP';model='nfet_03v3' if kind=='n' else 'pfet_03v3'
  d+=f'VD{name} D{name} 0 {drain}\nX{name} D{name} {gate} {source} {source} {model} w=8u l=.5u m={mult}\n'
  probes += [f'i(VD{name})']+[f'@m.x{name}.m0[{param}]' for param in ('id','vds','vgs','vdsat')]
d+='.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\nop\nwrdata /work/probe.dat '+' '.join(probes)+'\n.endc\n.end\n';p=O/'probe.spice';p.write_text(d);pre=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,deck_sha256_before=pre,probes=probes),indent=2)+'\n')
with (O/'probe.log').open('w') as log:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
assert r.returncode==0
a=np.loadtxt(O/'probe.dat',skiprows=1);assert a.shape==(21,) and np.isfinite(a).all();rows=[]
for j,(kind,mult) in enumerate((k,m) for k in ('n','p') for m in (1,4)):
 branch,id_,vds,vgs,vdsat=a[1+j*5:6+j*5]
 assert np.isclose(abs(branch),id_,rtol=1e-6,atol=1e-10)
 assert branch<0 if kind=='n' else branch>0
 assert np.isclose(vds,1.15,atol=1e-9) and np.isclose(vgs,1.,atol=1e-9)
 rows.append(dict(type=kind,multiplicity=mult,drain_source_branch_current_a=float(branch),reported_id_a=float(id_),reported_vds_v=float(vds),reported_vgs_v=float(vgs),reported_vdsat_v=float(vdsat)))
for i in (0,2):assert np.isclose(rows[i+1]['reported_id_a']/rows[i]['reported_id_a'],4,rtol=1e-6)
after={str(p):sha(p) for p in sources};assert before==after and sha(p)==pre
out=dict(status='device_probe_conventions_verified_at_selected_DC_points',cases=rows,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={e:sha(O/('probe'+e)) for e in ('.spice','.log','.dat')},limitations=['Selected forward-conduction nominal DC points, not reverse conduction or every transient operating region.', 'Reported ID already includes multiplicity; do not multiply again.', 'At these points PMOS VDS/VGS are positive magnitudes, not signed external terminal differences.'])
(O/'result.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
