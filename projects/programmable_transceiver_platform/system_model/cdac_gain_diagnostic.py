"""One-parameter charge-gain diagnostic with frame-separated fitting/scoring."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1]
def fit_gain(x,y):
    assert len(x)>0 and float(x@x)>0
    return float(x@y/(x@x))
assert np.isclose(fit_gain(np.array([-2.,1.,3.]),np.array([-1.,.5,1.5])),.5)
reports=[];hashes={}
for name in ['fast-cdac-charge-0.2ns.json','fast-cdac-charge.json','fast-cdac-charge-0.35ns.json']:
    path=P/'evidence'/name;d=json.loads(path.read_text());hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    anchors={(r['case'],r['hold_ns']):r['measured_residue_v'] for r in d['cases'] if r['anchor']}
    rows=[r for r in d['cases'] if not r['anchor']]
    anchor=np.array([anchors[r['case'],r['hold_ns']] for r in rows])
    x=np.array([r['msb_corrected_prediction_v'] for r in rows])-anchor
    actual=np.array([r['measured_residue_v'] for r in rows]);y=actual-anchor
    train=np.array([r['hold_ns']==70 for r in rows]);assert train.sum()==14 and (~train).sum()==28
    gain=fit_gain(x[train],y[train]);predicted=anchor+gain*x
    test=~train
    reports.append(dict(offset_ns=d['offset_ns'],gain=gain,
                        equivalent_extra_capacitance_fraction=1/gain-1,
                        training_samples=int(train.sum()),held_out_samples=int(test.sum()),
                        held_out_rms_v=float(np.sqrt(np.mean((predicted[test]-actual[test])**2))),
                        held_out_max_abs_v=float(np.max(abs(predicted[test]-actual[test]))),
                        held_out_sign_disagreements=int(np.sum((predicted[test]>=0)!=(actual[test]>=0))),
                        held_out_uncorrected_rms_v=float(np.sqrt(np.mean((x[test]-y[test])**2)))))
report=dict(status='empirical_gain_hypothesis_not_physical_identification',sources_sha256=hashes,
            script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),results=reports,
            limitations=['Early70ns frames fit one gain; later120/170ns frames score it, excluding per-frame anchors.',
                         'All records were inspected previously; this is held-out fitting, not a blind validation dataset.',
                         'Repeated nominal inputs and one fixture do not establish transfer across codes, process or load.',
                         'Equivalent capacitance fraction assumes attenuation solely from extra top capacitance; cause is unidentified.',
                         'Recorded code/rail/MSB trajectories and a measured anchor remain necessary; not autonomous SAR prediction.'])
(P/'evidence/fast-cdac-gain-diagnostic.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(reports,indent=2))
