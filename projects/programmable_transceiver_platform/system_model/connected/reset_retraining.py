"""Wired-framer reset during a partial word, with shared-transport RF continuity."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(P/'verification'))
from framing import Framer,MARKER
from recovered_clock import receive,receive_reset
from loopback_return import return_samples
from reset_status import ResetStatus,HostResetObserver,observer_controls,controls as status_controls
ap=argparse.ArgumentParser();ap.add_argument('--reset-clock',action='store_true');args=ap.parse_args()
status_controls();observer_controls()
rows=[]
for mode,rate,host_rate,width,fs in [(0,1.25e9,250e6,24,40e6),(1,2.5e9,312.5e6,16,20e6)]:
    rng=np.random.default_rng(668)
    training=rng.integers(0,2,1024).tolist()
    before=[0x12a,0x2b5,0x317,0x3ff]
    after=[((i*713)^(i>>3)^0x155)&1023 for i in range(256)]
    bits=lambda words:[(w>>k)&1 for w in words for k in range(10)]
    stream=training+list(MARKER)+bits(before)[:37]+training+list(MARKER)+bits(after)
    times,indices,decoded,_=receive(2*np.array(stream)-1,rate,.3,100)
    if args.reset_clock:
        probe=Framer();count=0;cut=None
        for when,bit in zip(times,decoded):
            was_payload=probe.state=='PAYLOAD';probe.feed(int(bit))
            if was_payload:count+=1
            if count==37:
                cut=float(when)+1e-6/rate;break
        assert cut is not None
        original_times=times.copy();original_bits=decoded.copy()
        times,decoded=receive_reset(2*np.array(stream)-1,rate,.3,100,cut)
        # No future reset may change any earlier observation.
        assert np.array_equal(times[times<cut],original_times[original_times<cut])
        assert np.array_equal(decoded[times<cut],original_bits[original_times<cut])
    status=ResetStatus();host=HostResetObserver()
    host.observe(status.snapshot())
    f=Framer();payload_seen=0;reset=False;words=[];arrivals=[];discarded=None;reacquired=False
    for when,bit in zip(times,decoded):
        old=f.state
        value=f.feed(int(bit))
        if old=='PAYLOAD':payload_seen+=1
        if reset and old=='SEARCH' and f.state=='PAYLOAD':reacquired=True
        if value is not None:words.append(value);arrivals.append(float(when)*host_rate);status.accepted()
        if not reset and payload_seen==37:
            discarded=f.count
            assert discarded==7 and f.value==127
            status.reset_event(discarded)
            f.reset();reset=True
            assert f.count==0 and f.value==0
    assert reset and reacquired and words==before[:3]+after
    # Independent uninterrupted RF source spans initial training, reset and reacquisition.
    adc=[((i*7919)^0x1234)&((1<<width)-1) for i in range(250)]
    adc_ticks=np.arange(250)*host_rate/fs
    captured=[]
    result=return_samples(mode,adc,adc_ticks,width,words,arrivals,capture=captured)
    assert captured==adc
    host_status=status.snapshot()
    notice=host.observe(host_status)
    assert notice['new_reset'] and not host.fault
    boundary=notice['accepted_word_boundary']
    assert host_status['epoch']==1 and host_status['discarded_partial_bits']==7
    assert words[:boundary]==before[:3] and words[boundary:]==after
    rows.append(dict(mode=mode,clock_tracker_reset=args.reset_clock,host_snapshot=host_status,discarded_partial_payload_bits=discarded,
        complete_pre_reset_words=3,post_retraining_words=len(after),
        rf_samples_preserved=len(captured),transport=result))
report=dict(status='wired_framer_reset_with_shared_transport',cases=rows,
 source_hashes={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
 [Path(__file__),Path(__file__).with_name('framing.py'),Path(__file__).with_name('reset_status.py'),Path(__file__).with_name('recovered_clock.py'),
  Path(__file__).with_name('loopback_return.py'),P/'system_model/clock_tracking_screen.py',
  P/'system_model/wired_screen.py',P/'verification/stream_codec.py',P/'verification/transport_model.py']},
 limitations=['Reset trigger is a testbench request after37 received payload bits, not automatic fault detection.',
 'Channel state persists; CDR state resets only in --reset-clock mode. This is not analog oscillator/pad reset.',
 'Complete accepted words drain unchanged; only the incomplete seven-bit word is discarded.',
 'RF continuity tests sample payloads and shared queues, not RF analog reset/supply coupling.',
 'Host snapshot is an abstract coherent sideband API; SPI register allocation, CDC and RTL are not implemented.'])
(P/('evidence/connected-clock-reset-retraining.json' if args.reset_clock else 'evidence/connected-reset-retraining.json')).write_text(json.dumps(report,indent=2)+'\n')
for r in rows:print(r)
