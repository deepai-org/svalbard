"""Internal reference/rail monitoring and caller-subdivision invariance."""
import json
from chip_model import P
from programmable_chip import ProgrammableChip
from managed_resources import command

def run(mode,route,pieces):
    c=ProgrammableChip(watchdog_s=100e-6,return_charge_per_transition=50e-15)
    assert command(c,'monitor_select',route)['accepted']
    assert command(c,'diagnostic_select',1)['accepted']
    c.configure(mode,c.time);c.advance(c.time+8e-6)
    if route==1:c.supply.draw(c.time,1e-12)
    if route==2:c.adc_reference.sample(c.time,.8+0j)
    start=c.time;c.capture(64,start+100e-9)
    for n in range(1,pieces+1):c.advance(start+6e-6*n/pieces)
    c.host_decoder.finish()
    assert len(c.host_samples)==64 and c.host_samples==c.adc_words
    assert c.monitor_updates>0 and abs(c.tile.voltage)>0
    return dict(mode=mode,route=route,updates=c.monitor_updates,voltage=c.tile.voltage,words=c.adc_words)

def main():
    rows=[]
    for mode in (0,1):
        for route in (1,2):
            a=run(mode,route,1);b=run(mode,route,137)
            assert a['words']==b['words'] and a['updates']==b['updates']
            assert abs(a['voltage']-b['voltage'])<1e-12
            rows.append(a)
    (P/'evidence/connected-internal-monitor.json').write_text(json.dumps(dict(status='passed',cases=rows,
        complete_architecture=False,physical_qualification=False,
        limitations=['Ideal monitor buffer and assumed sampling cadence; no switch charge, noise or loading.',
        'Rail and reference routes tested; probe-pad route and shutdown/rearm tests remain open.',
        'Slow sampling can miss short disturbances; no peak-detection guarantee.']),indent=2)+'\n')
    print('Passed internal monitor transport and fixed-cadence subdivision checks')
if __name__=='__main__':main()
