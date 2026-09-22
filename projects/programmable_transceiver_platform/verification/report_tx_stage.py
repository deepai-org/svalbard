import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform'
def sha(x):return hashlib.sha256(x.read_bytes()).hexdigest()
r=json.loads((root/'scratch/transceiver-tx-stage-mapping/buffered/timing-screen.json').read_text())
assert r['area_screen']['source_sha256']['rtl/pt_stream_tx.sv']==sha(p/'rtl/pt_stream_tx.sv')
logs=['transceiver-tx-stage-tests.log','transceiver-tx-stage-compare.log']
t=[(root/'scratch'/f).read_text() for f in logs]
assert 'BASELINE_PASS' in t[0] and 'STREAM_TX_PASS cycles=84096' in t[0]
assert 'TX_STAGE_COMPARE_PASS cycles=69824 reset_phases=128' in t[1]
r['functional_verification']={'scope':'Finite cycle-exact external-interface simulation, independent codec vectors and integrated baseline; not formal equivalence',
 'logs_sha256':{f:sha(root/'scratch'/f) for f in logs},
 'source_sha256':{f:sha(p/f) for f in ['evidence/experiments/tx-before-stage.sv','sim/tb_tx_stage_compare.sv','verification/run_tx_stage_compare.sh','verification/run_delay_mapping.sh','verification/report_tx_stage.py']}}
r['comparison_reference']='delay-sized-screen.json: same explicit 3200 ps ABC target and sizing boundary, before TX stage; unplaced zero-wire comparison only'
(p/'evidence/tx-stage-screen.json').write_text(json.dumps(r,indent=2)+'\n')
