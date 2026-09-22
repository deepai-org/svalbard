"""Check ideal settled charge conservation against recorded SAR trajectories."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1];R=P.parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--offset-ns',type=float,choices=[.2,.275,.35],default=.275);args=parser.parse_args()
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def bottom_difference(code,vh,vl):
    return (2*code-255)*(vh-vl)/256
def msb_adjustment(actual,ideal):
    difference=.5*(actual-ideal)
    return difference-difference[0]
assert np.allclose(msb_adjustment(np.array([1.,1.02]),np.array([1.,1.])),[0.,.01])
assert np.array_equal(msb_adjustment(np.ones(3),np.ones(3)),np.zeros(3))
# Complementary switching cancels equal rail translation; MSB step is one span.
assert bottom_difference(128,2.15,1.15)-bottom_difference(0,2.15,1.15)==1
assert np.isclose(bottom_difference(37,2.25,1.25),bottom_difference(37,2.15,1.15))
source=P/'evidence/adc-sar8-reference-reservoir-screen.json'
audit=json.loads(source.read_text());assert not audit['pending_or_incomplete_cases']
rows=[];hashes={}
for case in audit['cases']:
    path=R/'scratch/transceiver-adc-sar8-reference-reservoir'/(case['name']+'.dat')
    hashes[case['name']]=sha(path);assert hashes[case['name']]==case['artifacts_sha256']['.dat']
    with path.open() as f:header=f.readline().lower().split()
    names=['time','v(hp)','v(hn)','v(vh)','v(vl)']+[f'v(sd{i})' for i in range(8)]+['v(xd.xp7.bot)','v(xd.xn7.bot)']
    a=np.loadtxt(path,skiprows=1,usecols=[header.index(n) for n in names]);t=a[:,0]
    for frame in case['frames']:
        times=(frame['hold_ns']+args.offset_ns+5*np.arange(8))*1e-9
        v=np.column_stack([np.interp(times,t,a[:,i]) for i in range(1,len(names))])
        controls=v[:,4:12];assert np.all((controls<.33)|(controls>2.97))
        codes=(controls>1.65)@2**np.arange(8)
        measured=v[:,0]-v[:,1];vh=v[:,2];vl=v[:,3]
        weighted=bottom_difference(codes,vh,vl)
        predicted=measured[0]+weighted-weighted[0]
        # Replace only the ideal MSB differential contribution with its saved voltage.
        actual_msb=v[:,12]-v[:,13]
        ideal_msb=np.where(codes>=128,1.,-1.)*(vh-vl)
        corrected=predicted+msb_adjustment(actual_msb,ideal_msb)
        fixed=measured[0]+(codes-codes[0])*2/256
        for k in range(8):
            rows.append(dict(case=case['name'],hold_ns=frame['hold_ns'],bit=7-k,
                             code=int(codes[k]),measured_residue_v=float(measured[k]),
                             msb_bottom_following_error_v=float(actual_msb[k]-ideal_msb[k]),
                             msb_corrected_prediction_v=float(corrected[k]),
                             msb_corrected_error_v=float(corrected[k]-measured[k]),
                             measured_rail_prediction_v=float(predicted[k]),
                             nominal_span_prediction_v=float(fixed[k]),
                             measured_rail_error_v=float(predicted[k]-measured[k]),
                             nominal_span_error_v=float(fixed[k]-measured[k]),anchor=k==0))
scored=[r for r in rows if not r['anchor']]
metrics={key:dict(rms_v=float(np.sqrt(np.mean([r[key]**2 for r in scored]))),max_abs_v=max(abs(r[key]) for r in scored)) for key in ['measured_rail_error_v','nominal_span_error_v','msb_corrected_error_v']}
decisions={model:dict(sign_disagreements=sum((r[model]>=0)!=(r['measured_residue_v']>=0) for r in scored),samples=len(scored),minimum_measured_margin_v=min(abs(r['measured_residue_v']) for r in scored)) for model in ['nominal_span_prediction_v','measured_rail_prediction_v','msb_corrected_prediction_v']}
report=dict(offset_ns=args.offset_ns,decision_comparison=decisions,status='ideal_charge_model_residual_diagnostic',metrics=metrics,cases=rows,waveform_sha256=hashes,source_sha256=sha(source),script_sha256=sha(Path(__file__)),topology_sha256=sha(P/'analog/adc/cdac8_mim.spice'),limitations=['One measured residue anchor per frame removes initial acquisition error from scoring.', 'Only MSB bottom plates are observed; all lower branches still assume rail following.', 'Ideal matched capacitors omit parasitics, leakage, switch injection and comparator kickback.', 'Common-mode cancellation is ideal; real mismatch and comparator common-mode response remain absent.', 'Sign comparison is against sampled residue, not a physical comparator model or autonomous SAR run.', 'Measured rail history depends on actual code sequence; cannot reuse for changed input or autonomous SAR decisions.'])
(P/'evidence'/('fast-cdac-charge.json' if args.offset_ns==.275 else f'fast-cdac-charge-{args.offset_ns:g}ns.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(metrics=metrics,decisions=decisions),indent=2))
