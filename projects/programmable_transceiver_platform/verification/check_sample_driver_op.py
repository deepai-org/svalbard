#!/usr/bin/env python3
"""Preserve nominal headroom failures rather than accepting DC gain alone."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform';parser=argparse.ArgumentParser();parser.add_argument('--headroom',action='store_true');args=parser.parse_args();tag='sample-driver-headroom-op' if args.headroom else 'sample-driver-op';W=ROOT/('scratch/transceiver-adc-'+tag)
r=json.loads((W/'result.json').read_text())
source=P/('analog/adc/sample_driver_headroom.spice' if args.headroom else 'analog/adc/sample_driver.spice')
assert hashlib.sha256(source.read_bytes()).hexdigest()==r['source_sha256']
if args.headroom:
 original=(P/'analog/adc/sample_driver.spice').read_text()
 assert source.read_text().replace('pt_sample_driver_headroom','pt_sample_driver').replace('XOUT OUT X VSS VSS nfet_03v3 w=8u l=.5u m=8','XOUT OUT X VSS VSS nfet_03v3 w=8u l=.5u m=32')==original
 r['output_device_only_change_checked']=True
assert len(r['cases'])==4
for c in r['cases']:
 for suffix,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(c['name']+suffix)).read_bytes()).hexdigest()==digest
 a=np.loadtxt(W/(c['name']+'.dat'),skiprows=1);assert len(a)==44 and np.isfinite(a).all()
 assert np.allclose(a[1:],list(c['values'].values()),rtol=1e-12,atol=1e-15)
 v=c['values'];c['differential_gain_for_0p4v']=float((v['v(OP)']-v['v(ON)'])/.4)
 c['vds_minus_model_vdsat_v']={dev:v[f'@m.{dev}.m0[vds]']-v[f'@m.{dev}.m0[vdsat]'] for dev in ('xp.xip','xp.xin','xp.xt','xn.xip','xn.xin','xn.xt')}
 c['all_probed_nfet_headroom_positive']=all(x>0 for x in c['vds_minus_model_vdsat_v'].values())
r['model_operating_points_checked']=True;r['driver_qualified']=False
(P/('evidence/adc-'+tag+'.json')).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps([{k:c[k] for k in ('common_mode_v','differential_gain_for_0p4v','vds_minus_model_vdsat_v')} for c in r['cases']],indent=2))
