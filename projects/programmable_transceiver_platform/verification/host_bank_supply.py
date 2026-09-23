"""Exploratory switched-resistor host bank with explicit external capacitors.

Decoupling voltages and output-to-board voltages are continuous states. A common
resistive return is algebraic. Rising and falling currents follow their actual
branches rather than becoming identical two-terminal rail charge impulses.
This candidate is not yet connected to IntegratedTransceiverChip or fitted to
native pads. Ideal mutually exclusive pull-up/down controls omit gate energy.
"""
import hashlib
import copy
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

    def currents(self, state, levels):
        """Return ground potential, feed currents, pull-up and pull-down currents."""
        u = state[:self.n];out = state[self.n:]
        up_g = levels/self.pullup_r;down_g = (~levels)/self.pulldown_r
        denominator = 1/self.return_r+np.sum(1/self.feed_r)+np.sum(up_g+down_g)
        ground = (np.sum((self.nominal-u)/self.feed_r)
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
            for f in (Path(__file__), p/'system_model/connected/shared_supply_lifecycle.py')})
    (p/'evidence/host-bank-supply-controls.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    controls()
