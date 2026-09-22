"""Power monitor precision and calibration sensitivity on held-out chip traces."""
import json,hashlib
import numpy as np
from chip_model import P
from tx_output_stage import output_envelope
from tx_iq_calibration import probes,fit,correct
from rf_quality_screen import quality

def main():
    probe=probes();unity=np.ones(len(probe),complex)
    params=dict(gain_imbalance_db=.5,phase_error_deg=5.,lo_feedthrough=.01+.005j)
    p=abs(output_envelope(probe,unity,**params))**2
    cal=fit(probe,p,20)
    test=.2*np.exp(1j*np.arange(300)*.17)
    y=output_envelope(correct(test,cal),np.ones(len(test),complex),**params)
    assert quality(list(test),list(y))['corrected_relative_rms']<3e-6
    rejected=0
    for probes_,power in [(np.ones(9),p),(probe,-p),(probe,np.ones(9))]:
        try:fit(probes_,power)
        except ValueError:rejected+=1
    assert rejected==3
    rows=[]
    for mode in (0,1):
        path=P/'evidence'/f'connected-reconstructed-duplex-quality-mode{mode}-traces.npz'
        d=np.load(path);z=d['actual_baseband'];r=d['actual_rotation']
        rms=float(np.sqrt(np.mean(abs(z)**2)));peak=float(max(abs(z)))
        params=dict(gain_imbalance_db=.25,phase_error_deg=2.,lo_feedthrough=rms*.01,cubic=.03/peak**2)
        # Calibration probes are independent of the waveform and its validation partition.
        truth=abs(output_envelope(probe,unity,**params))**2
        uncorrected=quality(list(d['ideal_tx']),list(output_envelope(z,r,**params)))
        cases=[]
        for bits in (8,10,12):
          for error in (0.,.001,.005,.02,.05,.1):
           for seed in range(4):
            rng=np.random.default_rng(seed)
            # Signed bounded power-observer error relative to maximum probe power;
            # clamp/quantize models a unipolar ADC with 25% full-scale headroom.
            fullscale=1.25*float(max(truth));step=fullscale/(2**bits-1)
            measured=np.clip(np.rint((truth+rng.uniform(-error,error,len(truth))*max(truth))/step)*step,0,fullscale)
            cal=fit(probe,measured,12)
            corrected=correct(z,cal)
            y=output_envelope(corrected,r,**params)
            q=quality(list(d['ideal_tx']),list(y))
            cases.append(dict(adc_bits=bits,relative_power_error_bound=error,seed=seed,calibration=cal,
                peak_corrected_component=float(max(max(abs(corrected.real)),max(abs(corrected.imag)))),quality=q))
        rows.append(dict(mode=mode,trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),uncorrected=uncorrected,cases=cases))
    report=dict(status='passed',scope='Analytical controls and sensitivity execution pass, individual quality cases may fail.',cases=rows,
        limitations=['Independent finite probes with assumed square-law power detector; not existing RX offset calibration.',
        'Correction applied at continuous baseband immediately before modulator, not a qualified DAC-domain actuator.',
        'No detector offset/nonlinearity, monitor supply coupling, calibration timing or resource ownership modeled.',
        'Static calibration does not correct oscillator noise; no transistor or protocol qualification.'])
    (P/'evidence/connected-tx-iq-calibration.json').write_text(json.dumps(report,indent=2,default=lambda v:v.item())+'\n')
    for row in rows:
      print('mode',row['mode'],'uncorrected',row['uncorrected']['corrected_relative_rms'])
      for e in (0.,.001,.005,.02,.05,.1):
        q=[v['quality']['corrected_relative_rms'] for v in row['cases'] if v['relative_power_error_bound']==e]
        print(e,min(q),max(q))
if __name__=='__main__':main()
