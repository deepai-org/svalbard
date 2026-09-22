"""Qualify observation-only repeat before reconstructing capacitor movement."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
W=R/'scratch/transceiver-sar-bottom-plates';B=W.with_name(W.name+'-prepared')
OLD=R/'scratch/transceiver-sar-driver-physical-400';OB=OLD.with_name(OLD.name+'-prepared')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(w):
    with (w/'baseline.dat').open() as f:header=f.readline().lower().split()
    a=np.loadtxt(w/'baseline.dat',skiprows=1)
    assert a.shape[1]==len(header) and np.isfinite(a).all()
    assert np.all(np.diff(a[:,0])>0) and abs(a[-1,0]-209.9e-9)<1e-15
    return header,a

def weighted_bottom(p,n):
    assert len(p)==len(n)==8
    return sum(2**k*(p[k]-n[k]) for k in range(8))/256


def charge_controls():
    # Independently conserve charge on each 255-unit array plus one dummy.
    rng=np.random.default_rng(693)
    weights=2.**np.arange(8)
    p0=rng.normal(size=8);n0=rng.normal(size=8);dummy0=.3
    hp0=1.8;hn0=1.4
    qp=np.sum(weights*(hp0-p0))+(hp0-dummy0)
    qn=np.sum(weights*(hn0-n0))+(hn0-dummy0)
    for _ in range(20):
        p=rng.normal(size=8);n=rng.normal(size=8);dummy=rng.normal()
        hp=(qp+np.dot(weights,p)+dummy)/256
        hn=(qn+np.dot(weights,n)+dummy)/256
        prediction=hp0-hn0+weighted_bottom(p,n)-weighted_bottom(p0,n0)
        assert abs(hp-hn-prediction)<1e-14
        # Common dummy motion cancels, whereas differential top charge does not.
        injected=0.002
        hp_injected=(qp+256*injected+np.dot(weights,p)+dummy)/256
        assert abs(hp_injected-hn-prediction-injected)<1e-14
    for k in range(8):
        p=np.zeros(8);p[k]=1
        assert weighted_bottom(p,np.zeros(8))==2**k/256


def main():
    global W,B,OLD,OB
    ap=argparse.ArgumentParser();ap.add_argument('--small',action='store_true');args=ap.parse_args()
    if args.small:
        W=R/'scratch/transceiver-sar-bottom-plates-small';B=W.with_name(W.name+'-prepared')
        OLD=R/'scratch/transceiver-sar-driver-physical-100';OB=OLD.with_name(OLD.name+'-prepared')
    charge_controls()
    if not (W/'result.json').exists():
        print('No terminal result yet; no waveform scoring performed.')
        return
    result=json.loads((W/'result.json').read_text())
    assert result['returncode']==0 and not result['timed_out']
    assert result['sources_before']==result['sources_after']
    original_result=json.loads((OLD/'result.json').read_text())
    assert result['sources_before']==original_result['sources_before']
    for suffix,h in result['artifacts_sha256'].items():assert sha(W/('baseline'+suffix))==h
    manifest=json.loads((B/'manifest.json').read_text())
    assert sha(OB/'manifest.json')==manifest['baseline_preparation_sha256']
    assert sha(B/'baseline.spice')==manifest['artifacts_sha256']['baseline.spice']
    assert (W/'baseline.spice').read_bytes()==(B/'baseline.spice').read_bytes()
    extra=''.join(f' v(xd.x{side}{bit}.bot)' for bit in range(7) for side in ('p','n'))
    assert (B/'baseline.spice').read_text().replace(extra,'')==(OB/'baseline.spice').read_text()
    assert sha(OLD/'baseline.dat')==original_result['artifacts_sha256']['.dat']
    h,a=read(W);oh,oa=read(OLD)
    assert np.array_equal(a[:,0],oa[:,0])
    # Observation-only changes should reproduce every originally saved value.
    maximum_difference=float(np.max(abs(a[:,[h.index(n) for n in oh]]-oa)))
    assert maximum_difference==0, maximum_difference
    def at(node,t):return float(np.interp(t*1e-9,a[:,0],a[:,h.index('v('+node+')')]))
    def bottom(t):return weighted_bottom([at(f'xd.xp{k}.bot',t) for k in range(8)],
                                          [at(f'xd.xn{k}.bot',t) for k in range(8)])
    rows=[]
    for hold in (70,120,170):
        anchor_t=hold+.5;anchor=at('hp',anchor_t)-at('hn',anchor_t);initial=bottom(anchor_t)
        steps=[]
        for j in range(8):
            t=anchor_t+5*j;actual=at('hp',t)-at('hn',t)
            predicted=anchor+bottom(t)-initial
            steps.append(dict(bit=7-j,actual_residue_v=actual,bottom_plate_prediction_v=predicted,
                remaining_residue_v=actual-predicted))
        rows.append(dict(hold_ns=hold,steps=steps))
    report=dict(completed=True,original_vectors_maximum_difference=maximum_difference,
        waveform_sha256=sha(W/'baseline.dat'),source_waveform_sha256=sha(OLD/'baseline.dat'),
        checker_sha256=sha(Path(__file__)),frames=rows,
        limitations=['Equal linear unit-capacitance reconstruction; active MIM model is voltage-linear, but top-node MOS charge/leakage are excluded.',
                     'Observed trajectory only, not a prediction for changed inputs or decisions.'])
    (P/('evidence/sar-all-bottom-plates-small.json' if args.small else 'evidence/sar-all-bottom-plates.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
