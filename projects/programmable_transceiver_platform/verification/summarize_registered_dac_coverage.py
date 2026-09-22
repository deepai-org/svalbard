#!/usr/bin/env python3
"""Combine disjoint load/skew cases without elevating scenarios to physical bounds."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';E=P/'evidence'
files=['dac-segmented8-registered.json','dac-segmented8-coverage.json'];data=[json.loads((E/f).read_text()) for f in files]
assert all(d['status']=='complete_registered_diagnostic' for d in data)
assert data[0]['manifest']['source_sha256_before']==data[1]['manifest']['source_sha256_before']
rows=[]
for d in data:
 for c in d['cases']:
  assert c['completed']
  rows.append(dict(name=c['name'],capture_windows=c['captures'],pre_capture_holds=[e['pre_capture_registers_hold'] for e in c['events']],peak_errors_mv=[e['peak_error_mv'] for e in c['events']]))
assert len(rows)==6 and {c['name'] for c in rows}=={f'c{u}_skew{s:g}' for u in (32,128) for s in (-.2,0,.2)}
assert all(all(c['pre_capture_holds']) and all(x['max_register_rail_error_v']<.33 for x in c['capture_windows']) for c in rows)
out=dict(status='six_nominal_load_skew_scenarios_verified',cases=rows,source_evidence_sha256={f:hashlib.sha256((E/f).read_bytes()).hexdigest() for f in files},largest_observed_peak_error_mv=max(max(c['peak_errors_mv']) for c in rows),limitations=['One carry pair, two declared capacitor loads and three MSB command skews, matched typical devices.', 'These scenarios do not establish unknown fabrication/package bounds, yield or dynamic range.', 'Only the original fixed capture interval; setup/hold sweep is separate and includes known wrong-code failures.', 'No arbitrary-code spectrum, reconstruction/upconversion, reference noise or shared-supply verification.'])
(E/'dac-registered-coverage-summary.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['largest_observed_peak_error_mv'])
