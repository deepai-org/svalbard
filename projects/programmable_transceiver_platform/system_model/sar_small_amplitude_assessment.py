"""Apply pre-recorded loading factor to independently observed smaller input."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parents[1];R=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def assess(frames,beta):
    rows=[]
    for f in frames:
        anchor=f['steps'][0]['actual_residue_v'];steps=[]
        for s in f['steps']:
            predicted=anchor+beta*(s['bottom_plate_prediction_v']-anchor)
            actual=s['actual_residue_v']
            steps.append(dict(bit=s['bit'],actual_residue_v=actual,predicted_residue_v=predicted,
                error_v=actual-predicted,sign_disagrees=(actual<=0)!=(predicted<=0)))
        rows.append(dict(hold_ns=f['hold_ns'],steps=steps,
            maximum_error_v=max(abs(s['error_v']) for s in steps),
            sign_disagreement_bits=[s['bit'] for s in steps if s['sign_disagrees']]))
    return rows


def main():
    plan_path=P/'evidence/sar-small-amplitude-prediction.json'
    plan=json.loads(plan_path.read_text());fit=P/'evidence/sar-top-load-fit.json'
    assert sha(fit)==plan['source_fit_sha256'] and not plan['refit_allowed']
    beta=plan['beta'];assert beta==json.loads(fit.read_text())['beta']
    # An observed sign flip must remain visible; no fitting within assess.
    synthetic=[dict(hold_ns=0,steps=[dict(bit=7,actual_residue_v=.4,bottom_plate_prediction_v=.4),
        dict(bit=0,actual_residue_v=-.001,bottom_plate_prediction_v=.001)])]
    assert assess(synthetic,1)[0]['sign_disagreement_bits']==[0]
    source=P/'evidence/sar-all-bottom-plates-small.json'
    if not source.exists():
        print('Frozen assessment controls pass; independent waveform acceptance is pending.')
        return
    d=json.loads(source.read_text());assert d['completed'] and d['original_vectors_maximum_difference']==0
    assert d['checker_sha256']==sha(P/'verification/check_sar_bottom_plates.py')
    assert d['waveform_sha256']==sha(R/'scratch/transceiver-sar-bottom-plates-small/baseline.dat')
    rows=assess(d['frames'],beta)
    out=dict(beta=beta,refitted=False,frames=rows,source_sha256=sha(source),plan_sha256=sha(plan_path),
        script_sha256=sha(Path(__file__)),limitations=plan['limitations']+[
            'Signs compare preclock residues, not a new noisy comparator simulation.',
            'A small error across these three frames is not a bound for other input histories.'])
    (P/'evidence/sar-small-amplitude-assessment.json').write_text(json.dumps(out,indent=2)+'\n')
    for row in rows:print(row['hold_ns'],row['maximum_error_v'],row['sign_disagreement_bits'])

if __name__=='__main__':main()
