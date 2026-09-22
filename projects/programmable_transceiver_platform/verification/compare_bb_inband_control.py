"""Compare completed matched zero/tone fit magnitudes; no noise interpretation."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';E=P/'evidence/bb-inband.json';W=R/'scratch/transceiver-bb-inband'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
a=json.loads(E.read_text());assert a['completed']
cases={c['name']:c for c in a['cases']};assert set(cases)=={'tone','zero'}
for c in cases.values():
 assert c['completed']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(c['name']+ext))==h
rows=[]
for t in cases['tone']['fits']:
 z=next(x for x in cases['zero']['fits'] if x['window_ns']==t['window_ns'] and x['harmonic_order']==t['harmonic_order'])
 rows.append(dict(window_ns=t['window_ns'],harmonic_order=t['harmonic_order'],**{
  ch:dict(tone_peak_v=t[ch+'_peak_v'],zero_fitted_peak_v=z[ch+'_peak_v'],zero_over_tone=z[ch+'_peak_v']/t[ch+'_peak_v']) for ch in ('i','q')}))
window_change={}
for ch in ('i','q'):
 f=[x for x in cases['tone']['fits'] if x['harmonic_order']==8];assert len(f)==2
 window_change[ch]=dict(relative_amplitude_change=f[1][ch+'_peak_v']/f[0][ch+'_peak_v']-1)
out=dict(completed=True,analysis_sha256=sha(E),comparisons=rows,tone_late_window_change=window_change,
 conclusion='Selected late fitted IF component is strongly stimulus-dependent with small window/order sensitivity in this fixture.',
 limitations=['No stochastic device noise in these deterministic histories; tiny no-tone fit is not a receiver noise floor.',
 'Per-case measured LO frequencies differ; scalar amplitudes are compared without subtracting time histories or phasors.',
 'Two late windows and one amplitude do not establish broadband response, compression, sensitivity, startup or ADC performance.'])
(P/'evidence/bb-inband-control.json').write_text(json.dumps(out,indent=2)+'\n');print(rows[-1],window_change)
