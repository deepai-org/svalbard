"""Inspect saved amplifier state at matched observed SAR trial codes."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1];R=P.parents[1]
source=P/'evidence/sar-physical-divergence.json';d=json.loads(source.read_text())
physical=json.loads((P/'evidence/sar-driver-physical.json').read_text());rows=[]
for case in physical['cases']:
    path=R/'scratch'/('transceiver-'+case['name'])/'baseline.dat'
    assert hashlib.sha256(path.read_bytes()).hexdigest()==case['waveform_sha256']
    with path.open() as f:h=f.readline().lower().split()
    a=np.loadtxt(path,skiprows=1)
    def at(n,t):return float(np.interp(t*1e-9,a[:,0],a[:,h.index('v('+n+')')]))
    for frame in [r for r in d['results'] if r['case']==case['name']]:
        for j,s in enumerate(frame['steps']):
            t=frame['hold_ns']+.5+5*j
            for rail,node,internal in [('high','vh','xref.xhigh.x'),('low','vl','xref.xlow.x')]:
                rows.append(dict(case=case['name'],hold_ns=frame['hold_ns'],bit=s['bit'],trial=s['actual_trial'],rail=rail,
                    output_v=at(node,t),internal_x_v=at(internal,t),slope_v_per_ns=(at(node,t)-at(node,t-.2))/.2))
pairs=[]
for i,a in enumerate(rows):
    for b in rows[i+1:]:
        if (a['rail'],a['bit'],a['trial'])!=(b['rail'],b['bit'],b['trial']):continue
        if abs(a['output_v']-b['output_v'])>.001:continue
        pairs.append(dict(first=a,second=b,output_difference_v=abs(a['output_v']-b['output_v']),
            internal_difference_v=abs(a['internal_x_v']-b['internal_x_v']),slope_difference_v_per_ns=abs(a['slope_v_per_ns']-b['slope_v_per_ns'])))
pairs.sort(key=lambda x:x['internal_difference_v'],reverse=True)
out=dict(waveform_hashes={c['name']:c['waveform_sha256'] for c in physical['cases']},observations=rows,matched_pairs=pairs[:10],source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),limitations=[
      'Matched output within1mV and same bit/trial do not match complete switching/load history.',
      'Internal X is observed; compensation Z, other MOS charge states and load currents are not reconstructed.',
      'Diagnostic state evidence, not a fitted dynamical reference model.'])
(P/'evidence/reference-state-observability.json').write_text(json.dumps(out,indent=2)+'\n')
for p in pairs[:3]:print(p['first']['rail'],p['first']['bit'],p['output_difference_v'],p['internal_difference_v'],p['slope_difference_v_per_ns'])
