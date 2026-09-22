"""Frozen chip trace controls for coherent TX verification identifiability.

Observation transforms are diagnostic counterfactuals, not a physical RF tap.
No fitting uses validation samples. The receiver-inverse case deliberately
constructs an indistinguishable faulty cascade to demonstrate nonidentifiability.
"""
import hashlib,json
import numpy as np
from chip_model import P
from rf_quality_screen import quality

def q(x,y):return quality(list(x),list(y))

def main():
    rows=[]
    for mode in (0,1):
        path=P/'evidence'/f'connected-reconstructed-duplex-quality-mode{mode}-traces.npz'
        d=np.load(path);z=d['actual_baseband'];r=d['actual_rotation'];ref=d['ideal_tx'];b=d['ideal_baseband']
        external=q(ref,z*r);shared=q(b,z*r*r.conjugate())
        assert np.max(abs(z*r*r.conjugate()-z))<1e-14
        # Added common LO error is visible externally and cancels exactly in local loopback.
        perturb=np.exp(1j*.3*np.sin(2*np.pi*1.7e6*d['time_s']))
        perturbed=q(ref,z*r*perturb)
        hidden=q(b,z*r*perturb*(r*perturb).conjugate())
        assert not perturbed['screen_pass']
        assert abs(hidden['corrected_relative_rms']-shared['corrected_relative_rms'])<1e-12
        # Coherent observations catch power-only blind spots if the receiver is ideal.
        conjugation=q(b,z.conjugate())
        ampm=q(b,z*np.exp(1j*5*abs(z)**2))
        assert not conjugation['screen_pass'] and not ampm['screen_pass']
        # Two distinct TX/RX pairs with exactly the same observable cascade.
        M=np.array([[1.2,.15],[0.,.8]])
        v=np.stack((z.real,z.imag));bad=M@v;recovered=np.linalg.solve(M,bad)
        bad_tx=bad[0]+1j*bad[1];cascade=recovered[0]+1j*recovered[1]
        bad_external=q(b,bad_tx);false_good=q(b,cascade)
        assert not bad_external['screen_pass'] and false_good['screen_pass']
        assert np.max(abs(cascade-z))<1e-14
        rows.append(dict(mode=mode,trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            independent=external,shared_lo=shared,added_phase_independent=perturbed,added_phase_shared=hidden,
            ideal_receiver_conjugation=conjugation,ideal_receiver_ampm=ampm,
            receiver_cancellation=dict(tx_alone=bad_external,observed_cascade=false_good)))
    report=dict(status='passed',cases=rows,conclusion='Shared-LO loopback and unknown receiver response cannot independently certify the transmitter.',
        limitations=['Offline algebra on frozen traces; no additional RF path, delay, loading, ADC or resource implementation.',
        'Exact shared-LO cancellation assumes zero differential path delay; finite delay changes sensitivity, not independent identifiability.',
        'Receiver inverse is a constructed counterexample, not a prediction of actual mismatch.'])
    (P/'evidence/connected-tx-observability.json').write_text(json.dumps(report,indent=2,default=lambda v:v.item())+'\n')
    for row in rows:
        print(row['mode'],{k:round(row[k]['corrected_relative_rms']*100,4) for k in ('independent','shared_lo','added_phase_independent','added_phase_shared','ideal_receiver_conjugation','ideal_receiver_ampm')})
if __name__=='__main__':main()
