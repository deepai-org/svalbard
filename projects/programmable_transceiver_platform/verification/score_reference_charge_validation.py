"""Independent-amplitude scoring with frozen coefficients and no fitting."""
import contextlib,hashlib,io,json,runpy
from pathlib import Path
import numpy as np
from check_sar_balance_second_refinement import integrate,controls
from sar_conversion_history import inspect as inspect_history,controls as history_controls
HERE=Path(__file__).resolve().parent;P=HERE.parent;R=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def predict(drain_delta,gate_delta,cds,cdg):
    return cds*drain_delta+cdg*(drain_delta-gate_delta)

def main():
    controls();history_controls()
    assert abs(predict(.2,.1,2e-12,3e-12)-7e-13)<1e-27
    assert predict(0,0,2e-12,3e-12)==0
    assert predict(-.2,-.1,2e-12,3e-12)==-predict(.2,.1,2e-12,3e-12)
    frozen_path=P/'evidence/reference-charge-validation-frozen.json'
    W=R/'scratch/transceiver-reference-charge-validation'
    B=W.with_name(W.name+'-prepared')
    if not frozen_path.exists() or not (W/'result.json').exists():
        print('Frozen prediction/integration controls pass; frozen model and terminal validation run pending.')
        return
    frozen=json.loads(frozen_path.read_text());m=json.loads((B/'manifest.json').read_text())
    assert sha(B/'manifest.json')==frozen['preparation_sha256']
    for path,key in [(P/'evidence/reference-load-charge-fit.json','constant_fit_sha256'),
                     (P/'evidence/reference-two-terminal-charge.json','two_terminal_fit_sha256'),
                     (P/'evidence/reference-bias-observation.json','bias_observation_sha256')]:
        assert sha(path)==frozen[key]
    for name,h in m['artifacts_sha256'].items():assert sha(B/name)==h
    assert sha(W/'baseline.spice')==sha(B/'baseline.spice')
    with contextlib.redirect_stdout(io.StringIO()):
        shared=runpy.run_path(str(HERE/'check_sar_balance_refinement.py'))
    h,a,result=shared['load']('reference-charge-validation')
    parent=json.loads((R/'scratch/transceiver-reference-bias-observation/result.json').read_text())
    assert result['sources_before']==parent['sources_before']==parent['sources_after']
    history=inspect_history(h,a)
    t=a[:,0]
    def v(node):return a[:,h.index(node)]
    cap=2048*(1.47e-3*25e-12+3.79e-10*20e-6)*(1+4.0604e-5*2-6.90e-8*4)
    models={r['rail']:r for r in frozen['two_terminal_models']};rows=[]
    for hold in (70,120,170):
      for j in range(8):
       for window,left,right in [('preclock',.3,.5),('switching',2.5,3.6)]:
        lo,hi=(hold+5*j+np.array([left,right]))*1e-9
        grid=np.r_[lo,t[(t>lo)&(t<hi)],hi]
        for rail,node,bias,sense in [('xhigh','vh','rbn','h'),('xlow','vl','rbp','l')]:
            dv=float(np.diff(np.interp([lo,hi],t,v('v('+node+')')))[0])
            dg=float(np.diff(np.interp([lo,hi],t,v('v('+bias+')')))[0])
            assert np.all(np.interp(grid,t,v(f'@m.xref.{rail}.xload.m0[vds]'))>0)
            terminal={dev:integrate(t,v(f'i(v.xref.{rail}.{dev})'),lo,hi) for dev in ('vgate','vdrain','vload')}
            channel=integrate(t,v(f'@m.xref.{rail}.xload.m0[id]'),lo,hi)*(1 if rail=='xhigh' else -1)
            observed=terminal['vload']-channel
            constant=frozen['constant_capacitance_f'][rail]*dv
            model=models[rail]
            two=predict(dv,dg,model['cds_f'],model['cdg_f']) if model['identifiable'] else None
            compensation=integrate(t,(v(f'v(xref.{rail}.x)')-v(f'v(xref.{rail}.z)'))/25,lo,hi)
            cdac=integrate(t,v('i(vsense'+sense+')'),lo,hi)
            kcl=compensation-cap*dv-cdac-sum(terminal.values())
            rows.append(dict(hold_ns=hold,bit=7-j,window=window,rail=rail,drain_delta_v=dv,gate_delta_v=dg,
                observed_charge_c=observed,constant_prediction_c=constant,constant_error_c=constant-observed,
                two_terminal_prediction_c=two,two_terminal_error_c=None if two is None else two-observed,
                passive_coefficient_signs=model.get('passive_coefficient_signs'),full_terminal_kcl_residual_c=kcl))
    assert len(rows)==96
    report=dict(rows=rows,conversion_history=history,conversion_history_consistent=all(r['sequence_consistent'] for r in history),history_checker_sha256=sha(HERE/'sar_conversion_history.py'),frozen_model_sha256=sha(frozen_path),waveform_sha256=sha(W/'baseline.dat'),
        result_sha256=sha(W/'result.json'),scorer_sha256=sha(Path(__file__)),integrator_sha256=sha(HERE/'check_sar_balance_second_refinement.py'),
        physical_qualification=False,limitations=['All voltages are observed inputs; these are charge-law predictions, not autonomous rail/code predictions.',
          'One new input amplitude is not full input/code/corner coverage.',
          'No charge-error budget is established; numerical errors and model errors are reported without a physical pass claim.'])
    (P/'evidence/reference-charge-validation.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    for rail in models:
        group=[r for r in rows if r['rail']==rail]
        print(rail,'maximum constant error C',max(abs(r['constant_error_c']) for r in group))

if __name__=='__main__':main()
