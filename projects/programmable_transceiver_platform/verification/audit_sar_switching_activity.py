"""Relate artificial carry stress to observed SAR decision-window commands."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
source=P/'evidence/adc-sar8-reference-reservoir-screen.json';d=json.loads(source.read_text());rows=[]
for case in d['cases']:
 path=R/'scratch/transceiver-adc-sar8-reference-reservoir'/(case['name']+'.dat')
 assert hashlib.sha256(path.read_bytes()).hexdigest()==case['artifacts_sha256']['.dat']
 with path.open() as f:h=f.readline().lower().split()
 a=np.loadtxt(path,skiprows=1,usecols=[0]+[h.index(f'v(sd{k})') for k in range(8)])
 for frame in case['frames']:
  tt=(frame['hold_ns']+.275+5*np.arange(8))*1e-9
  v=np.column_stack([np.interp(tt,a[:,0],a[:,k+1]) for k in range(8)])
  assert np.all((v<.33)|(v>2.97));codes=(v>1.65)@2**np.arange(8)
  transitions=[dict(before=int(x),after=int(y),toggled_unit_weight=int(x)^int(y),net_code_change=int(y)-int(x)) for x,y in zip(codes[:-1],codes[1:])]
  rows.append(dict(case=case['name'],hold_ns=frame['hold_ns'],codes=codes.tolist(),transitions=transitions))
all_transitions=[t for row in rows for t in row['transitions']]
report=dict(status='observed_sar_command_scope_audit',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),frames=rows,carry_stress=dict(before=127,after=128,toggled_unit_weight=255,net_code_change=1),largest_observed_decision_to_decision_toggle_weight=max(t['toggled_unit_weight'] for t in all_transitions),observed_carry_127_128=any(t['before']==127 and t['after']==128 for t in all_transitions),limitations=['Decision-window SD commands, not physical gate/bottom-plate timing.', 'Intermediate trial/capture/reset/track transitions may be missed between these samples.', 'Six nominal frames at two input levels do not bound all SAR activity.', 'Toggle weight alone does not predict signed charge, peak current or reference error.'])
(P/'evidence/sar-switching-activity-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print('largest sampled toggle weight',report['largest_observed_decision_to_decision_toggle_weight'],'carry observed',report['observed_carry_127_128'])
