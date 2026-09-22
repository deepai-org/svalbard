"""Readout sampling/latency/cancellation and managed detector object wiring."""
import json,math
from chip_model import P
from buffered_shared_detector import BufferedSharedDetector,BufferedSharedPhaseChip

def main():
    samples=[]
    def sample(value,time):
        samples.append((value,time));return value,False
    d=BufferedSharedDetector(sample,readout_tau_s=500e-9)
    d.advance(100e-9,[(.2+0j,0j)])
    assert 0<d.readout_value<d.value
    held=d.readout_value;d.request()
    assert samples==[(held,d.time)]
    try:d.request()
    except ValueError:pass
    else:raise AssertionError('Busy ADC request admitted')
    try:d.read()
    except ValueError:pass
    else:raise AssertionError('Early ADC result admitted')
    deadline=d.pending[0];d.advance(deadline,[(.2+0j,0j)])
    assert d.read()['power']==held and d.readout_value>held
    d.request();before=(d.value,d.readout_value);epoch=d.epoch;d.abort()
    assert d.pending is None and d.epoch==epoch+1 and before==(d.value,d.readout_value)
    try:d.read()
    except ValueError:pass
    else:raise AssertionError('Aborted conversion survived')
    c=BufferedSharedPhaseChip(adc_latency_s=30e-9,readout_tau_s=500e-9)
    assert c.tx_detector is c.loaded_tx.detector is c.tx_cal.detector
    assert c.tx_detector.sample.__self__ is c
    # Ensure the vectorization mixin did not replace the two-pole advance method.
    c.tx_detector.advance(100e-9,[(.2+0j,0j)])
    assert math.isclose(c.tx_detector.readout_value,held,rel_tol=1e-12)
    report=dict(status='passed',detector_power_at_sample=.04*(1-math.exp(-.5)),sampled_readout=held,
        checks=['finite readout sampled','busy/early rejection','sample held through latency',
            'abort retains analog states','shared detector identity','two-pole method retained'],
        limitations=['Readout and adapter boundary screen; no full-chip startup/traffic claim.',
            'One-way buffer excludes mux reverse loading, ADC kickback and physical parameter qualification.'])
    (P/'evidence/connected-buffered-shared-detector.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
