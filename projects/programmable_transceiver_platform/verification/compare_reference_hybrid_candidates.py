"""Summarize actual ADC tradeoffs; pending candidates never count as evidence."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';E=P/'evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths=[E/'reference-hybrid-frames.json',E/'reference-hybrid-output2-frames.json'];reports=[json.loads(p.read_text()) for p in paths]
out=dict(completed=False,input_sha256={p.name:sha(p) for p in paths},cases=[],limitations=['Selected three-frame actual ADC histories only; no ENOB, noise, variation or physical integration qualification.', 'Metrics are diagnostic comparisons; no new thresholds or automatic adoption.', 'Sampled values and codes can change together; neither alone determines conversion correctness.'])
selected=[('retained',reports[0],'baseline',R/'scratch/transceiver-cdac-probe-reltol/probed'),('hybrid',reports[0],'candidate',R/'scratch/transceiver-reference-hybrid-frames'),('hybrid_output2',reports[1],'candidate',R/'scratch/transceiver-reference-hybrid-output2-frames')]
for name,report,key,root in selected:
 row=dict(name=name,completed=False);out['cases'].append(row)
 if not report['completed']:continue
 c=report['cases'][key];assert c['completed']
 for ext,h in c['artifacts_sha256'].items():assert sha(root/('frames'+ext))==h
 decisions=c['decisions'];spans=c['reference_span_windows']
 assert {(d['hold_ns'],d['bit_index'],d['rail']) for d in decisions}=={(t,b,r) for t in (70,120,170) for b in range(8) for r in ('h','l')} and len(decisions)==48
 assert {(d['hold_ns'],d['bit_index']) for d in spans}=={(t,b) for t in (70,120,170) for b in range(8)} and len(spans)==24
 row.update(completed=True,rail_metrics={rail:dict(worst_target_error_v=max(x['max_error_v'] for x in decisions if x['rail']==rail),worst_window_motion_v=max(x['motion_v'] for x in decisions if x['rail']==rail)) for rail in ('h','l')},span_range_v=[min(x['min_v'] for x in spans),max(x['max_v'] for x in spans)],worst_span_motion_v=max(x['motion_v'] for x in spans),reference_mean_power_w=c['reference_energy_j']/149.9e-9,driver_mean_power_w=c['driver_energy_j']/149.9e-9,held=c['held'],captures=c['captures'])
if all(r['completed'] for r in reports):
 assert reports[0]['cases']['baseline']==reports[1]['cases']['baseline']
 out['completed']=True
(E/'reference-hybrid-candidates.json').write_text(json.dumps(out,indent=2)+'\n')
for row in out['cases']:print(row['name'],row['completed'],row.get('rail_metrics'),row.get('reference_mean_power_w'))
