"""Dwell timing and execution-time rejection, without claiming RF acquisition."""
import json,math
from chip_model import P
from programmable_calibration_dwell import ProgrammableDwellChip,DwellSequence
from shared_tx_detector import SharedAdcDetector
from tx_iq_calibration import probes

def main():
    c=ProgrammableDwellChip(adc_latency_s=30e-9)
    assert c.execute_management('tx_cal_dwell',400,c.time)['value']==400
    assert math.isclose(c.tx_cal.probe_dwell_s,10e-6)
    for value in (0,79,4001,True):
        try:c.execute_management('tx_cal_dwell',value,c.time)
        except ValueError:pass
        else:raise AssertionError('Invalid dwell admitted')
    before=c.tx_cal.probe_dwell_s
    c.tx_cal.state='settle'
    try:c.execute_management('tx_cal_dwell',80,c.time)
    except ValueError:pass
    else:raise AssertionError('Busy dwell mutation admitted')
    assert c.tx_cal.probe_dwell_s==before
    z=probes();readings=iter(abs(z)**2)
    d=SharedAdcDetector(lambda value,time:(float(next(readings)),False),latency=30e-9)
    s=DwellSequence(d,lambda t,v:None,lambda c:None,lambda t:None,probe_dwell_s=10e-6)
    s.start(0.,epoch=0,quiet=True,probes=z)
    while s.next_event is not None:
        t=s.next_event;d.advance(t,[(0j,0j)]);s.service(t,epoch=0,quiet=True)
    assert s.state=='ready' and math.isclose(s.time,9*(10e-6+30e-9))
    report=dict(status='passed',duration_s=s.time,configured_ticks=400,
        limitations=['Local timing and management handler tests; serialized polling and full RF startup not yet exercised.',
            'Control tick range is a proposed model ABI, not implemented RTL or a proven physical settling budget.'])
    (P/'evidence/connected-programmable-dwell.json').write_text(json.dumps(report,indent=2)+'\n');print(report)

if __name__=='__main__':main()
