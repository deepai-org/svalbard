"""Long bounded-run controls for the unchanged recovered-clock/framing adapter."""
import hashlib,json
from pathlib import Path
import numpy as np
from recovered_clock import framed_words
P=Path(__file__).resolve().parents[2]
rows=[]
for run in (5,64):
    rng=np.random.default_rng(666)
    # Random run lengths avoid relying exclusively on a periodic pattern.
    bits=[];level=0
    while len(bits)<327680:
        bits.extend([level]*int(rng.integers(1,run+1)));level^=1
    bits=np.array(bits[:327680],dtype=int)
    edges=np.r_[0,np.flatnonzero(np.diff(bits))+1,len(bits)]
    actual_run=int(np.max(np.diff(edges)))
    assert actual_run<=run
    words=[sum(int(b)<<k for k,b in enumerate(bits[i:i+10])) for i in range(0,len(bits),10)]
    for rate in (1.25e9,2.5e9):
        for phase,ppm in ((-.3,-100),(.3,100)):
            got,times,metrics=framed_words(words,rate,phase,ppm)
            exact=got==words
            rows.append(dict(rate_bps=rate,maximum_input_run_bits=actual_run,payload_bits=len(bits),
                initial_phase_ui=phase,initial_period_ppm=ppm,exact_payload=exact,
                expected_words=len(words),received_words=len(got),
                differing_words=sum(a!=b for a,b in zip(got,words))))
            print(rate,run,phase,exact,flush=True)
report=dict(status='bounded_transition_density_sensitivity',cases=rows,
    source_hashes={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [Path(__file__),Path(__file__).with_name('recovered_clock.py'),Path(__file__).with_name('framing.py'),
         P/'system_model/clock_tracking_screen.py',P/'system_model/wired_screen.py']},
    limitations=['Artificial run-limited bits, not valid Ethernet/PCIe symbols or protocol traffic.',
      'Bounds apply to payload; the same separate training/marker is used as prior tests.',
      'No stochastic jitter, phase noise, oscillator wander or physical detector model.',
      'These adapter tests do not rerun host queues or RF traffic.',
      'Successful finite records do not prove a maximum supported run length or BER.'])
(P/'evidence/connected-transition-density.json').write_text(json.dumps(report,indent=2)+'\n')
assert all(row['exact_payload'] for row in rows), 'Bounded-run recovery failure; inspect report'
