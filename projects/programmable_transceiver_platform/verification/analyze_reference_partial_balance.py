"""Integrated partial reference-node balance; residual is not identified CDAC current."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=P/'evidence/sar-reference-devices.json';d=json.loads(e.read_text());assert d['completed'] and d['reproduction_pass']
p=R/'scratch/transceiver-sar-reference-devices/baseline.dat';assert sha(p)==d['waveform_sha256']
contract=P/'evidence/device-probe-contract.json';assert json.loads(contract.read_text())['status']=='device_probe_conventions_verified_at_selected_DC_points'
with p.open() as f:h=f.readline().lower().split()
a=np.loadtxt(p,skiprows=1);t=a[:,0]
# Nominal active MIM geometry/corner at 27C, 2048 units per rail.
cap=2048*(1.47e-3*25e-12+3.79e-10*20e-6)*(1+4.0604e-5*2-6.90e-8*4)
rows=[]
for hold in (70,120,170):
    for j in range(8):
        end=(hold+.5+5*j)*1e-9;start=end-.2e-9
        grid=np.r_[start,t[(t>start)&(t<end)],end]
        def v(name):return np.interp(grid,t,a[:,h.index(name)])
        for rail,node in [('xhigh','vh'),('xlow','vl')]:
            def dev(n,par):return v(f'@m.xref.{rail}.{n}.m0[{par}]')
            assert np.all(dev('xout','vds')>0) and np.all(dev('xload','vds')>0)
            conduction=dev('xout','id')-dev('xload','id')
            if rail=='xlow':conduction=-conduction
            compensation=(v(f'v(xref.{rail}.x)')-v(f'v(xref.{rail}.z)'))/25
            voltage=v(f'v({node})')
            qc=float(np.trapezoid(conduction,grid));qm=float(np.trapezoid(compensation,grid));qr=float(cap*(voltage[-1]-voltage[0]))
            rows.append(dict(hold_ns=hold,bit=7-j,rail=rail,window_ns=.2,
                conduction_charge_c=qc,compensation_charge_c=qm,reservoir_charge_change_c=qr,
                unaccounted_outward_charge_c=qc+qm-qr,
                equivalent_unaccounted_current_a=(qc+qm-qr)/(end-start)))
out=dict(reservoir_capacitance_f=cap,rows=rows,waveform_sha256=sha(p),probe_contract_sha256=sha(contract),script_sha256=sha(Path(__file__)),
    limitations=['Residual includes CDAC current, output MOS displacement and all other omitted node terms.',
      'This is partial KCL, not a model or measurement of a uniquely identified load.',
      'Finite windows preceding decisions omit largest switching transients.',
      'Capacitance uses nominal typical MIM parameters; source convention is specific to this qualified run.'])
(P/'evidence/reference-partial-balance.json').write_text(json.dumps(out,indent=2)+'\n')
for rail in ('xhigh','xlow'):
    group=[r for r in rows if r['rail']==rail]
    print(rail,min(r['equivalent_unaccounted_current_a'] for r in group),max(r['equivalent_unaccounted_current_a'] for r in group))
