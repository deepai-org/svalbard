"""Frozen Q=Cds*dVd+Cdg*(dVd-dVg) screen, gated on exact bias observation."""
import contextlib,hashlib,io,json,runpy
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def fit(design,charge):
    design=np.asarray(design,float);charge=np.asarray(charge,float)
    scales=np.linalg.norm(design,axis=0)
    if np.any(scales==0):raise ValueError('Unexcited charge-law coefficient')
    normalized=design/scales
    coeff,_,rank,singular=np.linalg.lstsq(normalized,charge,rcond=None)
    if rank<2:raise ValueError('Charge-law coefficients not independently identifiable')
    return coeff/scales,float(singular[0]/singular[-1])

def coefficient_sensitivity(design):
    """Worst coefficient response to independently bounded charge errors.

    Gain is F/C; no actual charge uncertainty is assumed. It describes only
    linear fit sensitivity, not omitted physics or input-voltage error.
    """
    design=np.asarray(design,float)
    fit(design,np.zeros(len(design)))  # Require excited, independent columns.
    scale=np.linalg.norm(design,axis=0)
    inverse=np.linalg.pinv(design/scale)/scale[:,None]
    return np.sum(abs(inverse),axis=1),inverse

def controls():
    a=np.array([[.1,.3],[-.2,.1],[.3,-.1]])
    truth=np.array([.6e-12,.3e-12]);coeff,condition=fit(a,a@truth)
    assert np.allclose(coeff,truth,rtol=1e-12,atol=1e-26)
    gain,inverse=coefficient_sensitivity(a)
    for index in range(2):
        error=1e-18*np.sign(inverse[index])
        perturbed,_=fit(a,a@truth+error)
        assert abs(abs(perturbed[index]-truth[index])-gain[index]*1e-18)<1e-26
    # Almost parallel columns permit a good prediction but unstable parameters.
    d=np.array([.1,-.2,.3]);g=np.array([.2,.1,-.1])
    weak=np.column_stack((d,d-1e-6*g))
    weak_gain,_=coefficient_sensitivity(weak)
    assert min(weak_gain)>1000*max(gain)
    for invalid in (np.ones((3,2)),np.zeros((3,2))):
        try:fit(invalid,np.ones(3))
        except ValueError:pass
        else:raise AssertionError('Unidentifiable coefficients accepted')

def main():
    controls()
    with contextlib.redirect_stdout(io.StringIO()):
        state=runpy.run_path(str(P/'verification/check_reference_bias_observation.py'))
    if 'report' not in state or not state['report']['reproduction_pass']:
        print('Two-terminal fit/identifiability controls pass; exact bias observations pending.')
        return
    observed=state['report']
    constant_path=P/'evidence/reference-load-charge-fit.json'
    constant=json.loads(constant_path.read_text())
    balance_path=P/'evidence/reference-terminal-balance.json'
    assert sha(balance_path)==constant['source_report_sha256']
    assert observed['parent_waveform_sha256']==constant['waveform_sha256']
    results=[]
    for base in constant['results']:
        rail=base['rail'];node='rbn' if rail=='xhigh' else 'rbp'
        biases={(r['hold_ns'],r['bit'],r['window']):r for r in observed['biases'][node]['windows']}
        rows=[]
        for original in base['rows']:
            row=original.copy();bias=biases[(row['hold_ns'],row['bit'],row['window'])]
            row['gate_delta_v']=bias['delta_v']
            row['design']=[row['delta_v'],row['delta_v']-bias['delta_v']]
            rows.append(row)
        training=[r for r in rows if r['hold_ns']==70]
        try:coeff,condition=fit([r['design'] for r in training],[r['observed_charge_c'] for r in training])
        except ValueError as error:
            results.append(dict(rail=rail,identifiable=False,reason=str(error)));continue
        sensitivity,_=coefficient_sensitivity([r['design'] for r in training])
        for row in rows:
            row['two_terminal_prediction_c']=float(np.dot(coeff,row['design']))
            row['two_terminal_error_c']=row['two_terminal_prediction_c']-row['observed_charge_c']
        summaries=[]
        for hold in (70,120,170):
            group=[r for r in rows if r['hold_ns']==hold]
            summaries.append(dict(hold_ns=hold,training=hold==70,
                constant_max_error_c=max(abs(r['error_c']) for r in group),
                two_terminal_max_error_c=max(abs(r['two_terminal_error_c']) for r in group)))
        results.append(dict(rail=rail,identifiable=True,cds_f=float(coeff[0]),cdg_f=float(coeff[1]),
            passive_coefficient_signs=bool(np.all(coeff>=0)),normalized_design_condition=condition,
            coefficient_error_gain_f_per_c=sensitivity.tolist(),
            summaries=summaries,rows=rows))
    report=dict(results=results,autonomous_prediction=False,
        source_hashes={p.name:sha(p) for p in (Path(__file__),constant_path,balance_path,P/'evidence/reference-bias-observation.json')},
        limitations=['Coefficient sensitivity reports gain only; an actual per-window charge uncertainty bound is not established.',
          'Both drain and gate endpoint voltages are measured inputs, not predicted states.',
          'Training only uses first conversion; held-out windows still share its waveform run.',
          'Negative coefficients are reported, not clipped or accepted as passive capacitance.',
          'Even positive coefficients and low error do not uniquely identify physical capacitances or establish extrapolation.'])
    (P/'evidence/reference-two-terminal-charge.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    for row in results:print({k:v for k,v in row.items() if k!='rows'})

if __name__=='__main__':main()
