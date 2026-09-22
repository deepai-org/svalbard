"""Counted divider edges and integer-N full-chip clock candidate."""
import copy
from fractions import Fraction
import json
import math
from autonomous_pll import AutonomousPLL
from divider_sequence import DividerSequence
from integer_clock_lifecycle import IntegerClockChip
from chip_model import P
from sustained_lifecycle import run


def sequence_controls():
    rows=[]
    for ratio,rate in ((Fraction(125,4),1.25e9),(Fraction(125,2),2.5e9),(Fraction(60),2.4e9),
                       (Fraction(125),1.25e9),(Fraction(250),2.5e9)):
        divider=DividerSequence(ratio);counts=[];errors=[]
        clock=AutonomousPLL(divider=float(ratio),reference_hz=rate/float(ratio),free_hz=rate,phase_cycles=0.)
        for _ in range(ratio.denominator*8):
            counts.append(divider.step());errors.append(float(divider.cycle_error)/rate)
            assert -1<divider.cycle_error<=0
            deadline=clock.edge_time(divider.total_cycles);clock.advance(deadline)
            assert abs(deadline-divider.total_cycles/rate)<1e-17
            assert abs(clock.output_phase_cycles-divider.total_cycles)<1e-8
        assert divider.cycle_error==0
        assert sum(counts)==len(counts)*ratio
        mean=sum(errors)/len(errors)
        rows.append(dict(ratio=str(ratio),rate_hz=rate,count_pattern=counts[:ratio.denominator],
            peak_to_peak_feedback_edge_error_s=max(errors)-min(errors),
            centered_rms_feedback_error_s=math.sqrt(sum((e-mean)**2 for e in errors)/len(errors))))
    assert rows[0]['peak_to_peak_feedback_edge_error_s']==600e-12
    assert rows[1]['peak_to_peak_feedback_edge_error_s']==200e-12
    assert all(r['peak_to_peak_feedback_edge_error_s']==0 for r in rows[2:])
    return rows


def counted_noisy_edges(chip):
    p=copy.copy(chip.wire_pll);divider=DividerSequence(p.divider)
    origin=math.ceil(p.output_phase_cycles);previous=None;periods=[];residual=0.
    for _ in range(32):
        count=divider.step();assert count==int(p.divider)
        phase=origin+divider.total_cycles;deadline=p.edge_time(phase)
        p.advance(deadline);residual=max(residual,abs(p.output_phase_cycles-phase))
        if previous is not None:periods.append(deadline-previous)
        previous=deadline
    assert residual<1e-8 and max(periods)-min(periods)>1e-14
    return dict(divide_count=int(p.divider),phase_residual_cycles=residual,
                noisy_period_peak_to_peak_s=max(periods)-min(periods))


def traffic(mode,ppm):
    chips=[]
    def factory(**kwargs):
        c=IntegerClockChip(wire_reference_ppm=ppm,rf_noise_rms_hz=20000,wire_noise_rms_hz=10000,
            rf_hz_per_v=1e6,wire_hz_per_v=-1e6,return_charge_per_transition=50e-15,**kwargs)
        chips.append(c);return c
    row=run(mode,ppm,frames=8,chip_factory=factory,matched_reference=True,host_ppm=-ppm)
    c=chips[0];p=c.wire_pll
    assert p.divider==(125 if mode==0 else 250)
    assert abs(p.lock_phase_cycles/p.reference_hz-c.rf_pll.lock_phase_cycles/c.rf_pll.reference_hz)<1e-22
    assert abs(p.lock_frequency_hz/p.reference_hz-1e-4/(1+ppm*1e-6))<1e-18
    row.update(wired_comparison_hz=p.reference_hz,wired_integer_divider=p.divider,
               lock_window_s=p.lock_phase_cycles/p.reference_hz,counted_edges=counted_noisy_edges(c))
    return row


def recovery(mode):
    off_grid=IntegerClockChip(watchdog_s=50e-6)
    off_grid.configure(mode,123.4e-9)
    assert abs(off_grid.next_wire_reference-200e-9)<1e-20
    off_grid.advance(5e-6)
    assert all(abs(t*40e6-round(t*40e6))<1e-7 for t,*_ in off_grid.wire_lock_history)
    assert off_grid.state=='active'
    c=IntegerClockChip(watchdog_s=50e-6,rf_noise_rms_hz=20000,wire_noise_rms_hz=10000)
    token,_,reply=c.submit('configure_mode',0,c.epoch,c.rx_generation,mode)
    assert c.read_reply(token,reply)['accepted'] and c.state=='active'
    c.set_reference(False,c.time);source=c.wire_pll.frequency_noise
    c.acknowledge_host_abort(c.epoch,c.time);c.acknowledge_drain(c.epoch,c.time)
    c.set_reference(True,c.time);c.configure(1-mode,c.time);c.advance(c.time+5e-6)
    assert c.state=='active' and c.wire_pll.frequency_noise is source
    assert c.wire_pll.divider==(250 if mode==0 else 125)
    return dict(mode=mode,timed_configuration=True,mode_recovery=True,noise_realization_retained=True,reference_edges_aligned=True)


def main():
    report=dict(status='passed',divider_counts=sequence_controls(),
        traffic=[traffic(m,ppm) for m in (0,1) for ppm in (-100,100)],recovery=[recovery(m) for m in (0,1)],
        complete_architecture=False,physical_qualification=False,
        limitations=['Raw fractional-divider feedback error is not transmitted clock jitter; the loop filters it.',
            'Integer candidate uses40MHz/4 for wired comparison and40MHz for the RF synthesizer; output rates and host pacing are unchanged.',
            'Lock phase/time and relative-frequency tolerances are preserved; eight slower reference observations extend qualification time.',
            'Counted feedback edges are checked separately; the connected loop still uses an averaged phase detector/filter, not charge-pump pulses.',
            'Reference-divider propagation noise, reference phase noise and physical high-speed divider feasibility remain open.'])
    (P/'evidence/connected-integer-clock.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed exact divider counts, noisy integer-N four-path traffic, timed configuration and mode recovery')


if __name__=='__main__':main()
