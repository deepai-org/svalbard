"""Sampled-loop matrix checks, instability control and full-chip noisy traffic."""
import copy
import json
import math
import numpy as np
from sampled_pll import SampledPLL
from sampled_clock_lifecycle import SampledClockChip
from chip_model import P
from sustained_lifecycle import run


def matrix_control(reference,divider,bandwidth):
    p=SampledPLL(reference_hz=reference,divider=divider,free_hz=reference*divider,
        bandwidth_hz=bandwidth,phase_cycles=1e-6)
    period=1/reference;g=p.kvco/divider
    matrix=np.array([[1-g*p.kp*period-.5*g*p.ki*period**2,-g*period],[p.ki*period,1.]])
    state=np.array([p.error,p.integral]);errors=[]
    # Exact recurrence for unsaturated held-error PI integration.
    for index in range(1,13):
        state=matrix@state;p.advance(index*period)
        errors.append(max(abs(p.error-state[0]),abs(p.integral-state[1])))
        assert abs(p.control())<p.rail
    assert max(errors)<1e-9
    return dict(reference_hz=reference,bandwidth_hz=bandwidth,
                spectral_radius=float(max(abs(np.linalg.eigvals(matrix)))),recurrence_error=max(errors))


def prediction_control():
    p=SampledPLL(reference_hz=10e6,divider=125,free_hz=1.25e9,phase_cycles=1e-4)
    p.advance(90e-9);q=copy.copy(p);before=(p.time,p.error,p.integral,p.detector_updates)
    target=p.output_phase_cycles+50;deadline=p.edge_time(target)
    assert (p.time,p.error,p.integral,p.detector_updates)==before
    p.advance(deadline)
    # Same crossing interval, many caller subdivisions, including a detector tick.
    for time in np.linspace(q.time,deadline,101)[1:]:q.advance(float(time))
    assert p.detector_updates==q.detector_updates and p.detector_updates>before[-1]
    assert abs(p.output_phase_cycles-target)<1e-8 and abs(p.error-q.error)<1e-10
    return dict(crossing_residual_cycles=abs(p.output_phase_cycles-target),detector_updates=p.detector_updates)


def recovery(mode):
    c=SampledClockChip(watchdog_s=50e-6,wire_noise_rms_hz=10000,rf_noise_rms_hz=20000)
    c.configure(mode,123.4e-9);c.advance(5e-6);assert c.state=='active'
    assert abs(c.wire_pll.next_detector-c.next_wire_reference)<1e-20
    c.set_reference(False,c.time);held=c.wire_pll.control();updates=c.wire_pll.detector_updates
    c.advance(c.time+1e-6)
    assert c.wire_pll.control()==held and c.wire_pll.detector_updates==updates
    c.acknowledge_host_abort(c.epoch,c.time);c.acknowledge_drain(c.epoch,c.time)
    c.set_reference(True,c.time);c.configure(1-mode,c.time);c.advance(c.time+5e-6)
    assert c.state=='active' and c.wire_pll.locked and c.rf_pll.locked
    return dict(mode=mode,off_grid_start=True,holdover_detector_frozen=True,mode_recovery=True)


def independent_rf(mode):
    values=[];codes=[]
    for shift in (0.,100000.):
        c=SampledClockChip(rf_noise_rms_hz=20000,wire_noise_rms_hz=10000,watchdog_s=50e-6)
        c.configure_rx('external_tone',1,5e6,5e6,.3+.1j,0.)
        c.configure(mode,0);c.advance(5e-6)
        c.capture(32,c.time+100e-9)
        c.disturb_rf_lo(c.time+200e-9,frequency_hz=shift)
        c.advance(9e-6);c.host_decoder.finish()
        assert c.state=='active' and c.host_samples==c.adc_words and len(c.adc_words)==32
        assert c.rf_continuity_error<1e-8
        values.append(c.analog_samples);codes.append(c.adc_words)
    difference=max(abs(a-b) for a,b in zip(*values))
    assert difference>1e-5
    return dict(mode=mode,maximum_analog_difference=difference,changed_codes=sum(a!=b for a,b in zip(*codes)))


def main():
    stable=[matrix_control(10e6,125,1e6),matrix_control(40e6,60,1e6)]
    unstable=matrix_control(10e6,125,3e6)
    assert all(row['spectral_radius']<1 for row in stable)
    assert unstable['spectral_radius']>1
    c=SampledClockChip(wire_bandwidth_hz=3e6,watchdog_s=50e-6)
    c.configure(0,0);c.advance(10e-6)
    assert not c.wire_pll.locked and c.state!='active'
    rows=[]
    for mode in (0,1):
        def factory(**kw):
            return SampledClockChip(wire_reference_ppm=100,rf_noise_rms_hz=20000,wire_noise_rms_hz=10000,
                rf_hz_per_v=1e6,wire_hz_per_v=-1e6,return_charge_per_transition=50e-15,**kw)
        rows.append(run(mode,100,frames=8,chip_factory=factory,matched_reference=True,host_ppm=-100))
    report=dict(status='passed',independent_rf=[independent_rf(m) for m in (0,1)],stable_matrices=stable,unstable_matrix=unstable,
        excessive_bandwidth_state=c.state,prediction=prediction_control(),recovery=[recovery(m) for m in (0,1)],traffic=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Detector samples unwrapped phase error at reference edges and holds it into a continuous PI filter; no charge-pump pulse shape, dead zone or extra pipeline delay.',
                    'The1MHz natural-frequency assumption passes this sampled model; it is not a measured loop bandwidth or a physical stability guarantee.',
                    'Shared reference noise, physical divider propagation and independent wideband RF quality remain open.'])
    (P/'evidence/connected-sampled-clock.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed sampled-loop recurrence, unstable-bandwidth control, predictive crossings, recovery and noisy four-path traffic')


if __name__=='__main__':main()
