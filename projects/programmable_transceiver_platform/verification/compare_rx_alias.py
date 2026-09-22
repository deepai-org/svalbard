#!/usr/bin/env python3
"""Compare settled wanted-edge and aliased-tone small-signal chain responses."""
import hashlib,json,math
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'evidence'
names=['rx-filtered-settling.json','rx-alias-screen.json']
base,alias=[json.loads((root/n).read_text()) for n in names]
for key in ('supply_v','temperature_c','process','sample_rate_hz','hold_cap_per_leg_f','filter_r_ohm','filter_c_per_leg_f','measurement_end_s','extended','image'):
    assert base[key]==alias[key],key
for key,value in base['source_sha256'].items():
    if key.endswith('/rx_filtered_sampler_screen.py'): continue
    assert alias['source_sha256'][key]==value,key
assert alias['analog_if_hz']==30e6 and alias['signed_complex_alias_hz']==-10e6
rows=[dict(channel=channel,wanted_gain=want,alias_gain=unwanted,relative_rejection_db=20*math.log10(want/unwanted))
      for channel,want,unwanted in zip(('I','Q'),base['held_tone_gain'],alias['held_tone_gain'])]
result=dict(status='separate_tone_chain_comparison_not_filter_qualification',channels=rows,
            late_window_diagnostics={name:r['convergence'] for name,r in zip(names,(base,alias))},
            input_sha256={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names},
            limitations=['Includes frequency dependence of receiver, filter and sampler.',
                         'No simultaneous blocker, noise, mismatch, PEX or full band response.',
                         'Reference pass 101 uses the original fixed 2.41 GHz RF / 10 MHz IF bench.'])
(root/'rx-alias-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(rows,indent=2))
