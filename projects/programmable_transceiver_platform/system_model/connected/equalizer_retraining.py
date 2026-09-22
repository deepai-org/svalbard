"""Equalizer analog-state inheritance and timed boost programming."""
import json
from chip_model import P
from timed_management import ManagedChip
from managed_resources import command
from wired_equalizer import EqualizedChip
from playback_memory_lifecycle import ready


def run(mode,boost):
    c=EqualizedChip(rx_boost=boost,watchdog_s=20e-6);ready(c,mode)
    c.capture(0,c.time+10e-9);c.incoming_wire([0x139],c.time)
    c.advance(c.live_rx.stop);old=c.live_rx
    state=(old.state,old.slow,old.pole,old.eq_pole,old.decision_value())
    assert abs(old.slow)>.01
    c.incoming_wire([0x267,0x155],c.time);new=c.live_rx
    assert state==(new.state,new.slow,new.pole,new.eq_pole,new.decision_value())
    c.advance(new.stop+1e-6)
    assert c.host_wire==[0x139,0x267,0x155] and not c.host_samples
    return dict(mode=mode,boost=boost,retained_channel=state[0],retained_equalizer=state[1],words=c.host_wire)


def management(mode):
    c=ManagedChip(watchdog_s=1e-3)
    assert command(c,'configure_wire_rx',3)['accepted'] and c.rx_boost==2
    assert not command(c,'configure_wire_rx',4)['accepted'] and c.rx_boost==2
    assert command(c,'configure_mode',mode)['accepted']
    c.incoming_wire([0x155],c.time);rx=c.live_rx
    assert rx.boost==2
    assert not command(c,'configure_wire_rx',0)['accepted'] and rx.boost==2
    assert command(c,'stop')['accepted'];assert command(c,'ack_abort')['accepted'];assert command(c,'ack_drain')['accepted']
    before=(rx.state,rx.slow,rx.pole,rx.eq_pole)
    assert command(c,'configure_wire_rx',1)['accepted'] and rx.boost==.5
    # Held input is steady by this point; changing gain must not clear charge.
    assert abs(rx.state-before[0])<1e-12 and abs(rx.slow-before[1])<1e-12
    assert command(c,'configure_mode',1-mode)['accepted']
    c.incoming_wire([0x267],c.time)
    assert c.live_rx.boost==.5 and c.live_rx.pole==before[2] and c.live_rx.eq_pole==before[3]
    c.advance(c.live_rx.stop)
    return dict(initial_mode=mode,new_mode=1-mode,boost=c.live_rx.boost,retained_pole=c.live_rx.pole)


def main():
    rows=[run(m,b) for m in (0,1) for b in (.5,2.)];writes=[management(m) for m in (0,1)]
    report=dict(status='passed',cases=rows,management_cases=writes,complete_architecture=False,physical_qualification=False,
        limitations=['Timed payload selects four fixed boosts; automatic adaptation and calibration are not implemented.',
        'State retention applies to the same equalizer topology; arbitrary capacitor reconnection is not modeled.',
        'Analog bandwidth is retained across mode changes; physical bias/termination switching remains outside the model.'])
    (P/'evidence/connected-equalizer-retraining.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed four equalizer-state retraining cases and two timed configuration/mode-change cases')

if __name__=='__main__':main()
