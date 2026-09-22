"""Compare intact short SAR reservoir experiment; never automatically adopt."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-sar-reservoir-double';B=R/'scratch/transceiver-sar-reservoir-double-prepared'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
m=json.loads((B/'manifest.json').read_text());e=P/'evidence/sar-command-baseline.json';base=json.loads(e.read_text())
assert base['completed'] and base['reproduction_pass'] and sha(e)==m['baseline_evidence_sha256']
assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
original=(R/'scratch/transceiver-sar-command-replay-prepared/baseline.spice').read_text()
extra='XHR_EXTRA VH 0 pt_ref_reservoir_2048\nXLR_EXTRA VL 0 pt_ref_reservoir_2048\n'
assert (B/'baseline.spice').read_text().replace(extra,'')==original
out=dict(completed=False,status='pending',adopted=False,preparation_sha256=sha(B/'manifest.json'),added_mim_plate_area_mm2=4096*25e-6,limitations=m['limitations']+['Plate area excludes spacing, routing and guard structures.'])
def measure(p):
 with p.open() as f:h=f.readline().lower().split()
 a=np.loadtxt(p,skiprows=1);t=a[:,0];assert a.shape[1]==len(h);assert np.isfinite(a).all() and np.all(np.diff(t)>0) and t[-1]>=80e-9-1e-20
 def v(n):return a[:,h.index('v('+n+')')]
 mask=(t>=70e-9)&(t<=79e-9);span=v('vh')-v('vl')
 tt=t[mask];power=-3.3*a[mask,h.index('i(vrefsup)')]
 return dict(reference_supply_mean_power_w=float(np.trapezoid(power,tt)/(tt[-1]-tt[0])),clock_onsets=[dict(time_ns=ns,span_v=float(np.interp(ns*1e-9,t,span)),residue_v=float(np.interp(ns*1e-9,t,v('hp')-v('hn')))) for ns in (70.5,75.5)],max_high_error_v=float(np.max(abs(v('vh')[mask]-2.15))),max_low_error_v=float(np.max(abs(v('vl')[mask]-1.15))),max_span_error_v=float(np.max(abs(span[mask]-1))),decisions=[dict(time_ns=ns,span_v=float(np.interp(ns*1e-9,t,span)),residue_v=float(np.interp(ns*1e-9,t,v('hp')-v('hn'))),comparator_v=float(np.interp(ns*1e-9,t,v('qp')-v('qn')))) for ns in (72.4,77.4)])
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after']
 assert sha(W/'baseline.spice')==sha(B/'baseline.spice')
 for ext,digest in r['artifacts_sha256'].items():assert sha(W/('baseline'+ext))==digest
 errors=[l for l in (W/'baseline.log').read_text().splitlines() if any(k in l.lower() for k in ('warning','error','aborted','timestep too small'))]
 out.update(status='terminal',returncode=r['returncode'],timed_out=r['timed_out'],errors=errors,result_sha256=sha(W/'result.json'))
 if r['returncode']==0 and not r['timed_out'] and not errors:
  donor=R/'scratch/transceiver-sar-command-baseline/baseline.dat';assert sha(donor)==base['waveform_sha256']
  out.update(completed=True,baseline=measure(donor),candidate=measure(W/'baseline.dat'))
  out['decision_output_matches_baseline']=[bool(abs(c['comparator_v'])>2.97 and abs(b['comparator_v'])>2.97 and np.sign(c['comparator_v'])==np.sign(b['comparator_v'])) for b,c in zip(out['baseline']['decisions'],out['candidate']['decisions'])]
  out['limitations'].append('Matching baseline decisions does not establish ADC accuracy; pre-clock residues and rail errors must also be evaluated.')
(P/'evidence/sar-reservoir-double.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
