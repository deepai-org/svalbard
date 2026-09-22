"""Reconstruct known series RC state from observed X/OUT, with linear forcing."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1];R=P.parents[1]

def reconstruct(t,x,out,resistance=25.,capacitance=4e-12):
    # w=V(Z)-V(OUT); dw/dt=(X-OUT-w)/(R*C).
    u=x-out;w=np.empty(len(t));w[0]=u[0] # DC operating point; no UIC.
    for k,dt in enumerate(np.diff(t)):
        a=dt/(resistance*capacitance);one_minus=-np.expm1(-a)
        w[k+1]=(1-one_minus)*w[k]+one_minus*u[k]+(u[k+1]-u[k])*(1-one_minus/a)
    return out+w,(u-w)/resistance

# Constant and ramp forcing have independent closed-form solutions.
t=np.arange(101)*1e-11;zero=np.zeros(len(t));u=np.ones(len(t))*.2
z,i=reconstruct(t,u,zero);assert np.max(abs(z-u))<1e-14 and np.max(abs(i))<1e-14
slope=1e8;u=slope*t;tau=1e-10
z,i=reconstruct(t,u,zero)
assert np.max(abs(z-slope*(t-tau*(1-np.exp(-t/tau)))))<1e-14
ap=argparse.ArgumentParser();ap.add_argument('--device-probe',action='store_true');args=ap.parse_args()
source=P/('evidence/sar-reference-devices.json' if args.device_probe else 'evidence/sar-all-bottom-plates.json');e=json.loads(source.read_text());assert e['completed']
if args.device_probe:assert e['reproduction_pass']
path=R/('scratch/transceiver-sar-reference-devices/baseline.dat' if args.device_probe else 'scratch/transceiver-sar-bottom-plates/baseline.dat');assert hashlib.sha256(path.read_bytes()).hexdigest()==e['waveform_sha256']
with path.open() as f:h=f.readline().lower().split()
a=np.loadtxt(path,skiprows=1);t=a[:,0];assert t[0]==0
rows=[];validation=[]
for rail,node,internal in [('high','vh','xref.xhigh.x'),('low','vl','xref.xlow.x')]:
    x=a[:,h.index('v('+internal+')')];out=a[:,h.index('v('+node+')')]
    z,current=reconstruct(t,x,out)
    if args.device_probe:
        actual_z=a[:,h.index('v('+internal[:-1]+'z)')]
        measured_current=(x-actual_z)/25
        times=np.array([hold+.5+5*j for hold in (70,120,170) for j in range(8)])*1e-9
        selected=(t>=70e-9)&(t<=209e-9)
        validation.append(dict(rail=rail,
            maximum_z_error_v=float(max(abs(z[selected]-actual_z[selected]))),
            maximum_decision_z_error_v=float(max(abs(np.interp(times,t,z-actual_z)))),
            maximum_decision_current_error_a=float(max(abs(np.interp(times,t,current-measured_current))))))
    for hold in (70,120,170):
        times=(hold+.5+5*np.arange(8))*1e-9
        rows.append(dict(rail=rail,hold_ns=hold,
            decision_compensation_current_a=np.interp(times,t,current).tolist(),
            decision_z_minus_x_v=np.interp(times,t,z-x).tolist()))
report=dict(direct_z_validation=validation,rows=rows,rc_ohm=25,cc_f=4e-12,time_constant_s=1e-10,
    waveform_sha256=e['waveform_sha256'],script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    limitations=['Exact linear-forcing RC update, but saved X/OUT are linearly interpolated between simulator points.',
      'Assumes initial DC equilibrium; valid for this non-UIC deck only.',
      'Direct Z comparison is provided only in device-probe mode; other runs lack that observation.',
      'Conditional branch reconstruction, not autonomous amplifier or full output KCL.'])
(P/('evidence/reference-compensation-validation.json' if args.device_probe else 'evidence/reference-compensation-reconstruction.json')).write_text(json.dumps(report,indent=2)+'\n')
for r in rows:print(r['rail'],r['hold_ns'],min(r['decision_compensation_current_a']),max(r['decision_compensation_current_a']))

if validation:print(json.dumps(validation,indent=2))
