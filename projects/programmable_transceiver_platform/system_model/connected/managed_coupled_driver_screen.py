"""Short startup wiring check through actual inherited managed advancement."""
import json
from chip_model import P
from managed_coupled_driver import ManagedCoupledDriverChip

def main():
    c=ManagedCoupledDriverChip(adc_latency_s=30e-9,tx_relative_gain=True)
    assert c.loaded_tx.detector is c.tx_detector is c.tx_cal.detector
    assert c.tx_detector.sample.__self__ is c
    c.advance(100e-9)
    d=c.loaded_tx.driver
    assert c.time==c.tx.time==d.time==d.network.time==c.tx_detector.time
    assert c.phase_steps>0 and 2.5<d.rail_v<3.3
    assert c.tx_detector.value>0 and c.tx_detector.readout_value>0
    assert c.tx_adc_samples==0 and not c.tx_cal.valid
    report=dict(status='passed',time_s=c.time,phase_substeps=c.phase_steps,
        local_driver_rail_v=d.rail_v,detector_power=c.tx_detector.value,readout=c.tx_detector.readout_value,
        limitations=['100ns startup wiring only; no RF lock, calibration, payload or quality claim.',
            'Inherited autonomous LO drives network; driver rail has no return coupling to PLL/reference yet.',
            'Implicit solve at every phase segment may be too slow for complete traffic; optimize only with equivalence checks.'])
    (P/'evidence/connected-managed-coupled-driver.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
