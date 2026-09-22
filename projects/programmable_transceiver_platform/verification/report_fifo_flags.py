import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-fifo-flags-mapping/buffered'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
r=json.loads((out/'timing-screen.json').read_text())
assert r['area_screen']['source_sha256']['rtl/pt_fifo.sv']==sha(p/'rtl/pt_fifo.sv')
logs=['transceiver-sync-fifo-flags.log','transceiver-fifo-flags-baseline.log']
a,b=[(root/'scratch'/f).read_text() for f in logs]
assert 'SYNC_FIFO_FLAGS_PASS cycles=26864 boundary_cases=132' in a
assert 'FIFO_FLAGS_NEGATIVE_CONTROL_PASS early_full' in a
assert 'BASELINE_PASS' in b
r['clock_pin_screen']=json.loads((out/'clock-power-screen.json').read_text())
r['verification']={'scope':'Independent queue/count/error scoreboard for installed W=10,A=5 FIFOs; all occupancies and push/pop pairs, random wrap/reset; not CDC or formal signoff',
 'logs_sha256':{f:sha(root/'scratch'/f) for f in logs},
 'source_sha256':{f:sha(p/f) for f in ['sim/tb_sync_fifo_flags.sv','verification/run_sync_fifo_flags.sh','verification/fifo_flags_negative_control.py','verification/report_fifo_flags.py','evidence/experiments/fifo-before-registered-flags.sv']}}
r['decision']='Retain registered synchronous FIFO flags as RTL candidate. No capacity, accepted-transfer boundary policy or target-rate change.'
r['comparison_reference']='pack-stage-screen.json'
(p/'evidence/fifo-flags-screen.json').write_text(json.dumps(r,indent=2)+'\n')
