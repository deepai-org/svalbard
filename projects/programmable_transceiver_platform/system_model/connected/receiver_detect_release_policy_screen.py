"""Local-only release decisions, validated against hidden state and repeat probes."""
import itertools,json
from chip_model import P
from receiver_detect_rearm_screen import RecoverableProbe


def main():
    rows=[]
    for rt,cc,rs in itertools.product((40.,100.,1e5,1e8),(10e-9,100e-9),(100.,1000.)):
        loads=[dict(cp=5e-12,cr=5e-12,cc=cc,rs=rs,rt=rt)]*2
        p=RecoverableProbe(loads);p.start(0,0);p.advance(3e-6)
        assert p.state=='releasing'  # Even a tiny sensed voltage cannot bypass dwell.
        p.advance(8e-6);assert p.state=='ready'
        first=p.read(0);expected='present' if rt<=100 else 'absent'
        assert first['decision']==expected
        assert first['ready_at']>=4.2e-6
        hidden=max(abs(leg.x[1]) for leg in p.legs)  # Validation oracle only.
        assert hidden<=.005
        p.start(p.time,0);p.advance(p.time+8e-6);assert p.read(0)['decision']==expected
        p.abort(p.time);p.rearm(p.time,p.epoch);p.advance(p.time+8e-6)
        assert p.state=='idle'
        rows.append(dict(rt=rt,cc=cc,rs=rs,decision=expected,ready_s=first['ready_at'],hidden_remote_voltage_v=float(hidden)))
    # An unavailable/stuck monitor must time out instead of overriding it with
    # the simulator's hidden capacitor voltage.
    p=RecoverableProbe(loads);p.start(0,0);p.advance(200e-9)
    p.sensor=lambda value:.01
    p.advance(1.01e-3)
    assert p.state=='fault' and p.result is None and p.drive is None
    report=dict(status='passed',cases=rows,stuck_monitor_fault=True,
        complete_architecture=False,physical_qualification=False,
        limitations=['Fixed4us minimum dwell plus local5mV monitor criterion is a candidate policy, not a proven full-envelope bound.',
        'Sixteen zero-initial-state paired load cases; arbitrary precharged remote networks are not qualified.',
        'Hidden remote voltage is inspected only by the test, never by the controller.',
        'Real monitor noise/offset, timing accuracy and output compliance still require joint coverage.'])
    (P/'evidence/connected-receiver-detect-release-policy.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed16 local-only release/repeat/rearm cases and stuck-monitor timeout')

if __name__=='__main__':main()
