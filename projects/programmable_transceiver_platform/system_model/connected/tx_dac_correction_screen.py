"""Connected queued DAC correction, reconstruction transients and RF output."""
import json
import numpy as np
from chip_model import P
from session import Session
from rf_tx_state import RfTxState,controls
from tx_reconstruction import Reconstruction
from tx_dac_correction import DacCorrection
from tx_iq_calibration import probes,fit
from tx_output_stage import output_envelope
from rf_quality_screen import quality

def make(bits,cal=None):
    s=Session();s.configure(0);s.host_ready=True;s.ready.update(rf=True,wire=True);s.arm()
    tx=RfTxState(s);tx.set_reconstruction(Reconstruction())
    if cal is not None:tx.sample_correction=DacCorrection(cal,bits,float(tx.reconstruction.response([0])[0].real))
    return tx

def main():
    controls();rows=[]
    params=dict(gain_imbalance_db=.5,phase_error_deg=5.,lo_feedthrough=.01+.005j)
    probe=probes();cal=fit(probe,abs(output_envelope(probe,np.ones(len(probe)),**params))**2)
    for bits,rate in ((12,40e6),(8,20e6)):
        ideal=make(bits);actual=make(bits,cal);raw=make(bits)
        values=[];out=[];uncorrected=[]
        # Explicit quiet bias-settling samples, then independent multitone waveform.
        for i in range(4096):
            t=i/rate
            z=0j if i<128 else .18*np.exp(2j*np.pi*1.3e6*t)+.12*np.exp(-2j*np.pi*3.1e6*t)
            scale=1<<(bits-1);z=complex(round(z.real*scale)/scale,round(z.imag*scale)/scale)
            for tx in (ideal,actual,raw):
                assert tx.accept(z);tx.clock(t)
            at=t+.6/rate
            values.append(ideal.output_value(at));out.append(actual.output_value(at));uncorrected.append(raw.output_value(at))
        y=output_envelope(np.array(out),np.ones(len(out)),**params)
        u=output_envelope(np.array(uncorrected),np.ones(len(out)),**params)
        q=quality(values[128:],list(y[128:]));before=quality(values[128:],list(u[128:]))
        assert q['corrected_relative_rms']<.02 and q['corrected_relative_rms']<before['corrected_relative_rms']/3
        # Headroom failure leaves the queued sample and held code unchanged.
        assert actual.accept(1+1j)
        held=actual.held;consumed=actual.consumed;codes=actual.sample_correction.last_codes
        try:actual.clock(4096/rate)
        except ValueError:pass
        else:raise AssertionError('Overrange must reject both channels')
        assert actual.held==held and actual.consumed==consumed and actual.sample_correction.last_codes==codes
        state=actual.reconstruction.states.copy();time=actual.time
        actual.reset(time)
        assert np.array_equal(state,actual.reconstruction.states) and actual.held==0
        rows.append(dict(bits=bits,sample_rate_hz=rate,quality=q,uncorrected=before,
            preamble_samples=128,accounting=actual.accounting(),headroom_rejections=actual.sample_correction.rejected))
    (P/'evidence/connected-tx-dac-correction.json').write_text(json.dumps(dict(status='passed',cases=rows,
        limitations=['Local queue/filter/output composition; no autonomous clock, host supply or full-chip traffic in this screen.',
        'Static correction coefficients; no managed live calibration or finite detector yet.',
        'Matched identical I/Q reconstruction filters; filter mismatch and converter nonlinearity unqualified.',
        'Reset sets held DAC zero; RF mixer/driver must be disabled separately to suppress residual LO feedthrough.']),indent=2,default=lambda v:v.item())+'\n')
    for r in rows:print(r['bits'],r['quality']['corrected_relative_rms'],r['uncorrected']['corrected_relative_rms'])
if __name__=='__main__':main()
