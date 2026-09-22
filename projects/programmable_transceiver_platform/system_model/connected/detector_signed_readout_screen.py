"""Check whether signed ADC noise is distinguishable from physical overrange.

Uses existing frontend/quantizer independently of slow RF startup. This diagnoses
readout semantics, not the cause of a specific full-chip cancellation.
"""
import json
from chip_model import P,decode_iq
from receiver_impairments import Frontend
from shared_phase_loaded_tx import SharedPhaseLoadedTxChip

def main():
    c=SharedPhaseLoadedTxChip(adc_latency_s=30e-9)
    c.bits=12
    front=Frontend(noise_rms=.001,seed=839)
    negative=0;n=10000;minimum=0.
    for _ in range(n):
        measured=decode_iq(c.quantize_adc(front.sample(0j)),12).real
        negative+=int(measured<0);minimum=min(minimum,measured)
    assert negative>0 and c.adc_diagnostics['clipped_samples']==0
    report=dict(status='passed',samples=n,negative_zero_input_readings=negative,
        minimum_reading=minimum,clipped_samples=c.adc_diagnostics['clipped_samples'],
        implication='Negative decoded values can arise from in-range signed ADC noise; they do not establish detector saturation.',
        limitations=['Local frontend/quantizer only; does not identify the pending integrated cancellation reason.',
        'Exploratory noise magnitude, not measured GF180 performance.'])
    (P/'evidence/connected-detector-signed-readout.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report)

if __name__=='__main__':main()
