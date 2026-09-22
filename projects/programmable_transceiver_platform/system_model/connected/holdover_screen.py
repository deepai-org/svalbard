"""Transition-starved link sensitivity; raw constant runs are not encoded protocols."""
import hashlib,json
from pathlib import Path
from recovered_clock import framed_words
P=Path(__file__).resolve().parents[2]
rows=[]
for length in (64,4096,32768):
    # Unique changing tail makes an insertion/deletion visible after constant data.
    words=[0]*length+[((i*713)^(i>>3)^0x2aa)&1023 for i in range(256)]
    for phase,ppm in ((-.3,-100),(.3,100)):
        try:
            got,times,metrics=framed_words(words,2.5e9,phase,ppm)
            first=next((i for i,(a,b) in enumerate(zip(got,words)) if a!=b),None)
            rows.append(dict(constant_bits=10*length,phase_ui=phase,initial_period_ppm=ppm,
                acquired=True,expected_words=len(words),received_words=len(got),
                differing_words=sum(a!=b for a,b in zip(got,words)),first_differing_word=first,
                exact_payload=got==words,clock=metrics))
        except ValueError as e:
            rows.append(dict(constant_bits=10*length,phase_ui=phase,initial_period_ppm=ppm,
                acquired=False,error=str(e),exact_payload=False))
report=dict(status='transition_starvation_sensitivity',cases=rows,
    source_hashes={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [Path(__file__),Path(__file__).with_name('recovered_clock.py'),Path(__file__).with_name('framing.py'),
         P/'system_model/clock_tracking_screen.py',P/'system_model/wired_screen.py']},
    limitations=['No noise or oscillator drift after training; not a physical holdover guarantee.',
        'Initial +/-100ppm is corrected during training, not a persistent frequency-error bound.',
        'Arbitrary raw streams may lack timing information; application encoding/run-length limits must be explicit.',
        'No transition timeout is adopted as a lock detector.'])
(P/'evidence/connected-clock-holdover.json').write_text(json.dumps(report,indent=2)+'\n')
for row in rows:print(row['constant_bits'],row['phase_ui'],row['exact_payload'],row.get('received_words'),row.get('first_differing_word'))
