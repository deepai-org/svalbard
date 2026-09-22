"""Partial rail charge accounting on reproduced probes with timestep sensitivity."""
import contextlib,hashlib,io,json,runpy
from pathlib import Path
import numpy as np
from check_sar_balance_second_refinement import integrate,controls

HERE=Path(__file__).resolve().parent;P=HERE.parent;R=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
controls()
with contextlib.redirect_stdout(io.StringIO()):
    runpy.run_path(str(HERE/'check_sar_balance_second_refinement.py'),run_name='__main__')
evidence=P/'evidence/sar-balance-second-refinement.json'
e=json.loads(evidence.read_text())
assert e['completed'] and e['comparisons']['second_pair']['within_10uv_and_decisions']
prior=json.loads((P/'evidence/sar-balance-refinement.json').read_text())
assert prior['comparisons']['refined_pair']['within_10uv_and_decisions']
contract=P/'evidence/device-probe-contract.json'
assert json.loads(contract.read_text())['status']=='device_probe_conventions_verified_at_selected_DC_points'
cap=2048*(1.47e-3*25e-12+3.79e-10*20e-6)*(1+4.0604e-5*2-6.90e-8*4)

def residual(conduction,compensation,reservoir,load):
    return conduction+compensation-reservoir-load
assert abs(residual(5e-15,2e-15,3e-15,4e-15))<1e-29
assert abs(residual(5e-15,2e-15,3e-15,3e-15)-1e-15)<1e-29
results={};hashes={}
for stage,name,expected in [('2.5ps','sar-balance-refined-instrumented',prior['waveform_hashes']['fine_instrumented']),
                            ('1.25ps','sar-balance-second-instrumented',e['waveform_hashes']['instrumented'])]:
    path=R/f'scratch/transceiver-{name}/baseline.dat';hashes[stage]=sha(path);assert hashes[stage]==expected
    with path.open() as f:header=f.readline().lower().split()
    a=np.loadtxt(path,skiprows=1);t=a[:,0]
    def v(node):return a[:,header.index(node)]
    rows=[]
    for hold in (70,120,170):
        for j in range(8):
            for window,start,end in [('preclock',.3,.5),('switching',2.5,3.6)]:
                lo,hi=(hold+5*j+np.array([start,end]))*1e-9
                grid=np.r_[lo,t[(t>lo)&(t<hi)],hi]
                for rail,node,sense in [('xhigh','vh','h'),('xlow','vl','l')]:
                    def dev(n,par):return v(f'@m.xref.{rail}.{n}.m0[{par}]')
                    for device in ('xout','xload'):
                        assert np.all(np.interp(grid,t,dev(device,'vds'))>0)
                    conduction=dev('xout','id')-dev('xload','id')
                    if rail=='xlow':conduction=-conduction
                    compensation=(v(f'v(xref.{rail}.x)')-v(f'v(xref.{rail}.z)'))/25
                    voltage=np.interp([lo,hi],t,v('v('+node+')'))
                    qc=integrate(t,conduction,lo,hi);qm=integrate(t,compensation,lo,hi)
                    qr=cap*(voltage[1]-voltage[0]);ql=integrate(t,v('i(vsense'+sense+')'),lo,hi)
                    rem=residual(qc,qm,qr,ql)
                    rows.append(dict(hold_ns=hold,bit=7-j,window=window,rail=rail,
                        conduction_charge_c=qc,compensation_charge_c=qm,reservoir_charge_c=float(qr),
                        cdac_outward_charge_c=ql,unaccounted_outward_charge_c=rem,
                        equivalent_unaccounted_current_a=rem/(hi-lo)))
    results[stage]=rows
for old,new in zip(results['2.5ps'],results['1.25ps']):
    assert all(old[k]==new[k] for k in ('hold_ns','bit','window','rail'))
    new['residual_timestep_change_c']=new['unaccounted_outward_charge_c']-old['unaccounted_outward_charge_c']
report=dict(reservoir_capacitance_f=cap,results=results,waveform_hashes=hashes,
    source_hashes={p.name:sha(p) for p in (Path(__file__),HERE/'check_sar_balance_second_refinement.py',evidence,contract)},
    physical_qualification=False,limitations=[
        'Partial KCL: residual includes output MOS displacement and other omitted node terms; no unique device attribution.',
        'Nominal MIM capacitance and25ohm compensation resistor follow this circuit, not measured silicon.',
        'Two-step sensitivity is not a rigorous numerical-error bound or proof of physical accuracy.',
        'Recorded currents reconstruct the observed trajectory; they do not form an autonomous predictive reference model.'])
(P/'evidence/reference-refined-balance.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
for window in ('preclock','switching'):
 for rail in ('xhigh','xlow'):
    rows=[r for r in results['1.25ps'] if r['window']==window and r['rail']==rail]
    print(window,rail,'residual current range',min(r['equivalent_unaccounted_current_a'] for r in rows),max(r['equivalent_unaccounted_current_a'] for r in rows),'max residual step change C',max(abs(r['residual_timestep_change_c']) for r in rows))
