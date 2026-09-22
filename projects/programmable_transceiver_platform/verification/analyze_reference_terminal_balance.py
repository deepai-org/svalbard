"""Gated whole-terminal rail accounting; no channel-current double counting."""
import contextlib,hashlib,io,json,runpy
from pathlib import Path
import numpy as np
from check_sar_balance_second_refinement import integrate,controls as integral_controls
HERE=Path(__file__).resolve().parent;P=HERE.parent;R=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def balance(compensation,reservoir,cdac,gate,drain,load):
    # Compensation positive INTO rail; all three terminal probes positive OUT.
    return compensation-reservoir-cdac-gate-drain-load

def controls():
    integral_controls()
    # Gate outward1, drain outward-8, load outward2: device net supplies5.
    assert balance(2.,3.,4.,1.,-8.,2.)==0
    assert balance(-2.,-3.,-4.,-1.,8.,-2.)==0
    assert balance(2.,3.,4.,0.,-8.,2.)==1  # Omitted feedback gate is visible.
    assert balance(2.,3.,4.,1.,-8.,2.)+7==7  # Adding channel supply double-counts.


def main():
    controls()
    with contextlib.redirect_stdout(io.StringIO()):
        gate=runpy.run_path(str(HERE/'check_reference_terminal_probe.py'))
    if 'report' not in gate:
        print('Signed balance and omission controls pass; accepted terminal data pending.')
        return
    qualification=gate['report']
    if not qualification['reproduction_pass']:
        print('Terminal probe failed reproduction; charge attribution blocked.')
        return
    h,a,_=gate['candidate'];t=a[:,0]
    convention=P/'evidence/device-probe-contract.json'
    assert json.loads(convention.read_text())['status']=='device_probe_conventions_verified_at_selected_DC_points'
    cap=2048*(1.47e-3*25e-12+3.79e-10*20e-6)*(1+4.0604e-5*2-6.90e-8*4)
    def v(name):return a[:,h.index(name)]
    rows=[]
    for hold in (70,120,170):
      for j in range(8):
       for window,left,right in [('preclock',.3,.5),('switching',2.5,3.6)]:
        lo,hi=(hold+5*j+np.array([left,right]))*1e-9
        for rail,node,sense in [('xhigh','vh','h'),('xlow','vl','l')]:
            charges={device:integrate(t,v(f'i(v.xref.{rail}.{device})'),lo,hi)
                     for device in ('vgate','vdrain','vload')}
            compensation=(v(f'v(xref.{rail}.x)')-v(f'v(xref.{rail}.z)'))/25
            qm=integrate(t,compensation,lo,hi)
            voltage=np.interp([lo,hi],t,v(f'v({node})'))
            qr=float(cap*(voltage[1]-voltage[0]))
            qdac=integrate(t,v('i(vsense'+sense+')'),lo,hi)
            rem=balance(qm,qr,qdac,charges['vgate'],charges['vdrain'],charges['vload'])
            channel={}
            grid=np.r_[lo,t[(t>lo)&(t<hi)],hi]
            for device in ('xout','xload'):
                assert np.all(np.interp(grid,t,v(f'@m.xref.{rail}.{device}.m0[vds]'))>0)
                sign=-1 if (rail=='xhigh')==(device=='xout') else 1
                channel[device]=sign*integrate(t,v(f'@m.xref.{rail}.{device}.m0[id]'),lo,hi)
            remainder=dict(output_drain=charges['vdrain']-channel['xout'],
                           load_drain=charges['vload']-channel['xload'],
                           feedback_gate=charges['vgate'])
            channel_only=-sum(channel.values())+qm-qr-qdac
            assert abs(channel_only-sum(remainder.values())-rem)<1e-24
            rows.append(dict(hold_ns=hold,bit=7-j,window=window,rail=rail,
                terminal_outward_charge_c=charges,channel_outward_charge_c=channel,
                beyond_channel_charge_c=remainder,channel_only_residual_c=channel_only,
                compensation_inward_charge_c=qm,
                reservoir_charge_change_c=qr,cdac_outward_charge_c=qdac,
                residual_charge_c=rem,equivalent_residual_current_a=rem/(hi-lo)))
    report=dict(rows=rows,reservoir_capacitance_f=cap,
        waveform_sha256=qualification['waveform_sha256'],
        reproduction_report_sha256=sha(P/'evidence/reference-terminal-probe.json'),
        source_hashes={p.name:sha(p) for p in (Path(__file__),HERE/'check_sar_balance_second_refinement.py',convention)},
        physical_qualification=False,limitations=[
            'KCL closure of recorded traces is not an autonomous predictive reference model.',
            'Residual includes integration error and nominal reservoir-law approximation; no residual tolerance pass is defined.',
            'Beyond-channel differences can include displacement, junction and wrapper terms; they are not uniquely identified capacitances.',
            'Preclock and switching windows do not cover every instant of the conversion.'])
    (P/'evidence/reference-terminal-balance.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    for window in ('preclock','switching'):
        for rail in ('xhigh','xlow'):
            selected=[r for r in rows if r['window']==window and r['rail']==rail]
            print(window,rail,'maximum absolute residual C',max(abs(r['residual_charge_c']) for r in selected))

if __name__=='__main__':main()
