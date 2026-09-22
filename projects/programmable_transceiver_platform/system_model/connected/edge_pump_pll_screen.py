"""Actual PFD edge acquisition, passive-filter invariants and startup envelope."""
import json
from edge_pump_pll import EdgePumpPLL
from chip_model import P


def controls():
    p=EdgePumpPLL(free_offset=0.);p.advance(3e-6)
    assert p.locked and p.feedback_edges==len(p.reference_history)==30
    assert not p.transitions and p.filter.charge==p.filter.voltage_integral==0.
    first=[]
    for offset in (-.04,.04):
        p=EdgePumpPLL(free_offset=offset,bandwidth_hz=.5e6)
        p.advance(300e-9)
        assert p.fault is None and p.transitions
        t,current=p.transitions[0]
        assert current*offset<0
        expected=1/p.reference if offset<0 else p.divider/p.gains.free_hz
        assert abs(t-expected)<1e-18
        first.append(dict(offset=offset,first_current_a=current,first_pulse_start_s=t))
    a=EdgePumpPLL(bandwidth_hz=.5e6);b=EdgePumpPLL(bandwidth_hz=.5e6)
    a.advance(20e-6)
    for i in range(1,124):b.advance(i*20e-6/123)
    voltage_error=max(abs(a.filter.v-b.filter.v),abs(a.filter.w-b.filter.w))
    phase_error=abs(a.phase-b.phase)
    assert voltage_error<1e-8 and phase_error<1e-6
    assert a.locked and b.locked and a.feedback_edges==b.feedback_edges
    return dict(coincident_edges_produce_no_pump_pulse=True,first_pulses=first,
                subdivision_voltage_error=voltage_error,subdivision_phase_error_cycles=phase_error)


def case(rate,reference,bandwidth,offset,phase_s,fraction):
    initial_phase=rate*phase_s
    p=EdgePumpPLL(rate_hz=rate,reference_hz=reference,bandwidth_hz=bandwidth,
        free_offset=offset,initial_phase_cycles=initial_phase,fast_fraction=fraction)
    p.advance(30e-6)
    residual=p.phase-initial_phase-p.gains.free_hz*p.time-p.gains.kvco*p.filter.voltage_integral
    assert abs(residual)<1e-6
    assert abs(p.filter.metrics()['energy_residual_j'])<1e-22
    assert abs(p.filter.cf*p.filter.v+p.filter.cs*p.filter.w-p.filter.charge)<1e-24
    if p.fault:
        assert p.time<30e-6 and p.filter.compliant
        time=p.time;assert not p.advance(31e-6) and p.time==time
    row=p.metrics();row.update(rate_hz=rate,reference_hz=reference,bandwidth_hz=bandwidth,
        free_offset=offset,initial_phase_s=phase_s,fast_fraction=fraction,phase_integral_residual_cycles=residual,
        outcome='compliance_boundary' if p.fault else 'qualified' if p.locked else 'not_qualified_by_deadline')
    return row


def main():
    checks=controls()
    # Keep both gain choices and both capacitor allocations, including failures.
    rows=[case(rate,reference,bw,sign*.04,phase,.5)
          for rate,reference in ((1.25e9,10e6),(2.5e9,10e6),(2.4e9,40e6))
          for bw in (.5e6,1e6) for sign in (-1,1) for phase in (-1e-9,1e-9)]
    rows.extend(case(2.5e9,10e6,bw,sign*.04,phase,.7)
                for bw in (.5e6,1e6) for sign in (-1,1) for phase in (-1e-9,1e-9))
    rows.extend(case(rate,reference,.5e6,sign*.04,phase,.5)
                for rate,reference in ((1.25e9,10e6),(2.5e9,10e6),(2.4e9,40e6))
                for sign in (-1,1) for phase in (-5e-9,5e-9))
    candidate=[r for r in rows if r['bandwidth_hz']==.5e6 and r['fast_fraction']==.5
               and abs(r['initial_phase_s'])==1e-9]
    assert len(candidate)==12 and all(r['outcome']=='qualified' for r in candidate)
    assert all(r['minimum_compliance_margin_v']>.05 for r in candidate)
    assert any(r['outcome']=='compliance_boundary' for r in rows)
    assert any(r['outcome']=='not_qualified_by_deadline' for r in rows)
    report=dict(status='passed',controls=checks,cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Ideal zero-reset-delay edge PFD and matched constant-current pump. Compliance crossing terminates prediction; nonlinear compliance recovery is not modeled.',
            'Linear positive VCO, noiseless reference, no pump leakage/mismatch or supply/VCO noise in this standalone pulse-loop screen.',
            'Selected startup phases and frequency offsets do not establish a full acquisition basin, PVT envelope or RF jitter qualification.',
            'The slower candidate has not replaced the connected full-chip controller; its longer qualification time must be carried into that integration.'])
    (P/'evidence/connected-edge-pump-pll.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed edge-driven PFD invariants and44 startup cases, preserving compliance failures and timeouts')
    print('Candidate worst margin',min(r['minimum_compliance_margin_v'] for r in candidate),
          'latest qualification',max(r['first_lock_s'] for r in candidate))


if __name__=='__main__':main()
