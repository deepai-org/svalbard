"""Transition-only clock recovery adapter for the connected behavioral platform."""
import hashlib,json,math,sys
from pathlib import Path
import numpy as np
from framing import Framer, MARKER
P=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(P/'system_model'))
from clock_tracking_screen import track
from wired_screen import sample_channel


def channel_crossings(symbols,ui,bandwidth):
    """Exact zero crossings of a held-symbol first-order channel, initially zero."""
    tau=1/(2*np.pi*bandwidth);decay=np.exp(-ui/tau);state=0.;edges=[]
    for k,symbol in enumerate(symbols):
        if state*symbol<0:
            dt=tau*np.log((symbol-state)/symbol)
            if 0<dt<ui:edges.append(k*ui+dt)
        state=symbol+(state-symbol)*decay
    return np.asarray(edges)


def receive(symbols,rate,phase_ui,period_ppm,bandwidth_ratio=1):
    ui=1/rate;edges=channel_crossings(symbols,ui,rate*bandwidth_ratio)
    # Only observed edge times and nominal oscillator settings enter feedback.
    states,samples=track(edges,ui,phase_ui,period_ppm,sample_until=len(symbols)*ui)
    values=sample_channel(symbols,samples[:,0],ui,rate*bandwidth_ratio)
    return samples[:,0],samples[:,1].astype(int),(values>0).astype(int),states


def main():
    ui=1e-9
    edges=channel_crossings(np.array([1.,-1.]),ui,1e9)
    expected=ui+np.log(2-np.exp(-2*np.pi))/(2*np.pi*1e9)
    assert len(edges)==1 and abs(edges[0]-expected)<1e-23
    assert np.array_equal(edges,channel_crossings(np.array([-1.,1.]),ui,1e9))
    rng=np.random.default_rng(649);bits=rng.integers(0,2,8192);symbols=2*bits-1
    rows=[]
    for rate in (1.25e9,2.5e9):
        for phase in (-.3,.3):
            for ppm in (-100,100):
                times,indices,decoded,states=receive(symbols,rate,phase,ppm)
                assert np.all(np.diff(times)>0)
                valid=(indices>=1024)&(indices<len(bits))
                errors=int(np.sum(decoded[valid]!=bits[indices[valid]]))
                omitted=int(np.sum(np.maximum(np.diff(indices[valid])-1,0)))
                rows.append(dict(rate_bps=rate,phase_ui=phase,period_ppm=ppm,
                    payload_bits=int(valid.sum()),payload_errors=errors,omitted_indices=omitted,
                    final_period_ppm=float(states[-1,1])))
                assert errors==0 and omitted==0
    report=dict(status='transition_tracker_adapter_verified_not_yet_connected',cases=rows,
        sources_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
          [Path(__file__),P/'system_model/clock_tracking_screen.py',P/'system_model/wired_screen.py']},
        limitations=['First1024 bits excluded as acquisition interval; no lock detector or framed preamble yet.',
          'Clock indices have initial alignment by convention; word framing remains unresolved.',
          'No transmitted bits enter feedback, but ideal zero-crossing timestamps and near-nominal oscillator are assumed.',
          'Not yet feeding host queues; recovered-time causality must be preserved when connected.',
          'No jitter/noise, physical tuning constraints or BER qualification.'])
    (P/'evidence/connected-clock-adapter.json').write_text(json.dumps(report,indent=2)+'\n')
    print(rows)
if __name__=='__main__':main()


def framed_words(words,rate,phase_ui=.3,period_ppm=100):
    """Explicit test-link training/marker; not PCIe/Ethernet protocol framing."""
    rng=np.random.default_rng(650)
    training=rng.integers(0,2,1024).tolist()
    marker=list(MARKER)
    payload=[(int(word)>>k)&1 for word in words for k in range(10)]
    transmitted=np.array(training+marker+payload)
    times,indices,decoded,states=receive(2*transmitted-1,rate,phase_ui,period_ppm)
    framer=Framer();recovered=[];completion=[];acquired=None
    for when,bit in zip(times,decoded):
        before=framer.state
        word=framer.feed(int(bit))
        if before=='SEARCH' and framer.state=='PAYLOAD':acquired=float(when)
        if word is not None:
            recovered.append(word);completion.append(when)
    if framer.state!='PAYLOAD':
        raise ValueError('receiver did not acquire framing; reset/retraining required')
    completion=np.asarray(completion)
    # Active payload t=0 follows training. This origin is testbench bookkeeping,
    # not input to recovery or marker detection.
    completion-=(len(training)+len(marker))/rate
    assert np.all(completion>=0) and np.all(np.diff(completion)>0)
    return recovered,completion,dict(training_bits=len(training),marker_bits=len(marker),
        marker_acquired_relative_payload_s=acquired-(len(training)+len(marker))/rate,
        recovered_words=len(recovered),initial_phase_ui=phase_ui,initial_period_ppm=period_ppm,
        clock='received zero-crossing PI tracker',framing='observed64-bit test marker',
        final_period_ppm=float(states[-1,1]))


def receive_reset(symbols,rate,phase_ui,period_ppm,reset_time):
    """Restart only digital timing state; channel impulse-response state persists."""
    ui=1/rate;end=len(symbols)*ui
    assert 0<reset_time<end
    edges=channel_crossings(symbols,ui,rate)
    _,before=track(edges[edges<reset_time],ui,phase_ui,period_ppm,sample_until=reset_time)
    _,after=track(edges[edges>=reset_time]-reset_time,ui,-phase_ui,-period_ppm,
                  sample_until=end-reset_time)
    times=np.r_[before[:,0],after[:,0]+reset_time]
    assert np.all(np.diff(times)>0)
    values=sample_channel(symbols,times,ui,rate)
    return times,(values>0).astype(int)
