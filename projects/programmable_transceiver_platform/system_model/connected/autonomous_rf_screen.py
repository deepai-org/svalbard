"""Shared RF oscillator: independent input, convergence, lock gates, four paths."""
import cmath
import json
import math
from autonomous_rf_lifecycle import AutonomousRFChip
from chip_model import P
from sustained_lifecycle import run as sustained
from whole_chip_lifecycle import expect_rejection
from rf_modulated_quality import Multicarrier
from rf_selectivity_screen import butterworth_order


def analytic_reference(step):
    c=AutonomousRFChip(rf_step_s=step,watchdog_s=50e-6)
    amplitude=.3+.1j
    c.configure_rx('external_tone',1,5e6,5e6,amplitude,0)
    c.configure(0,0);c.advance(5e-6);assert c.state=='active'
    initial=c.tx.received;start=c.time;duration=400e-9
    c.disturb_rf_lo(start,frequency_hz=1e6)
    p=c.rf_pll;omega=2*math.pi*1e6;zeta=.707;wd=omega*math.sqrt(1-zeta*zeta)
    a=p.error;velocity=p.reference_hz-p.frequency_hz/p.divider
    b=(velocity+zeta*omega*a)/wd
    def phase_error(t):return math.exp(-zeta*omega*t)*(a*math.cos(wd*t)+b*math.sin(wd*t))
    pole=c.tx.rx_pole;total=0j;n=20000;dt=duration/n
    for index in range(n):
        u=(index+.5)*dt
        total+=pole*math.exp(-pole*(duration-u))*amplitude*cmath.exp(2j*math.pi*p.divider*phase_error(u))*dt
    expected=initial*math.exp(-pole*duration)+total
    c.advance(start+duration)
    assert abs(c.rf_pll.error-phase_error(duration))<1e-10
    assert c.rf_continuity_error<1e-9
    assert c.state=='draining' and any(event[1]=='RF oscillator lock loss' for event in c.events if event[0]=='quiesce')
    return dict(step_s=step,waveform_error=abs(c.tx.received-expected),phase_continuity_error_rad=c.rf_continuity_error)


def independent(mode,sign):
    outputs=[];chips=[]
    for disturbed in (False,True):
        c=AutonomousRFChip(watchdog_s=50e-6)
        c.configure_rx('external_tone',1,5e6,5e6,.3+.1j,0)
        c.configure(mode,0);c.advance(5e-6)
        c.capture(32,c.time+100e-9)
        if disturbed:c.disturb_rf_lo(c.time,frequency_hz=sign*200000)
        c.advance(c.time+4e-6);c.host_decoder.finish()
        assert c.state=='active' and len(c.host_samples)==32 and c.host_samples==c.adc_words
        assert c.rf_continuity_error<1e-9
        outputs.append(c.adc_words);chips.append(c)
    assert outputs[0]!=outputs[1]
    # Shared source phase cancels in TX/RX loopback, unlike independent input.
    c=AutonomousRFChip(watchdog_s=50e-6);c.configure(mode,0);c.advance(5e-6)
    c.tx.held=c.tx.filtered=.3+.1j;c.tx.received=.3+.1j
    c.disturb_rf_lo(c.time,frequency_hz=sign*200000);c.advance(c.time+400e-9)
    assert abs(c.tx.received-(.3+.1j))<1e-12
    return dict(mode=mode,sign=sign,changed_adc_samples=sum(a!=b for a,b in zip(*outputs)),
                maximum_phase_discontinuity_rad=max(x.rf_continuity_error for x in chips),loopback_cancels=True)


def controls(mode):
    c=AutonomousRFChip(rf_free_offset=.15,watchdog_s=50e-6)
    c.configure(mode,0);c.advance(5e-6)
    assert c.wire_pll.locked and not c.rf_pll.locked and c.state=='acquiring'
    expect_rejection(lambda:c.schedule_lo([(6e-6,0.,0.,1e6,0.)]))
    expect_rejection(lambda:c.configure_lo(tx_offset_hz=1e6))
    c=AutonomousRFChip(watchdog_s=50e-6)
    token,_,reply=c.submit('configure_mode',0,c.epoch,c.rx_generation,mode)
    result=c.read_reply(token,reply)
    assert result['accepted'] and c.state=='active' and c.rf_pll.locked and c.wire_pll.locked
    old=c.rf_pll
    c.set_reference(False,c.time);phase=old.output_phase_cycles
    c.advance(c.time+1e-6)
    assert c.rf_pll.output_phase_cycles>phase and not c.rf_pll.locked
    c.acknowledge_host_abort(c.epoch,c.time);c.acknowledge_drain(c.epoch,c.time)
    c.set_reference(True,c.time);phase=old.output_phase_cycles;integral=old.integral
    c.configure(1-mode,c.time)
    assert c.rf_pll is old and old.output_phase_cycles==phase and old.integral==integral
    c.advance(c.time+5e-6);assert c.state=='active'
    return dict(mode=mode,outside_range_blocks_arm=True,timed_configuration=True,reference_loss_and_recovery=True)


def modulated(mode,changed_tx):
    source=Multicarrier(seed=828);values=source(800,40e6);chips=[]
    order,cutoff=butterworth_order(8e6,20e6,1,30)
    def factory(**kwargs):
        c=AutonomousRFChip(wire_reference_ppm=100,adc_latency_s=30e-9,dac_latency_s=20e-9,**kwargs)
        c.tx.set_butterworth(order,cutoff)
        c.configure_lo(tx_phase_rad=.7 if changed_tx else 0.)
        c.external_source(values,0,25e-9,offset_hz=250e3)
        chips.append(c);return c
    waveform=lambda n,fs:[complex(-.6 if changed_tx else .2,0)]*n
    row=sustained(mode,100,frames=16,chip_factory=factory,matched_reference=True,
                  host_ppm=-100,waveform=waveform)
    c=chips[0]
    assert c.external_updates>100 and c.rf_continuity_error<1e-9
    assert c.tx.consumed==len(c.adc_words)
    c.adc_accounting();c.dac_accounting()
    row.update(external_source=source.metadata,external_updates=c.external_updates,
               external_carrier_offset_hz=250e3,tx_changed=changed_tx)
    return row


def main():
    convergence=[analytic_reference(step) for step in (25e-9,12.5e-9,6.25e-9)]
    errors=[r['waveform_error'] for r in convergence]
    assert errors[1]<errors[0]/2 and errors[2]<errors[1]/2 and errors[2]<1e-5,errors
    rows=[independent(m,s) for m in (0,1) for s in (-1,1)]
    faults=[controls(m) for m in (0,1)]
    traffic=[]
    for mode in (0,1):
        factory=lambda **kw:AutonomousRFChip(wire_reference_ppm=100,**kw)
        traffic.append(sustained(mode,100,frames=16,chip_factory=factory,matched_reference=True,host_ppm=-100))
    modulation=[]
    for mode in (0,1):
        baseline=modulated(mode,False);changed=modulated(mode,True)
        assert baseline['adc_sha256']==changed['adc_sha256']
        modulation.extend((baseline,changed))
    report=dict(status='passed',modulated_input=modulation,convergence=convergence,independent_input=rows,controls=faults,sustained=traffic,
        complete_architecture=False,physical_qualification=False,
        limitations=['One shared RF synthesizer and separate wired synthesizer; no extra independent RF TX/RX PLL assumed.',
            '2.4GHz candidate carrier; carrier programming and hardware divider/band calibration remain open.',
            'Linear RF phase interpolation is a controlled numerical approximation; convergence checked against an independent analytic-loop convolution.',
            'RF supply-to-frequency coupling, stochastic phase noise, fractional-divider spurs and LO distribution mismatch are not included.',
            'Independent-source tests expose waveform changes, not a full modulated RF quality envelope or Wi-Fi compliance.'])
    (P/'evidence/connected-autonomous-rf.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed autonomous RF convergence, independent-input response, shared-LO cancellation, recovery and four-path traffic')


if __name__=='__main__':main()
