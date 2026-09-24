from timing_log import domain_group_slacks
import hashlib,json,re,sys
from pathlib import Path
out=Path(sys.argv[1]);project=Path(__file__).resolve().parents[1];cases=[]
for estimate in (0,1):
 p=out/f'timing-rc{estimate}.log';text=p.read_text()
 assert 'CONSTRAINT_AUDIT_END' in text and not re.search(r'\[(?:ERROR)|^Error:',text,re.M),'incomplete/error run'
 domains=domain_group_slacks(text)
 assert len(domains)==8
 electrical=text.split('ELECTRICAL_AUDIT_BEGIN')[1].split('ELECTRICAL_AUDIT_END')[0]
 cases.append({'estimated_signal_parasitics':bool(estimate),'worst_slacks_ns':domains,'electrical_violation_rows':electrical.count('(VIOLATED)'),'log_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
r={'scope':'High-rate nominal placed timing with ideal clocks; no routed or extracted timing qualification','cases':cases,
 'database_sha256':hashlib.sha256((out/'digital.odb').read_bytes()).hexdigest(),
 'rc_assumption':'OpenROAD placement estimate using nominal technology LEF Metal3 for all signal nets; not actual layer assignment or coupled extraction',
 'source_sha256':{f:hashlib.sha256((project/'verification'/f).read_bytes()).hexdigest() for f in ['placed_timing_screen.tcl','run_placed_timing.sh','report_placed_timing.py','timing_log.py']},
 'limitations':['Ideal clocks; no CTS, propagated skew/jitter or reset distribution repair.','No routed geometry, coupling, vias or qualified RC corners; selected Metal3 estimate is not a proven lower/upper bound.','No external IO timing closure; inherited interface warnings remain.','Electrical violations can cause library extrapolation; negative slacks are diagnostic, not precise achievable-frequency limits.']}
(out/'placed-timing-screen.json').write_text(json.dumps(r,indent=2)+'\n')
for c in cases:print(c['estimated_signal_parasitics'],c['worst_slacks_ns']['host_tx_clk'],c['worst_slacks_ns']['host_rx_clk'],c['electrical_violation_rows'])
