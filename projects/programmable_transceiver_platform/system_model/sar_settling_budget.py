"""Separate observed rail-following error from the verified loading correction."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]
def read(name):return json.loads((P/'evidence'/name).read_text())
fit=read('sar-top-load-fit.json');beta=fit['beta'];rail=read('sar-physical-divergence.json');physical=read('sar-driver-physical.json')
assert rail['source_sha256']==hashlib.sha256((P/'evidence/sar-driver-physical.json').read_bytes()).hexdigest()
rows=[]
for suffix,case in (('', 'sar-driver-physical-400'),('-small','sar-driver-physical-100')):
    bottom=read('sar-all-bottom-plates'+suffix+'.json')
    assert bottom['completed'] and bottom['original_vectors_maximum_difference']==0
    original=next(c for c in physical['cases'] if c['name']==case)
    assert bottom['source_waveform_sha256']==original['waveform_sha256']
    for frame in bottom['frames']:
        rf=next(f for f in rail['results'] if f['case']==case and f['hold_ns']==frame['hold_ns'])
        anchor=frame['steps'][0]['actual_residue_v'];steps=[]
        for b,r in zip(frame['steps'],rf['steps']):
            assert b['bit']==r['bit'] and abs(b['actual_residue_v']-r['actual_residue_v'])<1e-14
            loaded_rail=anchor+beta*(r['measured_rail_residue_v']-anchor)
            loaded_bottom=anchor+beta*(b['bottom_plate_prediction_v']-anchor)
            steps.append(dict(bit=b['bit'],rail_following_effect_v=loaded_bottom-loaded_rail,
                loaded_rail_error_v=b['actual_residue_v']-loaded_rail,
                loaded_bottom_error_v=b['actual_residue_v']-loaded_bottom,
                rail_sign_disagrees=(loaded_rail<=0)!=(b['actual_residue_v']<=0)))
        rows.append(dict(case=case,hold_ns=frame['hold_ns'],steps=steps,
            maximum_rail_following_effect_v=max(abs(s['rail_following_effect_v']) for s in steps),
            maximum_loaded_rail_error_v=max(abs(s['loaded_rail_error_v']) for s in steps)))
names=['sar-top-load-fit.json','sar-physical-divergence.json','sar-driver-physical.json','sar-all-bottom-plates.json','sar-all-bottom-plates-small.json']
out=dict(beta=beta,results=rows,source_hashes={n:hashlib.sha256((P/'evidence'/n).read_bytes()).hexdigest() for n in names},
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),limitations=[
    'Observed decision instants and histories only; cannot infer worst inter-decision settling.',
    'Small signed aggregate error may hide cancellation between individual bottom plates.',
    'Measured reference trajectories are still supplied, not predicted.'])
(P/'evidence/sar-settling-budget.json').write_text(json.dumps(out,indent=2)+'\n')
for r in rows:print(r['case'],r['hold_ns'],r['maximum_rail_following_effect_v'],r['maximum_loaded_rail_error_v'],[s['bit'] for s in r['steps'] if s['rail_sign_disagrees']])
