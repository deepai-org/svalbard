#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform';W=ROOT/'scratch/transceiver-vco-split-tuning';r=json.loads((W/'result.json').read_text())
s=(P/'analog/pll/ring_vco_split.spice').read_text().split('\n',1)[1]
s=s.replace('pt_split_delay','cml_vco_delay').replace('pt_split_ring','ring_vco').replace('VCTRL REGEN VDD VSS','VCTRL VDD VSS').replace('XMLT LTAIL REGEN','XMLT LTAIL VCTRL')
assert s==(ROOT/'ip/blocks/analog/wireline_serdes/pll/ring_vco.spice').read_text()
for c in r['cases']:
 for suffix,h in c['artifacts_sha256'].items():assert hashlib.sha256((W/(f"v{c['control_v']:g}"+suffix)).read_bytes()).hexdigest()==h
 assert c['gate_range_v'][0]>1.4 and c['gate_range_v'][1]<1.6
base=json.loads((P/'evidence/vco-capture-tuning.json').read_text());assert abs(r['cases'][0]['frequency_hz']/base['cases'][0]['frequency_hz']-1)<.001
r['original_dimensions_preserved']=True;r['positive_secants_all_tested_intervals']=all(x>0 for x in r['slopes_hz_per_v'])
r['same_bias_baseline_frequency_difference_hz']=r['cases'][0]['frequency_hz']-base['cases'][0]['frequency_hz']
r['limitations'].append('Separate ideal regenerative-bias source is a fixture; generation/noise and robust monotonicity not implemented or qualified.')
r['source_sha256']={name:hashlib.sha256((P/'analog'/name).read_bytes()).hexdigest() for name in ('pll/ring_vco_split.spice','rf_rx_candidate_split.spice')}
(P/'evidence/vco-split-tuning.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
