"""Compare standalone and combined scheduling experiments to pass 37."""
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
base=json.loads((p/'evidence/tx-stage-screen.json').read_text())
cases=[]
for name in ['owner-stage','owner-count-stage']:
 r=json.loads((root/f'scratch/transceiver-{name}-mapping/buffered/timing-screen.json').read_text())
 candidate=p/f'evidence/experiments/tx-{name}.sv'
 assert sha(candidate)==r['area_screen']['source_sha256']['rtl/pt_stream_tx.sv']
 log=root/f'scratch/transceiver-{name}-tests.log';t=log.read_text()
 for marker in ['STREAM_TX_PASS cycles=84096','BASELINE_PASS','TX_STAGE_COMPARE_PASS cycles=69824 reset_phases=128']:assert marker in t
 cases.append({'name':name,'timing_screen':r,'test_log_sha256':sha(log),'candidate_sha256':sha(candidate)})
r={'scope':'Nominal zero-wire/ideal-clock mapping experiments; not physical qualification',
 'reference_sha256':sha(p/'evidence/tx-stage-screen.json'),'cases':cases,
 'functional_scope':'Independent codec vectors with changing live counts and integrated tests, plus finite original-TX comparison under mode frozen between resets. No formal equivalence.',
 'source_sha256':{f:sha(p/f) for f in ['verification/report_owner_stage.py','verification/stream_tx_vectors.py','sim/tb_tx_stage_compare.sv','verification/run_delay_mapping.sh']},
 'decision':'Retain combined owner/count stages as next RTL candidate; no physical qualification. Standalone owner stage is comparison only.',
 'clock_pin_screens':{name:json.loads((root/f'scratch/transceiver-{name}-mapping/buffered/clock-power-screen.json').read_text()) for name in ['tx-stage','owner-count-stage']},
 'limitations':['Whole-design mapping changes affect unchanged paths.','No candidate placement, extracted timing, power or CDC closure.','Results are not frequency limits or uncertainty bounds.']}
(p/'evidence/owner-stage-comparison.json').write_text(json.dumps(r,indent=2)+'\n')
for c in cases:
 s=c['timing_screen'];print(c['name'],s['area_screen']['cell_area_um2'],s['profiles'][1]['worst_reported_slack_ns_by_domain_and_group'])
