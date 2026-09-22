#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-buffer-op';B=R/'scratch/transceiver-reference-buffer-dc'
r=json.loads((W/'result.json').read_text());assert hashlib.sha256((P/'analog/reference/buffer_scaled.spice').read_bytes()).hexdigest()==r['source_sha256']
assert {(c['target_v'],c['load_a']) for c in r['cases']}=={(v,i) for v in (1.15,2.15) for i in (-.015,0,.015)}
for c in r['cases']:
 for ext,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(c['name']+ext)).read_bytes()).hexdigest()==digest
 base=B/f"v{c['target_v']:g}_s16_d1.spice";assert hashlib.sha256(base.read_bytes()).hexdigest()==c['baseline_deck_sha256']
 d=(W/(c['name']+'.spice')).read_text();assert d.split('.control')[0].replace(f"ILOAD OUT 0 {c['load_a']}",'ILOAD OUT 0 0')==base.read_text().split('.control')[0]
 v=c['values'];c['devices']={}
 for dev in ('xip','xin','xt','xmp','xmn','xout','xload'):
  pre='@m.xbuf.'+dev+'.m0';c['devices'][dev]=dict(model_vds_minus_vdsat_v=v[pre+'[vds]']-v[pre+'[vdsat]'],gm_over_gds=v[pre+'[gm]']/v[pre+'[gds]'])
r['status']='reference_driver_device_headroom_audited';r['limitations']=['PDK nominal operating-region indicators, not worst-case process bounds.', 'DC diagnostic only; no feedback-loop phase margin, transient regulation or noise proof.']
(P/'evidence/reference-buffer-op-screen.json').write_text(json.dumps(r,indent=2)+'\n');print('Six OP cases audited.')
