"""Managed event alignment and causal RF pull, with zero-coupling control."""
import json
from chip_model import P
from managed_driver_feedback import ManagedDriverFeedbackChip

def run(sensitivity):
    c=ManagedDriverFeedbackChip(adc_latency_s=30e-9,driver_hz_per_v=sensitivity)
    detector=c.tx_detector;network=c.loaded_tx.network
    c.advance(100e-9)
    d=c.loaded_tx.driver
    assert c.time==c.tx.time==c.rf_pll.time==d.time==detector.time==network.time
    assert c.tx_detector is detector is c.tx_cal.detector is d.detector
    assert c.loaded_tx.network is network
    assert c.driver_feedback_steps>0 and c.tx_adc_samples==0
    phase=c.rf_pll.output_phase_cycles
    c.set_reference(False,c.time)
    assert c.rf_pll.output_phase_cycles==phase
    c.advance(150e-9)
    assert c.time==c.tx.time==c.rf_pll.time==d.time==detector.time
    assert not c.tx_cal.valid and detector.pending is None
    return c

def main():
    c=run(1e6);zero=run(0.)
    delta=c.rf_pll.output_phase_cycles-zero.rf_pll.output_phase_cycles
    assert abs(delta)>1e-4
    report=dict(status='passed',feedback_steps=c.driver_feedback_steps,phase_change_cycles=delta,
        final_rail_v=c.loaded_tx.driver.rail_v,reference_present=c.reference,
        limitations=['150ns managed startup/reference-loss alignment; not acquired lock/calibration/traffic quality.',
            'Local driver rail pulls RF PLL only; shared reference and other supply domains remain separate.',
            'Clock coupling step and driver laws require wider convergence/uncertainty validation.'])
    (P/'evidence/connected-managed-driver-feedback.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
