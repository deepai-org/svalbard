"""Integrate independently tabulated DC current along observed load trajectories."""
import contextlib, hashlib, io, json, math, runpy, subprocess, sys
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def interpolate(x,y,z,a,b):
    a,b=np.broadcast_arrays(np.asarray(a),np.asarray(b))
    if np.any((a<x[0])|(a>x[-1])|(b<y[0])|(b>y[-1])):
        raise ValueError('DC grid extrapolation forbidden')
    i=np.clip(np.searchsorted(x,a,side='right')-1,0,len(x)-2)
    j=np.clip(np.searchsorted(y,b,side='right')-1,0,len(y)-2)
    u=(a-x[i])/(x[i+1]-x[i]);v=(b-y[j])/(y[j+1]-y[j])
    return (1-u)*(1-v)*z[i,j]+u*(1-v)*z[i+1,j]+(1-u)*v*z[i,j+1]+u*v*z[i+1,j+1]

def controls():
    x=np.array([0.,1.,3.]);y=np.array([-2.,0.,4.])
    z=2+x[:,None]+3*y[None,:]+x[:,None]*y[None,:]
    a=np.array([0.,.3,1.,2.8,3.]);b=np.array([-2.,.4,0.,3.,4.])
    assert np.allclose(interpolate(x,y,z,a,b),2+a+3*b+a*b,rtol=0,atol=1e-14)
    for a,b in [(-.01,0),(3.01,0),(1,-2.01),(1,4.01)]:
        try:interpolate(x,y,z,a,b)
        except ValueError:pass
        else:raise AssertionError('Extrapolation accepted')

def main():
    controls()
    for script in ('verification/check_load_terminal_dc_grid.py','system_model/reference_ac_dc_validation.py'):
        subprocess.run([sys.executable,str(P/script)],check=True,stdout=subprocess.DEVNULL)
    names=['load-terminal-dc-grid.json','reference-ac-dc-charge-prediction.json',
           'reference-ac-dc-validation.json','reference-ac-charge-prediction.json']
    hashes={name:sha(P/'evidence'/name) for name in names}
    reports={name:json.loads((P/'evidence'/name).read_text()) for name in names}
    grid=reports[names[0]];ac=reports[names[3]]
    with contextlib.redirect_stdout(io.StringIO()):
        loader=runpy.run_path(str(P/'verification/check_sar_balance_refinement.py'))
    rows=[];waveforms={}
    for stimulus,source,ac_key,old_error in [
        ('reference-bias-observation',reports[names[1]],'predicted_charge_c','error_c'),
        ('reference-charge-validation',reports[names[2]],'ac_prediction_c','ac_dc_error_c')]:
        h,data,result=loader['load'](stimulus)
        waveforms[stimulus]=result['artifacts_sha256']['.dat']
        grid_pdk={Path(name).name:digest for name,digest in grid['source_hashes_before'].items() if name.startswith('/foss/pdks/')}
        transient_pdk={Path(name).name:digest for name,digest in result['sources_before'].items() if name.startswith('/foss/pdks/')}
        assert {'design.ngspice','sm141064.ngspice'} <= transient_pdk.keys()
        for name,digest in transient_pdk.items():assert grid_pdk[name]==digest
        time=data[:,0]
        for rail,kind,drain,gate in [('xhigh','n','vh','rbn'),('xlow','p','vl','rbp')]:
            cases=[c for c in grid['cases'] if c['type']==kind]
            x=np.array(sorted({c['drain_v'] for c in cases}));y=np.array(sorted({c['gate_v'] for c in cases}))
            table={(c['drain_v'],c['gate_v']):c['drain_minus_channel_a'] for c in cases}
            z=np.array([[table[d,g] for g in y] for d in x])
            cd,cg=[next(r for r in ac['summaries'] if r['rail']==rail)[k] for k in ('drain_derivative_f','gate_derivative_f')]
            for row in source['rows']:
                if row['rail']!=rail:continue
                left,right={'preclock':(.3,.5),'switching':(2.5,3.6)}[row['window']]
                lo,hi=(row['hold_ns']+5*(7-row['bit'])+np.array([left,right]))*1e-9
                t=np.r_[lo,time[(time>lo)&(time<hi)],hi]
                d=np.interp(t,time,data[:,h.index('v('+drain+')')])
                g=np.interp(t,time,data[:,h.index('v('+gate+')')])
                current=interpolate(x,y,z,d,g)
                charge=float(np.sum(np.diff(t)*(current[:-1]+current[1:])/2))
                # Midpoint subdivision provides a quadrature sensitivity check;
                # it does not validate the underlying DC grid interpolation.
                mid=interpolate(x,y,z,(d[:-1]+d[1:])/2,(g[:-1]+g[1:])/2)
                refined=float(np.sum(np.diff(t)*(current[:-1]+2*mid+current[1:])/4))
                predicted=cd*(d[-1]-d[0])+cg*(g[-1]-g[0])+refined
                rows.append(dict(stimulus=stimulus,rail=rail,hold_ns=row['hold_ns'],bit=row['bit'],window=row['window'],
                    observed_charge_c=row['observed_charge_c'],dc_charge_c=refined,
                    quadrature_change_c=refined-charge,predicted_charge_c=float(predicted),
                    error_c=float(predicted-row['observed_charge_c']),nominal_dc_error_c=row[old_error]))
    assert len(rows)==192
    summaries=[]
    for stimulus in waveforms:
        for rail in ('xhigh','xlow'):
            group=[r for r in rows if r['stimulus']==stimulus and r['rail']==rail]
            summaries.append(dict(stimulus=stimulus,rail=rail,
                max_error_c=max(abs(r['error_c']) for r in group),
                rms_error_c=math.sqrt(sum(r['error_c']**2 for r in group)/len(group)),
                max_nominal_dc_error_c=max(abs(r['nominal_dc_error_c']) for r in group),
                max_quadrature_change_c=max(abs(r['quadrature_change_c']) for r in group)))
    assert hashes=={name:sha(P/'evidence'/name) for name in names}
    report=dict(rows=rows,summaries=summaries,waveform_hashes=waveforms,source_hashes=hashes,
        script_sha256=sha(Path(__file__)),physical_qualification=False,limitations=[
            'Post-completion diagnostic; no transient fit, but not preregistered.',
            'Bilinear interpolation of independent DC samples needs off-grid validation.',
            'Measured trajectories remain inputs; neither rail nor bias dynamics are predicted.',
            'Nominal AC charge derivatives remain constant; no corner, noise or silicon qualification.'])
    (P/'evidence/reference-bias-current-prediction.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summaries,indent=2))

if __name__=='__main__':main()
