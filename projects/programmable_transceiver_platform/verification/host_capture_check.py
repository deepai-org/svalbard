"""Canonical host-pad voltage and forwarded-clock screens; unqualified hypotheses."""
import argparse
import hashlib
import json
import numpy as np
from full_chip_model import make_chip
from fast_loaded_output import P


def source_hashes():
    files=list((P/'system_model').rglob('*.py'))+list((P/'verification').glob('*.py'))+[P/'spec/contract.json']
    hashes={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    return hashes


def verify_sources(hashes):
    assert all(hashlib.sha256((P/p).read_bytes()).hexdigest()==h for p,h in hashes.items())


def voltage_screen(hashes):
    rows=[];bounds=[]
    conditions=[('nominal',1.,1.),('load_plus20',1.2,1.),
                ('limit_minus20',1.,.8),('combined',1.2,.8)]
    for condition,cap_scale,current_scale in conditions:
     for period in (4e-9,3.2e-9):
        c=make_chip();c.configure_resources(engine='wire',line_rate_bps=1.62e9)
        bank=c.analog_owner.host_bank
        # Hypothesis changes at time zero, before stored output charge exists.
        bank.load_cap*=cap_scale;bank.cap[bank.n:]=bank.load_cap
        bank.up_limit*=current_scale;bank.down_limit*=current_scale
        assert bank.cap_energy()==bank.initial_energy
        rise_bound=float(bank.up_limit[0]*period/bank.load_cap[0])
        bounds.append(dict(condition=condition,period_s=period,maximum_first_rise_v=rise_bound,
            first_high_impossible_within_word=rise_bound<2.31))
        for index,word in enumerate((1023,0,0x155,0x2aa)):
            start=index*period
            c.advance(start);c.emitted_return_word(word,start)
            for phase in (.25,.5,.75,.9):
                c.advance(start+phase*period)
                bank=c.analog_owner.host_bank;v=bank.state[bank.n:bank.n+10]
                low=.3*3.3;high=.7*3.3
                unknown=(v>low)&(v<high)
                observed=sum(int(x>=high)<<i for i,x in enumerate(v))
                margins=[float(x-high if word&(1<<i) else low-x) for i,x in enumerate(v)]
                if index==0:
                    assert max(v)<=rise_bound*phase+1e-9,'Output exceeded current/charge bound'
                rows.append(dict(condition=condition,cap_scale=cap_scale,current_limit_scale=current_scale,
                    period_s=period,word_index=index,expected_word=word,phase=phase,
                    minimum_logic_margin_v=min(margins),observed_word=observed,
                    ambiguous_bits=int(np.count_nonzero(unknown)),
                    word_valid=not bool(np.any(unknown)) and observed==word,
                    minimum_output_v=float(min(v)),maximum_output_v=float(max(v)),
                    forwarded_clock_v=float(bank.state[bank.n+10])))
        assert c.time==c.analog_owner.time
        print(condition,period,'completed',flush=True)
    verify_sources(hashes)
    report=dict(status='completed',cases=rows,source_sha256=hashes,full_chip_closure=False,
        physical_timing_qualified=False,current_charge_bounds=bounds,
        assumed_receiver=dict(vil_v=.99,vih_v=2.31,reference='fixed external ground, 3.3 V nominal'),
        scope='diagnostic pad launch and voltage sampling on canonical supply owner; no acquired framing or FPGA clock capture',
        limitations=['Four words per case; provisional fixed thresholds; +/-20% load/current hypotheses are not PDK corners. Pull resistances and switching charge are unchanged.',
            'No setup/hold, receiver hysteresis, clock skew, package ringing, process or temperature envelope.'])
    (P/'evidence/host-voltage.json').write_text(json.dumps(report,indent=2)+'\n')
    for period in (4e-9,3.2e-9):
     for phase in (.25,.5,.75):
      selected=[r for r in rows if r['condition']=='nominal' and r['period_s']==period and r['phase']==phase]
      print(period,phase,'valid words',sum(r['word_valid'] for r in selected),'of',len(selected),flush=True)


def capture_screen(hashes, sized_driver=False):
    rows=[]
    # Preserve the failing case; stronger drive is an unqualified design candidate.
    conditions=([('sized_candidate',1.2,1.2,1/1.5,1.5),
                 ('charge_stress',1.2,1.2,1/1.5,3.)] if sized_driver else
                [('nominal',1.,1.,1.,1.),('uncertain',1.2,.8,1.,1.),
                 ('stronger_candidate',1.2,1.2,1.,1.)])
    for name,cap_scale,current_scale,resistance_scale,charge_scale in conditions:
        c=make_chip();c.configure_resources(engine='wire',line_rate_bps=1.62e9)
        bank=c.analog_owner.host_bank
        bank.load_cap*=cap_scale;bank.cap[bank.n:]=bank.load_cap
        bank.up_limit*=current_scale;bank.down_limit*=current_scale
        bank.pullup_r*=resistance_scale;bank.pulldown_r*=resistance_scale
        bank.rise_charge*=charge_scale;bank.fall_charge*=charge_scale
        minimum_rail=float(min(bank.state[:bank.n]))
        assert bank.cap_energy()==bank.initial_energy
        period=3.2e-9;grid=np.linspace(0.,period,33);windows=[];details=[]
        for index in range(8):
            word=1023 if index%2==0 else 0;start=index*period
            c.advance(start);c.emitted_return_word(word,start)
            bank=c.analog_owner.host_bank;wave=[bank.state[bank.n:].copy()]
            for dt in grid[1:]:
                c.advance(start+float(dt));bank=c.analog_owner.host_bank
                wave.append(bank.state[bank.n:].copy())
                minimum_rail=min(minimum_rail,float(min(bank.state[:bank.n])))
            wave=np.asarray(wave)
            good=np.all(wave[:,:10]>=2.31 if word else wave[:,:10]<=.99,axis=1)
            crossings=np.flatnonzero((wave[:-1,10]-1.65)*(wave[1:,10]-1.65)<0)
            window=None;crossing=None
            if len(crossings)==1 and good[-1]:
                j=int(crossings[0]);v0,v1=wave[j:j+2,10]
                crossing=float(grid[j]+(1.65-v0)*(grid[j+1]-grid[j])/(v1-v0))
                bad=np.flatnonzero(~good);first=int(bad[-1]+1) if len(bad) else 0
                # Conservatively end at the next launch, without assuming extra hold
                # from output inertia. Each side reserves 0.2 ns combined allowance.
                window=[float(grid[first]-crossing+.2e-9),float(period-crossing-.2e-9)]
            windows.append(window)
            details.append(dict(word_index=index,clock_crossings=len(crossings),
                clock_crossing_s=crossing,clock_relative_window_s=window,
                valid_at_word_end=bool(good[-1])))
        valid=all(w is not None for w in windows)
        common=[max(w[0] for w in windows),min(w[1] for w in windows)] if valid else None
        rows.append(dict(condition=name,cap_scale=cap_scale,current_scale=current_scale,
            resistance_scale=resistance_scale,charge_scale=charge_scale,
            minimum_sampled_rail_v=minimum_rail,
            consumed_switching_charge_c=float(np.sum(bank.consumed_charge)),
            pending_switching_charge_c=float(np.sum(bank.pending_charge)),
            common_clock_relative_window_s=common,
            has_sampled_window=bool(valid and common[0]<common[1]),words=details))
        assert c.time==c.analog_owner.time==c.analog_owner.host_bank.time
        print(name,common,flush=True)
    verify_sources(hashes)
    report=dict(status='completed',cases=rows,source_sha256=hashes,full_chip_closure=False,
        physical_timing_qualified=False,word_period_s=period,grid_s=period/32,
        assumptions=['Eight alternating all-bit words, stopped diagnostic launches on canonical supply owner.',
            'Fixed external data thresholds 0.99/2.31 V; clock threshold 1.65 V with linear crossing interpolation.',
            '0.2 ns allowance on each side is hypothetical combined setup/hold/skew budget, not a receiver specification.',
            'Common window is relative to observed clock crossings, requiring external receiver delay capability.',
            'Sampled voltages do not prove continuous-time validity; jitter, launch mismatch, ringing and receiver hysteresis omitted.',
            'Default stronger candidate scales only current limits. Sized-driver cases additionally scale resistance and switching charge as explicit hypotheses, not PDK-calibrated sizing.'])
    (P/('evidence/host-capture-sized.json' if sized_driver else 'evidence/host-capture.json')).write_text(json.dumps(report,indent=2)+'\n')


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
    bank=make_chip().analog_owner.host_bank
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
                network.advance((i+1)*3.2e-9,[.02,.002,.002,0,0,0,.008],
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


def coupled_ground_solver_controls():
    import copy
    from types import MethodType
    for candidate in (False,True):
        bank=copy.deepcopy(make_chip().analog_owner.host_bank);bank.externally_owned=False
        if candidate:bank.currents=MethodType(piecewise_currents,bank)
        state=bank.state.copy();pending=bank.pending_charge.copy();drive=bank.drive.copy()
        try:bank.advance(10e-9,[20.]*7,[1]*11)
        except ValueError:pass
        else:raise AssertionError('Supply floor not rejected')
        assert bank.time==0 and np.array_equal(bank.state,state)
        assert np.array_equal(bank.pending_charge,pending) and np.array_equal(bank.drive,drive)
        assert bank.source_energy==bank.resistor_energy==bank.load_energy==bank.driver_energy==bank.internal_energy==0
    rows=[]
    for engine in ('none','rf'):
        baseline,candidate=make_chip(),make_chip()
        host=candidate.analog_owner.host_bank
        host.currents=MethodType(piecewise_currents,host)
        if engine=='rf':
            for chip in (baseline,candidate):chip.configure_resources(engine='rf')
        maximum=0.;phase_error=0.
        for i,word in enumerate((1023,0,341,682)):
            for chip in (baseline,candidate):
                chip.advance(i*4e-9);chip.emitted_return_word(word,chip.time)
                chip.advance((i+1)*4e-9)
            maximum=max(maximum,float(np.max(abs(baseline.analog_owner.host_bank.state-candidate.analog_owner.host_bank.state))),
                abs(baseline.adc_reference.voltage-candidate.adc_reference.voltage))
            phase_error=max(phase_error,float(abs(baseline.rf_pll.output_phase_cycles-candidate.rf_pll.output_phase_cycles)))
        assert maximum<1e-9 and phase_error<1e-9,(maximum,phase_error)
        rows.append(dict(engine=engine,maximum_state_difference_v=maximum,
            maximum_phase_difference_cycles=phase_error))
    return dict(cases=rows,atomic_floor_rejections=2,full_chip_requalification=False,
        scope='Four host launches over 16 ns, inactive/powered RF; no acquired RF payload.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--coupled-ground-solver-check',action='store_true',help='Compare candidate inside coupled chip and check atomic floor rejection')
    modes.add_argument('--ground-solver-check',action='store_true',help='Compare candidate algebraic solver without changing the chip')
    modes.add_argument('--voltage-screen', action='store_true', help='Run voltage/current-bound screen instead of clock capture')
    modes.add_argument('--sized-driver', action='store_true', help='Run clock capture with candidate resistance/charge sizing')
    args=parser.parse_args()
    if args.coupled_ground_solver_check:
        print(json.dumps(coupled_ground_solver_controls(),indent=2));return
    if args.ground_solver_check:
        print(json.dumps(ground_solver_controls(),indent=2));return
    hashes=source_hashes()
    if args.voltage_screen:
        voltage_screen(hashes)
    else:
        capture_screen(hashes, args.sized_driver)


if __name__ == '__main__':
    main()
