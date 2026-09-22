"""Retain the rejected count-stage experiment, bound to its source and logs."""
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform'
def sha(x):return hashlib.sha256(x.read_bytes()).hexdigest()
r=json.loads((root/'scratch/transceiver-count-stage-mapping/buffered/timing-screen.json').read_text())
assert r['area_screen']['source_sha256']['rtl/pt_stream_tx.sv']==sha(p/'evidence/experiments/tx-count-stage.sv')
logs=['transceiver-count-stage-tests.log','transceiver-count-stage-vectors.log']
t=[(root/'scratch'/f).read_text() for f in logs]
assert 'BASELINE_PASS' in t[0] and 'TX_STAGE_COMPARE_PASS cycles=69824 reset_phases=128' in t[0]
assert 'STREAM_TX_PASS cycles=84096' in t[1]
r['decision']='Rejected as default: no host-TX setup improvement, host-RX regression in whole-design remapping; retain pass-37 RTL. No physical comparison performed.'
r['comparison_reference']='tx-stage-screen.json: same 3200 ps ABC target and sizing boundary'
r['functional_verification']={'scope':'Finite simulation; no formal or physical qualification',
 'logs_sha256':{f:sha(root/'scratch'/f) for f in logs},
 'source_sha256':{f:sha(p/f) for f in ['evidence/experiments/tx-count-stage.sv','evidence/experiments/tx-before-count-stage.sv','verification/stream_tx_vectors.py','verification/report_count_stage.py']}}
(p/'evidence/rejected-count-stage-screen.json').write_text(json.dumps(r,indent=2)+'\n')
