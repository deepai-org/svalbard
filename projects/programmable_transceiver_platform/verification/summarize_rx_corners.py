#!/usr/bin/env python3
"""Aggregate retained same-circuit corner evidence without claiming qualification."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
names=['rx-buffered-screen.json','rx-process-screen.json','rx-mixed-process-screen.json']
reports=[json.loads((root/'evidence'/name).read_text()) for name in names]
common=['/screen/rf_measure.py','/screen/rx_branch_load_tb.spice.in','/screen/rx_iq_buffered_core.spice',
        '/screen/lo_buffer.spice','/screen/rx_iq_split_core.spice',
        '/src/rf_lna/lna_cs_core.spice','/src/rf_switch_mixer/mixer.spice']
for report in reports:
    assert report['status']=='simulation_completed_not_receiver_qualified'
    for field in ('temperature_c','supply_v','rf_hz','lo_hz','if_hz','max_step_s','image'):
        assert report[field]==reports[0][field],field
    for source in common:
        assert report['source_sha256'][source]==reports[0]['source_sha256'][source],source
rows=[]
for name,report in zip(names,reports):
    for row in report['summaries']:
        if row['topology']=='ideal': continue
        corner='typical' if row['topology']=='buffered' else row['topology']
        rows.append(dict(corner=corner,source=name,gain_i_v_per_v=row['gain_i_v_per_v'],
                         gain_q_v_per_v=row['gain_q_v_per_v'],
                         measured_total_current_a=row['measured_total_current_a'],
                         q_relative_to_i_deg=row['q_relative_to_i_deg']))
assert len(rows)==5 and {r['corner'] for r in rows}=={'typical','ff','ss','fs','sf'}
result=dict(status='observed_five_global_corners_not_signoff',rows=rows,
            observed_gain_range=[min(r['gain_i_v_per_v'] for r in rows),max(r['gain_i_v_per_v'] for r in rows)],
            observed_current_range_a=[min(r['measured_total_current_a'] for r in rows),max(r['measured_total_current_a'] for r in rows)],
            input_sha256={n:hashlib.sha256((root/'evidence'/n).read_bytes()).hexdigest() for n in names},
            limitations='Single-frequency small-signal schematic screens; no mismatch, passive variation, RF noise, PEX, converter load or yield bound.')
(root/'evidence/rx-five-corners.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
