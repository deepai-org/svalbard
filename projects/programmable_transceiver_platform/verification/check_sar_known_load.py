"""Test pre-recorded loading prediction without refitting the perturbed run."""
import hashlib,json
from pathlib import Path
import numpy as np
from check_sar_bottom_plates import read,weighted_bottom,charge_controls
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
W=R/'scratch/transceiver-sar-known-load';B=W.with_name(W.name+'-prepared');OLD=R/'scratch/transceiver-sar-bottom-plates'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
charge_controls()
r=json.loads((W/'result.json').read_text());m=json.loads((B/'manifest.json').read_text());old=json.loads((OLD/'result.json').read_text())
assert r['returncode']==0 and not r['timed_out']
assert r['sources_before']==r['sources_after']==old['sources_before']
for suffix,h in r['artifacts_sha256'].items():assert sha(W/('baseline'+suffix))==h
assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']==sha(W/'baseline.spice')
ob=OLD.with_name(OLD.name+'-prepared');assert sha(ob/'manifest.json')==m['baseline_preparation_sha256']
addition='CLOADP HP 0 60f\nCLOADN HN 0 60f\n'
assert (B/'baseline.spice').read_text().count(addition)==1
assert (B/'baseline.spice').read_text().replace(addition,'')==(ob/'baseline.spice').read_text()
fit=P/'evidence/sar-top-load-fit.json';assert sha(fit)==m['prediction_source_sha256']
beta=m['predicted_beta'];prior=json.loads(fit.read_text())['beta']
h,a=read(W)
def at(node,t):return float(np.interp(t*1e-9,a[:,0],a[:,h.index('v('+node+')')]))
def bottom(t):return weighted_bottom([at(f'xd.xp{k}.bot',t) for k in range(8)],[at(f'xd.xn{k}.bot',t) for k in range(8)])
rows=[]
for hold in (70,120,170):
    t0=hold+.5;anchor=at('hp',t0)-at('hn',t0);initial=bottom(t0);steps=[]
    for j in range(8):
        t=t0+5*j;actual=at('hp',t)-at('hn',t);movement=bottom(t)-initial
        predicted=anchor+beta*movement;uncorrected=anchor+prior*movement
        steps.append(dict(bit=7-j,actual_residue_v=actual,predicted_residue_v=predicted,
            frozen_prediction_error_v=actual-predicted,unchanged_beta_error_v=actual-uncorrected))
    rows.append(dict(hold_ns=hold,steps=steps,
        maximum_frozen_error_v=max(abs(s['frozen_prediction_error_v']) for s in steps),
        maximum_unchanged_beta_error_v=max(abs(s['unchanged_beta_error_v']) for s in steps)))
out=dict(completed=True,predicted_beta=beta,prior_beta=prior,frames=rows,
    preparation_sha256=sha(B/'manifest.json'),result_sha256=sha(W/'result.json'),checker_sha256=sha(Path(__file__)),
    waveform_sha256=sha(W/'baseline.dat'),limitations=['Uses observed bottom movements and held anchors; does not predict acquisition, references or decisions autonomously.',
      'Controlled load sensitivity supports an effective capacitance model, not unique device identification or precision qualification.'])
(P/'evidence/sar-known-load.json').write_text(json.dumps(out,indent=2)+'\n')
for row in rows:print(row['hold_ns'],row['maximum_frozen_error_v'],row['maximum_unchanged_beta_error_v'])
