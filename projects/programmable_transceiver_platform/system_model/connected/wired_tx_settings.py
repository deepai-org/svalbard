"""Programmable bounded NRZ swing and one-postcursor TX shaping."""
import json,math
from chip_model import P
from wired_blocks import WiredChannel,controls as old_controls
from timed_management import ManagedChip
from managed_resources import command
from sustained_lifecycle import run


def controls():
    old_controls()
    for swing in (.25,.5,1.):
        for tap in (0.,.25,.5):
            c=WiredChannel(1e9,swing=swing,postcursor=tap)
            for _ in range(20):assert c.word(1023)==1023
            assert abs(c.state-swing*(1-tap)/(1+tap))<1e-14
            for _ in range(20):assert c.word(0x155)==0x155
            assert c.peak_drive<=swing+1e-15
    c=ManagedChip(watchdog_s=50e-6)
    assert command(c,'configure_wire_tx',1|(2<<2))['accepted']
    assert c.wire_swing==.5 and c.wire_postcursor==.5
    assert not command(c,'configure_wire_tx',15)['accepted']
    assert command(c,'configure_mode',0)['accepted']
    assert c.channel.swing==.5 and c.channel.postcursor==.5
    assert not command(c,'configure_wire_tx',0)['accepted']
    assert c.channel.swing==.5


def main():
    controls();rows=[]
    for mode in (0,1):
        for swing,tap in ((.25,0.),(.5,.25),(1.,.5)):
            chips=[]
            def factory(**kw):
                c=ManagedChip(**kw);c.configure_wire_tx(swing,tap);chips.append(c);return c
            row=run(mode,100,chip_factory=factory,matched_reference=True,host_ppm=-100)
            row['wired_tx_channel']=chips[0].channel.report();assert row['wired_tx_channel']['peak_drive']<=swing+1e-15
            rows.append(row)
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        contract=['Drive=swing*(current_symbol-postcursor*previous_symbol)/(1+postcursor); history crosses word boundaries.',
        'Swing settings0.25/0.5/1 and postcursor0/0.25/0.5 are disarmed-only candidate normalized settings.'],
        limitations=['Channel still processes one complete TX word per scheduling event; mid-word reset and true bit-clock output remain open.',
        'Normalized swing does not qualify pad voltage, termination, current, power or any interface electrical specification.',
        'One postcursor TX shaping is not a complete programmable RX equalizer or adaptation loop.'])
    (P/'evidence/connected-wired-tx-settings.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six sustained swing/shaping cases, nine driver controls and timed configuration permissions')

if __name__=='__main__':main()
