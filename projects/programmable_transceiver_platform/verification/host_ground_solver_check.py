"""Standalone host-bank solver equivalence under explicit circuit hypotheses.

One resistive supply branch and eleven 10 pF loads intentionally simplify and
stress the mathematics. They are not the selected package, GPIO implementation
or a host capture/whole-chip qualification fixture.
"""
import json
import numpy as np
from host_bank_supply import LimitedHostBankSupply


def fixture_bank():
    return LimitedHostBankSupply([3.3],[2.],[100e-12],.1,
        [0]*11,[10e-12]*11,[100.]*11,[80.]*11,
        pullup_limit_a=[.010]*11,pulldown_limit_a=[.012]*11,
        rising_charge_c=[7e-12]*11,falling_charge_c=[7e-12]*11,
        switching_tau_s=.5e-9,minimum_supply_v=[2.5])


def piecewise_currents(bank,state,levels):
    """Candidate exact piecewise-linear ground solve; verification only."""
    u=state[:bank.n];out=state[bank.n:]
    denominator=1/bank.return_r+np.sum(1/bank.feed_r)
    center=np.sum((bank.nominal-u)/bank.feed_r)/denominator
    resistance=np.where(levels,bank.pullup_r,bank.pulldown_r)
    limit=np.where(levels,bank.up_limit,bank.down_limit)
    offset=np.where(levels,out-u[bank.output_domain],out)
    radius=np.sum(limit)/denominator
    lo=center-radius-1e-12;hi=center+radius+1e-12
    knots=np.unique(np.clip(np.r_[lo,offset-resistance*limit,
                                     offset+resistance*limit,hi],lo,hi))
    values=denominator*(knots-center)+np.sum(np.clip(
        (knots[:,None]-offset)/resistance,-limit,limit),axis=1)
    index=int(np.searchsorted(values,0.))
    assert 0<index<len(knots)
    a,b=knots[index-1:index+1];fa,fb=values[index-1:index+1]
    ground=a-fa*(b-a)/(fb-fa)
    branch=np.clip((ground-offset)/resistance,-limit,limit)
    up=np.where(levels,branch,0.);down=np.where(levels,0.,-branch)
    return ground,(bank.nominal-u-ground)/bank.feed_r,up,down


def ground_solver_controls():
    import time
    bank=fixture_bank()
    rng=np.random.default_rng(93642);cases=[]
    for _ in range(2000):
        state=np.r_[rng.uniform(2.5,3.6,bank.n),rng.uniform(-.5,4.,bank.m)]
        levels=rng.integers(0,2,bank.m).astype(bool)
        cases.append((state,levels))
    start=time.perf_counter();expected=[bank.currents(*case) for case in cases]
    baseline=time.perf_counter()-start
    start=time.perf_counter();actual=[piecewise_currents(bank,*case) for case in cases]
    candidate=time.perf_counter()-start
    maximum=0.
    for (ground,feed,up,down),reference in zip(actual,expected):
        delta=max(float(np.max(abs(np.asarray(a)-np.asarray(b))))
            for a,b in zip((ground,feed,up,down),reference))
        maximum=max(maximum,delta);assert delta<1e-12
        assert abs(ground/bank.return_r-np.sum(feed)+np.sum(up)-np.sum(down))<1e-12
    import copy
    from types import MethodType
    transients=[]
    for rtol,atol in ((1e-9,1e-12),(1e-10,1e-13),(1e-11,1e-14)):
        baseline_bank=copy.deepcopy(bank);candidate_bank=copy.deepcopy(bank)
        baseline_bank.externally_owned=candidate_bank.externally_owned=False
        candidate_bank.currents=MethodType(piecewise_currents,candidate_bank)
        voltage_error=0.
        for i,word in enumerate((0,2047,0,1365,682,2047,0,1023)):
            for network in (baseline_bank,candidate_bank):
                network.advance((i+1)*3.2e-9,[.020],
                    [(word>>bit)&1 for bit in range(11)],rtol=rtol,atol=atol)
            voltage_error=max(voltage_error,float(np.max(abs(baseline_bank.state-candidate_bank.state))))
        energy_error=max(abs(getattr(baseline_bank,k)-getattr(candidate_bank,k))
            for k in ('source_energy','resistor_energy','load_energy','driver_energy','internal_energy'))
        transients.append(dict(rtol=rtol,atol=atol,maximum_voltage_difference_v=voltage_error,
            maximum_final_energy_difference_j=energy_error,passes_1nv=voltage_error<1e-9))
    # Keep the coarse discrepancy visible; qualify the refined comparison only.
    assert all(row['passes_1nv'] and row['maximum_final_energy_difference_j']<1e-18
               for row in transients[1:])
    return dict(transient_refinement=transients,cases=len(cases),maximum_numeric_difference=maximum,
        baseline_seconds=baseline,candidate_seconds=candidate,
        speedup=baseline/candidate,full_chip_requalification=False)


def floor_rejection_controls():
    from types import MethodType
    for candidate in (False,True):
        bank=fixture_bank()
        if candidate:bank.currents=MethodType(piecewise_currents,bank)
        state=bank.state.copy();pending=bank.pending_charge.copy();drive=bank.drive.copy()
        try:bank.advance(10e-9,[20.],[1]*11)
        except ValueError:pass
        else:raise AssertionError('Supply floor not rejected')
        assert bank.time==0 and np.array_equal(bank.state,state)
        assert np.array_equal(bank.pending_charge,pending) and np.array_equal(bank.drive,drive)
        assert bank.source_energy==bank.resistor_energy==bank.load_energy==bank.driver_energy==bank.internal_energy==0
    return dict(atomic_floor_rejections=2)


if __name__=='__main__':
    import argparse
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(dict(scope=__doc__.strip(),solver=ground_solver_controls(),
                          floor=floor_rejection_controls()),indent=2))
