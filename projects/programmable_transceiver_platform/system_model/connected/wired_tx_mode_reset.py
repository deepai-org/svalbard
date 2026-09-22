"""Retain external TX channel voltage and bandwidth across serializer mode reset."""
import json,math
from chip_model import P
from timed_lifecycle import TimedChip


def run(mode,cut_ui):
    c=TimedChip();c.configure(mode,0);c.advance(c.acquisition_s)
    c.accept_wire(0x155);start=c.time+100e-9;c.schedule_wire(1,start)
    ui=c.wire_period/10;cut=start+cut_ui*ui;c.advance(cut)
    old_pole=c.serializer.pole;old_state=c.channel.state
    assert abs(old_state)>.1 and c.serializer.active
    c.set_reference(False,cut);c.acknowledge_drain(c.epoch,cut)
    c.set_reference(True,cut);c.configure(1-mode,cut)
    assert c.channel.state==old_state and c.serializer.pole==old_pole
    assert c.channel.previous_symbol==0 and not c.serializer.active
    assert c.channel.rate==(2.5e9 if mode==0 else 1.25e9)
    c.advance(cut+.1*ui)
    assert abs(c.channel.state-old_state*math.exp(-old_pole*(c.time-cut)))<1e-12
    c.advance(c.lock_at)
    for word in (0x123,0x267):c.accept_wire(word)
    start=c.time+100e-9;c.schedule_wire(2,start);c.advance(start+2*c.wire_period)
    assert c.wired_output==[0x123,0x267]
    accounting=c.wire_accounting()
    assert accounting['partial_words_discarded']==1 and accounting['completed_words']==2
    return dict(initial_mode=mode,new_mode=1-mode,cut_ui=cut_ui,retained_state=old_state,
                retained_bandwidth_hz=old_pole/(2*math.pi),accounting=accounting)


def main():
    rows=[run(m,t) for m in (0,1) for t in (.75,3.75,8.75)]
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        contract=['Digital mode reset clears serializer history but retains external channel voltage and absolute bandwidth.',
        'Muted drive decays continuously during reacquisition; subsequent bits use the new line rate against the same channel.'],
        limitations=['Single-pole external fixture only; termination switches, common mode and package reflections are unmodeled.',
        'Successful selected words at both rates do not qualify eye margin or channel loss tolerance.',
        'Autonomous TX clock acquisition, jitter and supply response remain open.'])
    (P/'evidence/connected-wired-tx-mode-reset.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six cross-mode TX channel continuity, decay and partial-word exclusion cases')

if __name__=='__main__':main()
