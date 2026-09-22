"""Frozen one-parameter load-drain charge law; observed endpoints, not prediction."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1];R=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fit(delta,charge):
    delta=np.asarray(delta);charge=np.asarray(charge)
    assert delta.shape==charge.shape and np.dot(delta,delta)>1e-20
    return float(np.dot(delta,charge)/np.dot(delta,delta))
# Independent constant-capacitance and sign controls.
d=np.array([-.2,.1,.3]);q=2e-12*d
assert abs(fit(d,q)-2e-12)<1e-26
assert max(abs((-fit(d,q))*d-q))>1e-12
source=P/'evidence/reference-terminal-balance.json'
report=json.loads(source.read_text())
gate=P/'evidence/reference-terminal-probe.json';g=json.loads(gate.read_text())
assert g['reproduction_pass'] and sha(gate)==report['reproduction_report_sha256']
path=R/'scratch/transceiver-reference-terminal-probe/baseline.dat'
assert sha(path)==report['waveform_sha256']==g['waveform_sha256']
with path.open() as f:header=f.readline().lower().split()
a=np.loadtxt(path,skiprows=1,usecols=[0,header.index('v(vh)'),header.index('v(vl)')])
results=[]
for rail,column in [('xhigh',1),('xlow',2)]:
    rows=[]
    for original in report['rows']:
        if original['rail']!=rail:continue
        left,right=(.3,.5) if original['window']=='preclock' else (2.5,3.6)
        start,end=(original['hold_ns']+5*(7-original['bit'])+np.array([left,right]))*1e-9
        voltages=np.interp([start,end],a[:,0],a[:,column])
        rows.append(dict(hold_ns=original['hold_ns'],bit=original['bit'],window=original['window'],
            start_v=float(voltages[0]),end_v=float(voltages[1]),delta_v=float(voltages[1]-voltages[0]),
            observed_charge_c=original['beyond_channel_charge_c']['load_drain']))
    train=[r for r in rows if r['hold_ns']==70]
    capacitance=fit([r['delta_v'] for r in train],[r['observed_charge_c'] for r in train])
    # Freeze before examining the other conversions; no fitted intercept/offset.
    for row in rows:
        row['predicted_charge_c']=capacitance*row['delta_v']
        row['error_c']=row['predicted_charge_c']-row['observed_charge_c']
    summaries=[]
    for hold in (70,120,170):
        selected=[r for r in rows if r['hold_ns']==hold]
        summaries.append(dict(hold_ns=hold,training=hold==70,
            maximum_error_c=max(abs(r['error_c']) for r in selected),
            rms_error_c=float(np.sqrt(np.mean([r['error_c']**2 for r in selected]))),
            maximum_observed_charge_c=max(abs(r['observed_charge_c']) for r in selected)))
    results.append(dict(rail=rail,constant_capacitance_f=capacitance,positive_capacitance=capacitance>0,
        training_hold_ns=70,training_windows=len(train),held_out_windows=len(rows)-len(train),
        summaries=summaries,rows=rows))
    print(rail,'capacitance F',capacitance,'maximum errors fC',[(s['hold_ns'],s['maximum_error_c']*1e15) for s in summaries])
out=dict(results=results,source_report_sha256=sha(source),waveform_sha256=sha(path),script_sha256=sha(Path(__file__)),
    autonomous_prediction=False,limitations=[
        'Measured rail endpoints are inputs; this does not predict rail voltage or conversion code.',
        'Held-out windows share the same waveform run; independent stimulus validation remains required.',
        'Beyond-channel charge can include junction/wrapper terms and gate/bulk movement; a constant capacitance is only a hypothesis.',
        'No physically justified charge-error acceptance threshold is established.'])
(P/'evidence/reference-load-charge-fit.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
