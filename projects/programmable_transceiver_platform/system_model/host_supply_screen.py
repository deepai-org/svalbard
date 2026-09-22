"""Frame activity -> binned current -> shared supply -> RF sensitivity."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from fast_screen import run
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'verification'))
from stream_codec import slots
c=json.loads((P/'spec/contract.json').read_text());cases=[]
for index,mode in enumerate(c['modes']):
    iq=next(s for s in mode['sources'] if s['id']=='iq');fs=iq['rate_bps']/iq['sample_bits'];bits=iq['sample_bits']//2
    assert bits*2*fs==iq['rate_bps']
    profile=c['transport']['profiles'][mode['profile']];word_rate=profile['clock_hz']*profile['edges']
    n=4096;count=int(np.ceil(n*word_rate/fs));ticks=np.arange(count)
    bins=np.floor(ticks*fs/word_rate).astype(int);valid=bins<n
    plan=slots(index)
    # Charge per physical transfer varies with owner; full scheduled utilization.
    weight=np.array([1. if plan[k%64] in ('wire','iq') else .5 for k in ticks])[valid]
    events=np.bincount(bins[valid],weights=weight,minlength=n)
    assert np.isclose(events.sum(),weight.sum())
    for charge in [0,1e-12,10e-12]:
        for sensitivity in [-1e8,1e8]:
            result=run(256,20e6,0,0,fs=fs,bits=bits,activity_trace=events,
                supply=dict(load_a=charge*fs,pole_hz=2e6,resistance_ohm=1,
                    vco_hz_per_v=sensitivity,gain_per_v=1,reference_v_per_v=.1,correction_hz=1e6))
            if charge==0: assert result['residual_evm']==run(256,20e6,0,0,fs=fs,bits=bits)['residual_evm']
            cases.append(dict(mode=mode['id'],charge_per_weighted_transfer_c=charge,
                weighted_transfer_count=float(events.sum()),result=result))
report=dict(status='hypothetical_coupling_not_coexistence_qualification',cases=cases,
    source_hashes={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
    [Path(__file__),P/'system_model/fast_screen.py',P/'spec/contract.json',P/'verification/stream_codec.py',P/'verification/transport_model.py']},
    limitations=['Full scheduled utilization proxy, not actual data transitions or queue-driven traffic.',
    'Charge per transfer and control-word weighting are hypothetical.',
    'Charge-preserving binning loses sub-sample edges; cannot predict GHz supply spurs.',
    'One direction only; converter width is the contract target, not achieved circuit resolution.',
    'No physical supply-network or PLL fit; no protocol qualification.'])
(P/'evidence/fast-host-supply.json').write_text(json.dumps(report,indent=2)+'\n')
print(len(cases),'coupled cases; charge conservation and zero-load controls pass')
