"""Independent compliance-region solution and recovery of prior boundary cases."""
import json
import math
import numpy as np
from compliant_pump_filter import CompliantPumpFilter
from compliant_edge_pll import CompliantEdgePLL
from edge_pump_pll import EdgePumpPLL
from chip_model import P


def controls():
    errors=[]
    for sign in (-1,1):
        f=CompliantPumpFilter(60e3,.2e-12,4e-12,voltage=sign*.95)
        command=sign*100e-6;time=2e-9;conductance=abs(command)/f.headroom
        matrix=np.array([[-(1/f.r+conductance)/f.cf,1/(f.r*f.cf)],
                         [1/(f.r*f.cs),-1/(f.r*f.cs)]])
        eigenvectors=None
        rates,vectors=np.linalg.eig(matrix)
        initial=np.array([f.v-sign*f.limit,f.w-sign*f.limit])
        weights=np.linalg.solve(vectors,initial)
        expected=sign*f.limit+vectors@(np.exp(rates*time)*weights)
        expected_integral=sign*f.limit*time+(vectors@(np.expm1(rates*time)/rates*weights))[0]
        initial_charge=f.cf*f.v+f.cs*f.w
        f.advance(time,command)
        error=max(abs(f.v-expected[0]),abs(f.w-expected[1]));errors.append(float(error))
        assert error<1e-12 and abs(f.voltage_integral-expected_integral)<1e-21
        assert abs(f.cf*f.v+f.cs*f.w-initial_charge-f.charge)<1e-25
        assert abs(f.metrics()['energy_residual_j'])<1e-24
        assert f.compliant and 0<f.minimum_current_fraction<1
        # With the pump off, charge stays stored while differential energy decays.
        charge=f.charge;energy=f.energy;f.advance(time+100e-9,0.)
        assert f.charge==charge and f.energy<energy
    return dict(independent_matrix_voltage_errors=errors,pump_off_charge_conserved=True)


def simulate(settings,headroom=.1):
    p=CompliantEdgePLL(rate_hz=settings['rate_hz'],reference_hz=settings['reference_hz'],
        bandwidth_hz=settings['bandwidth_hz'],free_offset=settings['free_offset'],
        initial_phase_cycles=settings['rate_hz']*settings['initial_phase_s'],
        fast_fraction=settings['fast_fraction'],headroom_v=headroom)
    p.advance(30e-6)
    assert p.fault is None and p.filter.compliant
    assert abs(p.filter.cf*p.filter.v+p.filter.cs*p.filter.w-p.filter.charge)<1e-22
    assert abs(p.filter.metrics()['energy_residual_j'])<1e-21
    residual=p.phase-settings['rate_hz']*settings['initial_phase_s']-p.gains.free_hz*p.time-p.gains.kvco*p.filter.voltage_integral
    assert abs(residual)<1e-6
    row=p.metrics();row.update(settings=settings,headroom_v=headroom,
        outcome='qualified' if p.locked else 'not_qualified_by_deadline',phase_integral_residual_cycles=residual)
    return row


def main():
    checks=controls();baseline=json.loads((P/'evidence/connected-edge-pump-pll.json').read_text())
    rows=[]
    for old in baseline['cases']:
        settings={key:old[key] for key in ('rate_hz','reference_hz','bandwidth_hz','free_offset','initial_phase_s','fast_fraction')}
        row=simulate(settings);row['prior_outcome']=old['outcome'];rows.append(row)
    recovered=[r for r in rows if r['prior_outcome']=='compliance_boundary']
    assert len(rows)==44 and len(recovered)==6 and all(r['outcome']=='qualified' for r in recovered)
    sensitivity=[]
    for sign in (-1,1):
        settings=dict(rate_hz=2.5e9,reference_hz=10e6,bandwidth_hz=.5e6,
            free_offset=sign*.04,initial_phase_s=sign*5e-9,fast_fraction=.5)
        for headroom in (.05,.2):sensitivity.append(simulate(settings,headroom))
    assert all(r['outcome']=='qualified' for r in sensitivity)
    unreachable=CompliantEdgePLL(rate_hz=2.5e9,bandwidth_hz=.5e6,free_offset=.15)
    unreachable.advance(30e-6)
    assert unreachable.fault is None and not unreachable.locked and unreachable.first_lock is None
    assert unreachable.frequency_hz>unreachable.rate*1.01 and unreachable.filter.compliant
    report=dict(status='passed',controls=checks,cases=rows,headroom_sensitivity=sensitivity,
        outside_tuning_range=unreachable.metrics(),complete_architecture=False,physical_qualification=False,
        limitations=['Assumed symmetric linear current rolloff over50–200mV below a+/-1V control limit; not a measured GF180 pump I/V curve.',
            'No voltage clipping or charge reset; current reduction changes the actual PFD pulse-loop trajectory.',
            'Ideal zero-delay PFD reset and matched pumps remain; leakage, mismatch, switching charge and clock noise still need integration.',
            'Standalone startup cases do not establish a complete acquisition basin, jitter quality or full-chip closure.'])
    (P/'evidence/connected-compliant-edge-pll.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed compliance-law controls,44 startup comparisons, headroom sensitivity and unreachable-frequency rejection')


if __name__=='__main__':main()
