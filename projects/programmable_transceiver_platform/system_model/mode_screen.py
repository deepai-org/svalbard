"""Common contract for RF envelope and host arithmetic; not full-chip dynamics."""
import hashlib
import json
from pathlib import Path
from fast_screen import loopback
from host_screen import budget
P=Path(__file__).resolve().parents[1]
path=P/'spec/contract.json';contract=json.loads(path.read_text());cases=[]
for mode in contract['modes']:
    iq=next(s for s in mode['sources'] if s['id']=='iq')
    assert iq['sample_bits']%2==0
    bits=iq['sample_bits']//2;fs=iq['rate_bps']/iq['sample_bits']
    assert fs*bits*2==iq['rate_bps']
    for amplitude in [.05,.4,.8]:
        rf=loopback(amplitude,0,0,3,fs=fs,bits=bits)
        transport={d:budget(contract['transport'],mode['profile'],
            {s['id']:s['rate_bps'] for s in mode['sources'] if d in s['directions']}) for d in ['d2h','h2d']}
        cases.append(dict(mode=mode['id'],rf=rf,transport=transport))
report=dict(status='common_configuration_only_not_whole_chip_verified',cases=cases,
    sources_sha256={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [path,Path(__file__),P/'system_model/fast_screen.py',P/'system_model/host_screen.py']},
    limitations=['Declared12-bit sample width is a mode target, not proof of12-bit ADC circuitry or ENOB.',
    'Envelope filter discretization needs oversampled convergence before spectral conclusions.',
    'No waveform-to-word queues or shared supply/clock dynamics yet.',
    'Contract modes remain targets; no link or Wi-Fi compliance claim.'])
(P/'evidence/fast-mode-screen.json').write_text(json.dumps(report,indent=2)+'\n')
for c in cases:print(c['mode'],c['rf']['sample_rate_hz'],c['rf']['bits_per_component'],c['rf']['amplitude_v'],round(c['rf']['residual_evm'],4))
