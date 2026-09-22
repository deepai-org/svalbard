import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-pack-stage-mapping/buffered'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
r=json.loads((out/'timing-screen.json').read_text())
assert r['area_screen']['source_sha256']['rtl/pt_pack.sv']==sha(p/'rtl/pt_pack.sv')
logs=['transceiver-pack-stream.log','transceiver-pack-stage-baseline.log']
a,b=[(root/'scratch'/f).read_text() for f in logs]
for marker in ['PACK_STREAM_PASS cycles=40062 samples=10068 words=19487','PACK_NEGATIVE_CONTROL_PASS flip_bit','PACK_NEGATIVE_CONTROL_PASS ignore_stall']:assert marker in a
assert 'BASELINE_PASS' in b
r['clock_pin_screen']=json.loads((out/'clock-power-screen.json').read_text())
r['verification']={'scope':'Finite independent input-bit queue with backpressure, source gaps, reset and drain; integrated baseline; not cycle-equivalence or CDC signoff',
 'logs_sha256':{f:sha(root/'scratch'/f) for f in logs},
 'source_sha256':{f:sha(p/f) for f in ['sim/tb_pack_stream.sv','verification/run_pack_stream.sh','verification/pack_negative_controls.py','verification/report_pack_stage.py','evidence/experiments/pack-before-input-stage.sv']}}
r['decision']='Retain input staging as candidate. Empty-path local packing latency increases one host cycle; framing latency/boundaries and physical timing need requalification.'
r['comparison_reference']='owner-stage-comparison.json, owner-count-stage case'
(p/'evidence/pack-stage-screen.json').write_text(json.dumps(r,indent=2)+'\n')
