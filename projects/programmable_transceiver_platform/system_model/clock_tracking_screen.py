"""Transition-observed PI timing tracker; acquisition diagnostic, not complete CDR."""
import hashlib,json
from pathlib import Path
import numpy as np
from wired_screen import sample_channel
P=Path(__file__).resolve().parents[1]
def crossings(t,y):
    k=np.flatnonzero(y[:-1]*y[1:]<0)
    return t[k]-y[k]*(t[k+1]-t[k])/(y[k+1]-y[k])
def track(edges,nominal_ui,offset_ui,ppm,kp=.1,ki=.001,sample_until=None):
    period=nominal_ui*(1+ppm*1e-6);anchor=offset_ui*nominal_ui;rows=[];cycle_index=0
    samples=[];next_index=0;last_event=0.
    def emit(until):
        nonlocal next_index
        while True:
            when=anchor+(next_index-cycle_index+.5)*period
            if when>=until: break
            # A correction cannot schedule a sample in the past. Report omissions via indices.
            if when>=last_event: samples.append((when,next_index))
            next_index+=1
    for edge in edges:
        if sample_until is not None: emit(edge)
        cycles=max(1,round((edge-anchor)/period))
        cycle_index+=cycles
        predicted=anchor+cycles*period;error=edge-predicted
        # Hard tuning bound is a hypothetical oscillator constraint.
        period=np.clip(period+ki*error/cycles,nominal_ui*.995,nominal_ui*1.005)
        anchor=predicted+kp*error
        last_event=edge
        rows.append((error/nominal_ui,(period/nominal_ui-1)*1e6,cycle_index))
    if sample_until is not None:
        emit(sample_until)
        return np.array(rows),np.array(samples)
    return np.array(rows)
def score_cycles(edges,indices,symbols,ui):
    # Evaluation only: attribute each crossing to the most recent launched transition.
    transitions=np.flatnonzero(symbols[1:]!=symbols[:-1])+1
    j=np.searchsorted(transitions*ui,edges,side='right')-1
    valid=j>=0;truth=transitions[j[valid]];observed=indices[valid]
    delta=np.diff(observed)-np.diff(truth)
    return dict(cycle_count_disagreements=int(np.sum(delta!=0)),
        net_cycle_count_error=int(np.sum(delta)),
        unmatched_or_repeated_transitions=int(len(transitions)-len(np.unique(truth))))

def aligned_score(values, indices, symbols):
    """Evaluation-only alignment learned on indices256..1023, then frozen."""
    candidates=[]
    decisions=values>=0
    for shift in range(-3,4):
        mapped=indices+shift
        valid=(mapped>=0)&(mapped<len(symbols))
        train=valid&(indices>=256)&(indices<1024)
        assert train.any()
        errors=int(np.sum(decisions[train]!=(symbols[mapped[train]]>0)))
        candidates.append((errors,shift))
    best=min(e for e,_ in candidates)
    tied=[s for e,s in candidates if e==best]
    shift=min(tied,key=lambda s:(abs(s),s))
    mapped=indices+shift;test=(mapped>=0)&(mapped<len(symbols))&(indices>=1024)
    return dict(training_errors=best,selected_shift=shift,tied_shifts=tied,
        held_out_samples=int(test.sum()),held_out_errors=int(np.sum(decisions[test]!=(symbols[mapped[test]]>0))))

def main():
    assert np.allclose(crossings(np.array([0.,1.,2.]),np.array([-1.,1.,-1.])),[.5,1.5])
    ideal=track(np.arange(1,1001,dtype=float),1,0,0)
    assert np.array_equal(ideal[:,:2],np.zeros_like(ideal[:,:2]))
    assert np.array_equal(ideal[:,2],np.arange(1,1001))
    assert score_cycles(np.array([1.1,2.1,3.1]),np.array([1,2,4]),np.array([-1,1,-1,1]),1)['cycle_count_disagreements']==1
    _,ss=track(np.arange(1,5,dtype=float),1,0,0,sample_until=5)
    assert np.array_equal(ss[:,0],np.arange(5)+.5)
    _,prefix=track(np.array([1.,2.]),1,.2,100,sample_until=2.5)
    _,longer=track(np.array([1.,2.,3.,4.]),1,.2,100,sample_until=5)
    assert np.array_equal(prefix,longer[longer[:,0]<2.5])
    rng_control=np.random.default_rng(541);truth=2*rng_control.integers(0,2,2048)-1
    idx=np.arange(2,2046);observed=truth[idx-1].astype(float)
    clean=aligned_score(observed,idx,truth)
    assert clean['selected_shift']==-1 and clean['held_out_errors']==0
    observed[idx==1500]*=-1
    damaged=aligned_score(observed,idx,truth)
    assert damaged['selected_shift']==-1 and damaged['held_out_errors']==1
    rows=[];ui=1/2.5e9;n=8192;rng=np.random.default_rng(538)
    patterns={'random':2*rng.integers(0,2,n)-1,'alternating':2*(np.arange(n)%2)-1,
        'runs64':2*((np.arange(n)//64)%2)-1}
    for name,symbols in patterns.items():
        for ratio in [.15,.35,1]:
            for resolution in [16,32]:
                t=(np.arange(n*resolution)+.5)*ui/resolution
                y=sample_channel(symbols,t,ui,ratio/ui);edges=crossings(t,y)
                for offset in [-.3,.3]:
                    for ppm in [-100,100]:
                        result,samples=track(edges,ui,offset,ppm,sample_until=n*ui);tail=result[-256:]
                        assert np.all(np.diff(samples[:,0])>0)
                        values=sample_channel(symbols,samples[:,0],ui,ratio/ui)
                        indices=samples[:,1].astype(int)
                        valid=(indices>=0)&(indices<n)
                        errors=(values[valid]>=0)!=(symbols[indices[valid]]>0)
                        late=indices[valid]>=1024
                        rows.append(dict(pattern=name,bandwidth_ratio=ratio,resolution=resolution,
                            initial_offset_ui=offset,initial_period_ppm=ppm,observed_transitions=len(edges),
                            tail_events=len(tail),tail_rms_detector_error_ui=float(np.sqrt(np.mean(tail[:,0]**2))),
                            final_period_error_ppm=float(result[-1,1]),
                            cycle_score=score_cycles(edges,result[:,2],symbols,ui),
                            alignment_score=aligned_score(values,indices,symbols),
                            data_score=dict(samples=int(valid.sum()),errors=int(errors.sum()),
                                late_samples=int(late.sum()),late_errors=int(errors[late].sum()),
                                omitted_clock_indices=int(np.sum(np.maximum(np.diff(indices)-1,0))))))
    report=dict(status='behavioral_transition_tracking_only',cases=rows,
        sources_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),P/'system_model/wired_screen.py']},
        limitations=['Only received zero crossings enter feedback; transmitted bits are not supplied to tracker.',
        'Near-nominal frequency assumed; nearest-cycle association can slip or false-lock.',
        'Ideal timestamp detector and unlimited phase update, finite hypothetical frequency range.',
        'Finite recovered-data errors only; no BER bound, jitter/noise, detector dead zone or real oscillator.',
        'Tail detector residual is not proof of lock; runs64 has fewer than256 transitions.',
        'No transistor calibration or protocol qualification.'])
    (P/'evidence/fast-clock-tracking.json').write_text(json.dumps(report,indent=2)+'\n')
    print(len(rows),'cases completed; ideal-tracking and crossing controls passed')
if __name__=='__main__':main()
