#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];W=ROOT/'scratch/transceiver-loaded-divider';r=json.loads((W/'result.json').read_text())
for c in r['cases']:
 name='restored' if c['restored'] else 'direct'
 for s,h in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+s)).read_bytes()).hexdigest()==h
 c['nominal_division_check']=bool(c['ratio'] is not None and abs(c['ratio']-2)<.001 and c['divider_edges']>=24 and c['divider_diff_range_v'][0]<-.5 and c['divider_diff_range_v'][1]>.5 and c['gate_range_v'][0]>1.4 and c['gate_range_v'][1]<1.6)
 assert c['nominal_division_check']
r['source_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['projects/programmable_transceiver_platform/analog/rf_rx_candidate.spice','ip/blocks/analog/wireline_serdes/pll/divider.spice','ip/blocks/analog/wireline_serdes/pll/clock_restorer_cascade.spice']}
r['limitations'].append('Femtosecond deterministic period spread is numerical waveform variation, not intrinsic jitter evidence.')
(ROOT/'projects/programmable_transceiver_platform/evidence/loaded-divider-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print('Both nominal first-stage divider scenarios pass bias, amplitude and ratio checks.')
