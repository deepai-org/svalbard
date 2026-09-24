"""Exploratory switched-resistor host bank with explicit external capacitors.

Decoupling voltages and output-to-board voltages are continuous states. A common
resistive return is algebraic. Rising and falling currents follow their actual
branches rather than becoming identical two-terminal rail charge impulses.
This candidate is not yet connected to IntegratedTransceiverChip or fitted to
native pads. Ideal mutually exclusive pull-up/down controls omit gate energy.
"""
import hashlib
import copy
import argparse
import json
from pathlib import Path
import sys

import numpy as np


class HostBankSupply:
    def __init__(self, nominal_v, feed_r, decap_f, return_r, output_domain,
                 load_cap_f, pullup_r, pulldown_r):
        def vector(values, size):
            a = np.asarray(values, dtype=float)
            if a.shape != (size,) or not np.all(np.isfinite(a)) or np.any(a <= 0):
                raise ValueError('Positive finite circuit vector required')
            return a.copy()
        self.n = len(nominal_v);self.m = len(output_domain)
        if not self.n or not np.isfinite(return_r) or return_r <= 0:
            raise ValueError('Positive return resistance and nonempty supplies required')
        self.nominal = vector(nominal_v, self.n)
        self.feed_r = vector(feed_r, self.n)
        self.decap = vector(decap_f, self.n)
        self.output_domain = np.asarray(output_domain)
        if self.m and (self.output_domain.dtype.kind not in 'iu' or
                       np.any(self.output_domain < 0) or np.any(self.output_domain >= self.n)):
            raise ValueError('Every output needs one physical supply owner')
        self.output_domain = self.output_domain.astype(int)
        self.load_cap = vector(load_cap_f, self.m)
        self.pullup_r = vector(pullup_r, self.m)
        self.pulldown_r = vector(pulldown_r, self.m)
        self.return_r = float(return_r)
        self.cap = np.r_[self.decap, self.load_cap]
        self.state = np.r_[self.nominal, np.zeros(self.m)]
        self.time = 0.;self.initial_energy = self.cap_energy()
        self.source_energy = self.resistor_energy = self.load_energy = 0.
        self._systems = {}

    def levels(self, values):
        a = np.asarray(values)
        if a.shape != (self.m,) or not np.all((a == 0) | (a == 1)):
            raise ValueError('One binary drive per output required')
        return a.astype(bool)

    def currents(self, state, levels, external_return_a=0.):
        """Return ground potential, feed currents, pull-up and pull-down currents."""
        if not np.isfinite(external_return_a) or external_return_a<0:
            raise ValueError("Finite nonnegative external return current required")
        u = state[:self.n];out = state[self.n:]
        up_g = levels/self.pullup_r;down_g = (~levels)/self.pulldown_r
        denominator = 1/self.return_r+np.sum(1/self.feed_r)+np.sum(up_g+down_g)
        ground = (external_return_a+np.sum((self.nominal-u)/self.feed_r)
            -np.sum(up_g*(u[self.output_domain]-out))+np.sum(down_g*out))/denominator
        feed = (self.nominal-u-ground)/self.feed_r
        up = up_g*(u[self.output_domain]+ground-out)
        down = down_g*(out-ground)
        return ground, feed, up, down

    def derivative(self, state, load, levels):
        ground, feed, up, down = self.currents(state, levels)
        return np.r_[(feed-load-np.bincount(self.output_domain, weights=up,
            minlength=self.n))/self.decap, (up-down)/self.load_cap]

    def cap_energy(self):
        return float(.5*np.sum(self.cap*self.state**2))

    def _system(self, levels):
        key = tuple(levels)
        if key not in self._systems:
            count = self.n+self.m;zero = np.zeros(count)
            b = self.derivative(zero, np.zeros(self.n), levels)
            a = np.column_stack([self.derivative(e, np.zeros(self.n), levels)-b
                for e in np.eye(count)])
            root = np.sqrt(self.cap)
            symmetric = root[:, None]*a/root[None, :]
            if not np.allclose(symmetric, symmetric.T, rtol=1e-12, atol=1e-4):
                raise AssertionError('Passive network lost energy symmetry')
            rates, vectors = np.linalg.eigh((symmetric+symmetric.T)/2)
            if np.any(rates >= 0):raise AssertionError('Unstable passive network')
            self._systems[key] = a, b, rates, vectors
        return self._systems[key]

    def advance(self, end, load_current_a, drive):
        """Exact affine propagation and independent branch-energy integrals.

        The caller must split digital changes and changes in held background
        load. No continuous voltage-floor or current-limit qualification is
        implied by this primitive.
        """
        if not np.isfinite(end) or end < self.time:raise ValueError('Nonmonotonic time')
        load = np.asarray(load_current_a, float)
        if load.shape != (self.n,) or not np.all(np.isfinite(load)) or np.any(load < 0):
            raise ValueError('Finite nonnegative held background currents required')
        levels = self.levels(drive);dt = end-self.time
        if not dt:return self.state.copy()
        a, b, rates, vectors = self._system(levels)
        forcing = b-np.r_[load/self.decap, np.zeros(self.m)]
        equilibrium = np.linalg.solve(a, -forcing)
        root = np.sqrt(self.cap)
        modes = vectors/root[:, None]*(vectors.T@(root*(self.state-equilibrium)))[None, :]
        after = equilibrium+modes@np.exp(rates*dt)
        integral = np.expm1(rates*dt)/rates
        sums = rates[:, None]+rates[None, :]
        product_integral = np.expm1(sums*dt)/sums
        def branch(x):
            ground, feed, up, down = self.currents(x, levels)
            return np.r_[feed, ground/self.return_r, up, down]
        steady = branch(equilibrium)
        weights = np.column_stack([branch(equilibrium+v)-steady for v in modes.T])
        integrated_current = steady*dt+weights@integral
        integrated_square = (steady**2*dt+2*steady*(weights@integral)
            +np.einsum('ik,kl,il->i', weights, product_integral, weights))
        resistance = np.r_[self.feed_r, self.return_r, self.pullup_r, self.pulldown_r]
        dissipated = float(resistance@integrated_square)
        if dissipated < -1e-20 or not np.all(np.isfinite(after)):
            raise AssertionError('Invalid passive propagation')
        self.source_energy += float(self.nominal@integrated_current[:self.n])
        self.resistor_energy += dissipated
        self.load_energy += float(load@(equilibrium*dt+modes@integral)[:self.n])
        self.state = after;self.time = end
        return after.copy()

    def energy_residual(self):
        return self.source_energy-self.resistor_energy-self.load_energy-(self.cap_energy()-self.initial_energy)


class LimitedHostBankSupply(HostBankSupply):
    """Current-limited output paths plus finite internal switching-current pulses.

    Edge charge is a pending consumption ledger, not capacitor energy. The
    delivered current draws from the owning local rail and returns to local
    ground. Explicit external output capacitors are charged separately.
    """
    def __init__(self, *args, pullup_limit_a, pulldown_limit_a,
                 rising_charge_c, falling_charge_c, switching_tau_s,
                 minimum_supply_v, **kwargs):
        super().__init__(*args, **kwargs)
        def vector(values, count, positive):
            a = np.asarray(values, float)
            if a.shape != (count,) or not np.all(np.isfinite(a)) or np.any(a < 0) or (positive and np.any(a == 0)):
                raise ValueError('Invalid explicit driver/load bound')
            return a.copy()
        self.up_limit = vector(pullup_limit_a, self.m, True)
        self.down_limit = vector(pulldown_limit_a, self.m, True)
        self.rise_charge = vector(rising_charge_c, self.m, False)
        self.fall_charge = vector(falling_charge_c, self.m, False)
        self.floor = vector(minimum_supply_v, self.n, True)
        if np.any(self.state[:self.n] <= self.floor):raise ValueError('Initial supply below envelope')
        if not np.isfinite(switching_tau_s) or switching_tau_s <= 0:
            raise ValueError('Positive finite switching-current duration required')
        self.switching_tau = float(switching_tau_s)
        self.drive = self.levels([0]*self.m)
        self.pending_charge = np.zeros(self.n)
        self.injected_charge = np.zeros(self.n)
        self.consumed_charge = np.zeros(self.n)
        self.driver_energy = self.internal_energy = 0.

    def currents(self, state, levels, external_return_a=0.):
        from scipy.optimize import brentq
        if not np.isfinite(external_return_a) or external_return_a<0:
            raise ValueError("Finite nonnegative external return current required")
        u = state[:self.n];out = state[self.n:]
        denominator = 1/self.return_r+np.sum(1/self.feed_r)
        center = (external_return_a+np.sum((self.nominal-u)/self.feed_r))/denominator
        radius = np.sum(np.where(levels, self.up_limit, self.down_limit))/denominator
        def branches(g):
            up = np.where(levels, np.clip((u[self.output_domain]+g-out)/self.pullup_r,
                -self.up_limit, self.up_limit), 0.)
            down = np.where(levels, 0., np.clip((out-g)/self.pulldown_r,
                -self.down_limit, self.down_limit))
            return up, down
        def residual(g):
            up, down = branches(g)
            return denominator*(g-center)+np.sum(up)-np.sum(down)
        ground = brentq(residual, center-radius-1e-12, center+radius+1e-12,
            xtol=1e-14, rtol=1e-14)
        up, down = branches(ground)
        return ground, (self.nominal-u-ground)/self.feed_r, up, down

    def internal_current(self, time):
        if not np.isfinite(time) or time < self.time:raise ValueError('Unknown switching-current history')
        return self.pending_charge*np.exp(-(time-self.time)/self.switching_tau)/self.switching_tau

    def advance(self, end, load_current_a, drive, rtol=1e-9, atol=1e-12):
        from scipy.integrate import solve_ivp
        if not np.isfinite(end) or end < self.time:raise ValueError('Nonmonotonic time')
        if getattr(self,'externally_owned',False) and end!=self.time:
            raise ValueError('Host bank must advance through the shared analog owner')
        if not all(np.isfinite(v) and v > 0 for v in (rtol, atol)):
            raise ValueError('Positive numerical tolerances required')
        load = np.asarray(load_current_a, float)
        if load.shape != (self.n,) or not np.all(np.isfinite(load)) or np.any(load < 0):
            raise ValueError('Finite nonnegative background currents required')
        levels = self.levels(drive)
        edge_charge = np.where(levels != self.drive,
            np.where(levels, self.rise_charge, self.fall_charge), 0.)
        injected = np.bincount(self.output_domain, weights=edge_charge, minlength=self.n)
        pending = self.pending_charge+injected
        if not np.all(np.isfinite(pending/self.switching_tau)):
            raise ValueError('Unbounded switching-current pulse')
        if np.any(self.state[:self.n] <= self.floor):raise ValueError('Supply outside envelope')
        dt = end-self.time;size = len(self.state);start = self.time
        scale = max(self.initial_energy, 1e-12)
        energies = np.zeros(5);after = self.state.copy()
        if dt:
            def rhs(t, y):
                x = y[:size];u = x[:self.n];out = x[self.n:]
                internal = pending*np.exp(-(t-start)/self.switching_tau)/self.switching_tau
                ground, feed, up, down = self.currents(x, levels)
                du = (feed-load-internal-np.bincount(self.output_domain, weights=up,
                    minlength=self.n))/self.decap
                dv = (up-down)/self.load_cap
                feed_loss = self.feed_r@(feed**2)+ground**2/self.return_r
                driver_loss = up@(u[self.output_domain]+ground-out)+down@(out-ground)
                return np.r_[du, dv, np.array([self.nominal@feed, feed_loss,
                    u@load, driver_loss, u@internal])/scale]
            def floor_event(t, y):return float(np.min(y[:self.n]-self.floor))
            floor_event.terminal = True;floor_event.direction = -1
            result = solve_ivp(rhs, (start, end), np.r_[after, np.zeros(5)],
                method='Radau', rtol=rtol, atol=atol, events=floor_event)
            if not result.success or result.status == 1 or not np.all(np.isfinite(result.y[:, -1])):
                raise ValueError('Host supply left envelope or solve failed')
            after = result.y[:size, -1];energies = result.y[size:, -1]*scale
            if np.any(after[:self.n] <= self.floor):raise ValueError('Host supply below floor')
        # Commit only after the entire interval is accepted; rejected forecasts
        # do not consume charge, latch bits or partially update rail states.
        fraction = -np.expm1(-dt/self.switching_tau)
        self.injected_charge += injected
        self.consumed_charge += pending*fraction
        self.pending_charge = pending*np.exp(-dt/self.switching_tau)
        self.state = after;self.time = end;self.drive = levels
        self.source_energy += float(energies[0]);self.resistor_energy += float(energies[1])
        self.load_energy += float(energies[2]);self.driver_energy += float(energies[3])
        self.internal_energy += float(energies[4])
        return after.copy()

    def energy_residual(self):
        if getattr(self,'externally_owned',False):raise ValueError('Energy belongs to the shared analog owner')
        return super().energy_residual()-self.driver_energy-self.internal_energy


def limited_controls():
    p = Path(__file__).resolve().parents[1]
    arguments = ([3.3]*7, [2.]*7, [100e-12]*7, .1,
        [1]*5+[2]*6, [10e-12]*11, [100.]*11, [80.]*11)
    background = np.array([.020, .002, .002, 0., 0., .012, .008])
    low = [0]*11;high = [1]*11
    def factory(limit, charge):
        return LimitedHostBankSupply(*arguments, pullup_limit_a=[limit]*11,
            pulldown_limit_a=[limit*1.2]*11, rising_charge_c=[charge]*11,
            falling_charge_c=[charge]*11, switching_tau_s=.5e-9, minimum_supply_v=[2.5]*7)
    linear = HostBankSupply(*arguments);unlimited = factory(10., 0.)
    for end, drive in ((3.2e-9, high), (6.4e-9, low)):
        linear.advance(end, background, drive);unlimited.advance(end, background, drive)
    linear_error = float(np.max(np.abs(linear.state-unlimited.state)))
    assert linear_error < 1e-8, linear_error
    c = factory(.010, 7e-12);c.advance(20e-9, background, low)
    refined = copy.deepcopy(c)
    for end, drive in ((23.2e-9, high), (26.4e-9, low)):
        start = refined.time
        for t in np.linspace(start, end, 9)[1:]:refined.advance(float(t), background, drive)
        c.advance(end, background, drive)
    refinement = float(np.max(np.abs(c.state-refined.state)))
    assert refinement < 1e-7, refinement
    assert np.allclose(c.injected_charge, [0., 70e-12, 84e-12, 0., 0., 0., 0.], rtol=0., atol=1e-25)
    charge_error = float(np.max(np.abs(c.injected_charge-c.consumed_charge-c.pending_charge)))
    assert charge_error < 1e-24, charge_error
    residual = c.energy_residual()
    assert abs(residual) < 1e-17, residual
    assert c.internal_energy > 0 and c.driver_energy > 0
    # A repeated identical word must not charge every pad again.
    injected_before = c.injected_charge.copy()
    c.advance(c.time, background, low)
    assert np.array_equal(c.injected_charge, injected_before)
    snapshot = copy.deepcopy(c.__dict__)
    overload = background.copy();overload[1] = 2.
    try:c.advance(c.time+10e-9, overload, high)
    except ValueError:pass
    else:raise AssertionError('Overload did not reject')
    for key in ('state', 'pending_charge', 'consumed_charge', 'injected_charge', 'drive'):
        assert np.array_equal(getattr(c, key), snapshot[key]), key
    for key in ('time', 'source_energy', 'resistor_energy', 'driver_energy', 'internal_energy', 'load_energy'):
        assert getattr(c, key) == snapshot[key], key
    report = dict(status='controls_passed', integrated_into_chip=False,
        full_chip_closure=False, physical_qualification=False,
        unlimited_comparison_error_v=linear_error, interval_refinement_error_v=refinement,
        charge_residual_c=charge_error, energy_residual_j=residual,
        internal_switching_energy_j=c.internal_energy, driver_dissipation_j=c.driver_energy,
        injected_charge_by_domain_c=c.injected_charge.tolist(),
        repeated_word_does_not_inject_charge=True, overload_rollback_verified=True,
        assumptions=['7 pC per changed output and 0.5 ns exponential duration are hypotheses, not extracted bounds.',
            'Finite internal consumption is separate from external capacitor charging and held background loads.',
            '10/12 mA output limits and 100/80 ohm resistance are control parameters, not an installed native fit.',
            'Events occur at ideal drive changes; propagation delay, current overlap, input-receiver loads and package effects remain open.'],
        source_sha256={str(Path(__file__).relative_to(p)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    (p/'evidence/host-bank-limited-supply-controls.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return report


def coupled_controls(chip_events=False):
    """Check shared analog ownership against the standalone supply equations."""
    p = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(p/'system_model/connected'))
    from shared_supply_lifecycle import DomainSupply
    from limited_coupled_driver import LimitedCoupledDriver
    h = LimitedHostBankSupply([3.3]*7, [2.]*7, [100e-12]*7, .1,
        [1]*5+[2]*6, [10e-12]*11, [100.]*11, [80.]*11,
        pullup_limit_a=[.01]*11, pulldown_limit_a=[.012]*11,
        rising_charge_c=[7e-12]*11, falling_charge_c=[7e-12]*11,
        switching_tau_s=.5e-9, minimum_supply_v=[2.5]*7)
    background = np.array([.020, .002, .002, 0., 0., .012, .008])
    d = DomainSupply(('CORE', 'HOST_A', 'HOST_B', 'WIRE_A', 'WIRE_B', 'RF', 'PLL'),
        [3.3]*7, [2.]*7, [100e-12]*7, .1)
    if chip_events:
        from fast_exclusive_engine import IntegratedTransceiverChip
        rows = []
        for engine in ('rf', 'wire'):
            c = IntegratedTransceiverChip(coupled_analog=True,
                rf_hz_per_v=1e6, wire_hz_per_v=1e5,
                return_charge_per_transition=0., domain_supply=d,
                domain_minimum_v=[2.5]*7, domain_load=lambda t, v:background.copy(),
                host_bank=h)
            c.select_engine(engine);c.advance(10e-9)
            for word in (1023, 0, 31):
                c.emitted_return_word(word, c.time);c.advance(c.time+3.2e-9)
            owner=c.analog_owner;bank=owner.host_bank;domains=owner.domains
            residual=(domains.source_energy_j-domains.feed_loss_j-domains.load_energy_j
                -domains.impulse_energy_j-(bank.cap_energy()-bank.initial_energy))
            assert abs(residual)<1e-17, residual
            assert bank.time==c.time==owner.time
            assert all(pll.time==c.time for pll in (c.rf_pll,c.wire_pll) if pll is not None)
            assert np.max(abs(bank.state[:7]-domains.voltage))<1e-12
            assert np.max(abs(bank.injected_charge-np.array([0,105e-12,91e-12,0,0,0,0])))<1e-24
            assert np.max(abs(bank.injected_charge-bank.consumed_charge-bank.pending_charge))<1e-24
            assert domains.impulse_energy_j==0 and c.return_charge==0
            assert c.clock_supply_delta()==domains.voltage[6]-domains.nominal[6]
            rows.append(dict(engine=engine,energy_residual_j=float(residual),
                voltage_v=domains.voltage.tolist(),feedback_intervals=c.feedback_intervals))
        report=dict(status='passed',cases=rows,full_chip_closure=False,
            physical_qualification=False,scope='19.6 ns startup and three output words in each engine',
            limitations=['No payload throughput or signal-quality qualification.',
                'Exploratory driver, switching charge and background currents.'],
            source_sha256={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest()
                for f in list((p/'system_model/connected').glob('*.py'))+
                         list((p/'system_model/architecture_fast').glob('*.py'))+
                         [Path(__file__).resolve(),p/'verification/fast_exclusive_engine.py',p/'verification/fast_loaded_output.py']})
        (p/'evidence/host-bank-chip-events.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2));return report
    c = LimitedCoupledDriver(domain_supply=d, domain_minimum_v=[2.5]*7,
        domain_load=lambda t, v: background.copy(), host_bank=h)
    c.driver_enabled = False
    maximum_error = 0.
    for end, drive in ((20e-9, [0]*11), (23.2e-9, [1]*11), (26.4e-9, [0]*11)):
        c.host_bank.advance(c.time, np.zeros(7), drive)
        c.advance(end, 0j, rtol=1e-9, atol=1e-12)
        h.advance(end, background, drive)
        maximum_error = max(maximum_error, float(np.max(np.abs(c.host_bank.state-h.state))))
    d = c.domains
    residual = (c.host_bank.cap_energy()-c.host_bank.initial_energy
        -d.source_energy_j+d.feed_loss_j+d.load_energy_j)
    charge_error = float(np.max(np.abs(c.host_bank.injected_charge
        -c.host_bank.consumed_charge-c.host_bank.pending_charge)))
    assert maximum_error < 1e-7, maximum_error
    assert abs(residual) < 1e-17, residual
    assert charge_error < 1e-24, charge_error
    report = dict(status='controls_passed', full_chip_closure=False,
        physical_qualification=False, shared_owner_state_error_v=maximum_error,
        energy_residual_j=residual, charge_residual_c=charge_error,
        limitations=['RF driver disabled for supply-equation comparison.',
            'Does not verify full-chip event hooks, PLL feedback or payload operation.',
            'Driver and internal charge parameters remain exploratory.'],
        source_sha256={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in (Path(__file__).resolve(), p/'system_model/connected/limited_coupled_driver.py',
                      p/'system_model/connected/shared_supply_lifecycle.py')})
    (p/'evidence/host-bank-coupled-supply-controls.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return report


def sampling_screen():
    """Conditional pad-level sampling windows; ideal equal launch delays only."""
    p=Path(__file__).resolve().parents[1]
    rows=[]
    for rate in (250e6,300e6,312.5e6):
        h=LimitedHostBankSupply([3.3]*7,[2.]*7,[100e-12]*7,.1,
            [1]*5+[2]*6,[10e-12]*11,[100.]*11,[80.]*11,
            pullup_limit_a=[.01]*11,pulldown_limit_a=[.012]*11,
            rising_charge_c=[7e-12]*11,falling_charge_c=[7e-12]*11,
            switching_tau_s=.5e-9,minimum_supply_v=[2.5]*7)
        background=np.array([.020,.002,.002,0.,.005,0.,.008])
        h.advance(20e-9,background,[0]*11)
        period=1/rate;phases=np.linspace(0.,period,65)
        windows=[];middle_errors=0;minimum=3.3
        for word in range(24):
            high=word%2==0;drive=[int(high)]*11;start=h.time
            h.advance(start,background,drive)
            wave=[h.state[7:].copy()]
            for dt in phases[1:]:
                h.advance(start+float(dt),background,drive)
                wave.append(h.state[7:].copy());minimum=min(minimum,float(min(h.state[:7])))
            if word<8:continue
            wave=np.asarray(wave)
            good=np.all(wave[:,:10]>=.7*3.3 if high else wave[:,:10]<=.3*3.3,axis=1)
            middle_errors+=int(not good[32])
            changes=np.where((wave[:-1,10]-1.65)*(wave[1:,10]-1.65)<=0)[0]
            if len(changes)!=1 or not good[-1]:
                windows.append(None);continue
            j=int(changes[0]);v0,v1=wave[j:j+2,10]
            crossing=phases[j]+(1.65-v0)*(phases[j+1]-phases[j])/(v1-v0)
            # Take only the terminal contiguous valid interval; grid resolution
            # and a separate 0.2 ns per-side allowance remain explicit.
            last_bad=np.flatnonzero(~good)
            first=int(last_bad[-1]+1) if len(last_bad) else 0
            windows.append((float(phases[first]-crossing+.2e-9),float(period-crossing-.2e-9)))
        valid=all(w is not None for w in windows)
        lower=max(w[0] for w in windows) if valid else None
        upper=min(w[1] for w in windows) if valid else None
        rows.append(dict(word_rate_hz=rate,measured_words=16,
            common_clock_relative_window_s=[lower,upper],
            has_sampled_window=bool(valid and lower<upper),
            midpoint_launch_sample_errors=middle_errors,
            minimum_sampled_supply_v=minimum,phase_grid_s=period/64,
            energy_residual_j=h.energy_residual()))
        assert abs(h.energy_residual())<1e-16
        print(rows[-1],flush=True)
    report=dict(status='screen_completed',cases=rows,physical_qualification=False,
        full_chip_closure=False,assumptions=[
            '10 pF per output, 100/80 ohm paths, 10/12 mA limits, 7 pC internal edge charge and 0.5 ns decay.',
            'Receiver thresholds 0.3/0.7 of 3.3 V and clock threshold 1.65 V are test hypotheses, not an FPGA specification.',
            '0.2 ns allowance at each window edge represents an assumed combined timing margin.',
            'Equal ideal launch delays; delay mismatch, PCB/package impedance, receiver hysteresis and clock jitter omitted.',
            'Synchronous alternating data; 8 warmup and 16 measured words, sampled at 65 points per word.',
            'Grid window is conditional and finite; neither all patterns nor continuous-time eye qualification.'],
        source_sha256={str(Path(__file__).resolve().relative_to(p)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    (p/'evidence/host-bank-sampling-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def controls():
    """Independent nodal KCL/energy, ODE and existing domain-model comparisons."""
    from scipy.integrate import solve_ivp
    p = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(p/'system_model/connected'))
    from shared_supply_lifecycle import DomainSupply
    names = ('CORE', 'HOST_A', 'HOST_B', 'WIRE_A', 'WIRE_B', 'RF', 'PLL')
    background = np.array([.020, .002, .002, 0., 0., .012, .008])
    c = HostBankSupply([3.3]*7, [2.]*7, [100e-12]*7, .1, [], [], [], [])
    d = DomainSupply(names, [3.3]*7, [2.]*7, [100e-12]*7, .1)
    c.advance(2e-9, background, []);d.advance(2e-9, background)
    reduction_error = float(np.max(np.abs(c.state-d.voltage)))
    assert reduction_error < 1e-12, reduction_error

    c = HostBankSupply([3.3]*7, [2.]*7, [100e-12]*7, .1,
        [1]*5+[2]*6, [10e-12]*11, [150.]*11, [100.]*11)
    low = c.levels([0]*11);high = c.levels([1]*11)
    c.advance(20e-9, background, low)
    before = c.state.copy()
    rise_ground = float(c.currents(before, high)[0])
    # Independent MNA: solve the algebraic ground-node equation including
    # capacitor incidence, rather than evaluating currents() as the oracle.
    def independent_rhs(t, x, drive):
        u = x[:7];out = x[7:]
        def at(g):
            feed = (3.3-u-g)/2
            up = np.where(drive, (u[c.output_domain]+g-out)/150, 0.)
            down = np.where(drive, 0., (out-g)/100)
            du = (feed-background-np.bincount(c.output_domain, weights=up, minlength=7))/100e-12
            ground_kcl = g/.1-np.sum(background)-np.sum(100e-12*du)-np.sum(down)
            return ground_kcl, np.r_[du, (up-down)/10e-12]
        k0, _ = at(0.);k1, _ = at(1.)
        return at(-k0/(k1-k0))[1]
    refined = copy.deepcopy(c)
    for t in np.linspace(c.time, c.time+3.2e-9, 33)[1:]:refined.advance(t, background, high)
    ode = solve_ivp(lambda t, x:independent_rhs(t, x, high), (0., 3.2e-9), before,
        method='Radau', rtol=1e-10, atol=1e-12)
    assert ode.success
    c.advance(c.time+3.2e-9, background, high)
    ode_error = float(np.max(np.abs(c.state-ode.y[:, -1])))
    assert ode_error < 1e-8, ode_error
    refinement_error = float(np.max(np.abs(c.state-refined.state)))
    assert refinement_error < 1e-11, refinement_error
    ground, feed, up, down = c.currents(c.state, high)
    derivative = c.derivative(c.state, background, high)
    kcl = ground/.1-np.sum(background)-np.sum(c.decap*derivative[:7])-np.sum(down)
    cap_return = np.sum(feed)-ground/.1-np.sum(c.load_cap*derivative[7:])
    assert max(abs(kcl), abs(cap_return)) < 1e-12
    fall_ground = float(c.currents(c.state, low)[0])
    assert rise_ground < 0 < fall_ground, (rise_ground, fall_ground)
    fall_ode = solve_ivp(lambda t, x:independent_rhs(t, x, low), (0., 3.2e-9), c.state,
        method='Radau', rtol=1e-10, atol=1e-12)
    assert fall_ode.success
    c.advance(c.time+3.2e-9, background, low)
    fall_error = float(np.max(np.abs(c.state-fall_ode.y[:, -1])))
    assert fall_error < 1e-8, fall_error
    residual = c.energy_residual()
    assert abs(residual) < 1e-18, residual
    report = dict(status='controls_passed', integrated_into_chip=False,
        full_chip_closure=False, physical_qualification=False,
        domain_reduction_error_v=reduction_error, independent_ode_error_v=ode_error,
        falling_ode_error_v=fall_error, interval_refinement_error_v=refinement_error,
        ground_kcl_error_a=float(kcl), external_capacitor_return_kcl_error_a=float(cap_return),
        energy_residual_j=residual, rising_edge_initial_ground_v=rise_ground,
        falling_edge_initial_ground_v=fall_ground,
        assumptions=['150 ohm pull-up / 100 ohm pull-down are exploratory, not extracted pad parameters.',
            'Seven 2 ohm feeds, 100 pF local decoupling each, 0.1 ohm common return; eleven 10 pF external outputs.',
            'Ideal exclusive resistive switches omit gate delay, overlap current and internal switching charge.',
            'No package inductance, separate ground paths, substrate coupling or voltage-floor envelope qualification.',
            'Board sources may absorb regenerative current; regulator behavior is not qualified.'],
        source_sha256={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in (Path(__file__).resolve(), p/'system_model/connected/shared_supply_lifecycle.py')})
    (p/'evidence/host-bank-supply-controls.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limited-controls', action='store_true')
    parser.add_argument('--coupled-controls', action='store_true')
    parser.add_argument('--chip-events', action='store_true')
    parser.add_argument('--sampling-screen', action='store_true')
    args = parser.parse_args()
    sampling_screen() if args.sampling_screen else coupled_controls(chip_events=True) if args.chip_events else coupled_controls() if args.coupled_controls else limited_controls() if args.limited_controls else controls()
