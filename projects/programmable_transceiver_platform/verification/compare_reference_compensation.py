#!/usr/bin/env python3
"""Paired baseline/candidate observations at identical ADC decision windows."""
import hashlib,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';E=P/'evidence'
files=['adc-reference-reservoir-decision-windows.json','adc-reference-compensated-decision-windows.json','adc-sar8-reference-reservoir-screen.json','adc-sar8-reference-compensated-screen.json']
output2='--output2' in sys.argv
if output2:files=[f.replace('compensated','output2').replace('reservoir','compensated') for f in files]
base,new,bc,nc=[json.loads((E/f).read_text()) for f in files];rows=[]
def metrics(c,full):
 steps=[s for f in c['frames'] for s in f['steps']]
 return dict(max_in_window_span_motion_mv=max(s['span_peak_to_peak_mv'] for s in steps),span_range_v=[min(s['span_mean_v'] for s in steps),max(s['span_mean_v'] for s in steps)],worst_high_error_mv=max(s['high_max_error_mv'] for s in steps),worst_low_error_mv=max(s['low_max_error_mv'] for s in steps),codes=[f['final_code'] for f in full['frames']],held_errors_v=[f['held_error_v'] for f in full['frames']],reference_average_current_ma=[f['reference_supply_average_ma'] for f in full['frames']],reference_peak_current_ma=max(f['reference_supply_peak_ma'] for f in full['frames']))
for c in new['cases']:
 b=next(x for x in base['cases'] if x['name']==c['name'])
 assert len(c['frames'])==len(b['frames'])
 for cf,bf in zip(c['frames'],b['frames']):
  assert cf['hold_ns']==bf['hold_ns'] and cf['input_v']==bf['input_v']
  assert [(s['bit'],s['window_ns']) for s in cf['steps']]==[(s['bit'],s['window_ns']) for s in bf['steps']]
 rows.append(dict(name=c['name'],baseline=metrics(b,next(x for x in bc['cases'] if x['name']==c['name'])),candidate=metrics(c,next(x for x in nc['cases'] if x['name']==c['name']))))
out=dict(status='paired_reference_compensation_observations',cases=rows,pending=new['pending'],evidence_sha256={f:hashlib.sha256((E/f).read_bytes()).hexdigest() for f in files},limitations=['Identical nominal decision windows, not a complete comparator aperture or jitter analysis.', 'Reduced error is not reference qualification; selected codes and logic correctness do not establish ADC precision.', 'AC candidate compensation remains ideal components, with ideal targets/bias and separate supply.'])
(E/('reference-output2-connected-comparison.json' if output2 else 'reference-compensation-connected-comparison.json')).write_text(json.dumps(out,indent=2)+'\n');print('Compared',len(rows),'histories; pending:',new['pending'])
