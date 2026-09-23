"""Characterize a simple delayed-RC driver against retained native-pad traces.

This deliberately reports model error rather than promoting fitted parameters
to the full-chip supply model. Supply current and rail dependence remain open.
"""
import hashlib
import argparse
import io
import json
from pathlib import Path
import tarfile

import numpy as np
from scipy.optimize import least_squares

P = Path(__file__).resolve().parents[1]
ROOT = P.parents[1]


def waveform(archive, case, row):
    with tarfile.open(archive) as bundle:
        raw = bundle.extractfile(case+'/wave.txt').read()
        if hashlib.sha256(raw).hexdigest() != row['waveform_sha256']:
            raise ValueError('Native waveform identity mismatch')
        deck = bundle.extractfile(case+'/tb.spice').read()
        if hashlib.sha256(deck).hexdigest() != row['deck_sha256']:
            raise ValueError('Native deck identity mismatch')
    return np.loadtxt(io.BytesIO(raw), skiprows=1)


def predict(array, input_col, capacitance_pf, supply_v, parameters):
    times = array[:, 0]*1e9;input_v = array[:, input_col]
    indices = np.flatnonzero((input_v[:-1] < 1.65) != (input_v[1:] < 1.65))
    edges = times[indices]+(1.65-input_v[indices])*(times[indices+1]-times[indices])/(input_v[indices+1]-input_v[indices])
    rise = input_v[indices+1] > input_v[indices]
    # Parameters are R in ohms and transport delay in ns. The threshold here
    # identifies testbench gate events; it is not an FPGA input specification.
    changes = edges+np.where(rise, parameters[2], parameters[3])
    if np.any(np.diff(changes) <= 0):raise ValueError('Delayed drive events reordered')
    output = np.zeros(len(times));previous = 0.;value = 0.;level = False
    for end, new in list(zip(changes, rise))+[(times[-1]+10., False)]:
        tau = parameters[0 if level else 1]*capacitance_pf*.001
        target = supply_v if level else 0.
        mask = (times >= previous) & (times < end)
        def evolve(dt):
            if len(parameters) == 4:
                return target+(value-target)*np.exp(-dt/tau)
            # I = min(Ilimit, |Vtarget-Vout|/R). Capacitor voltage is
            # continuous at the linear-ramp/exponential boundary.
            limit_ma = parameters[4 if level else 5]
            boundary_v = limit_ma*.001*parameters[0 if level else 1]
            distance = abs(value-target)
            rate = limit_ma/capacitance_pf  # V/ns
            ramp_ns = max(0., (distance-boundary_v)/rate)
            remaining = np.where(dt < ramp_ns, distance-rate*dt,
                min(distance, boundary_v)*np.exp(-np.maximum(0., dt-ramp_ns)/tau))
            return target+np.sign(value-target)*remaining
        output[mask] = evolve(times[mask]-previous)
        value = float(evolve(end-previous))
        previous = end;level = new
    return output


def errors(array, output_col, predicted, begin_ns, end_ns=None):
    selected = array[:, 0] >= begin_ns*1e-9
    if end_ns is not None:selected &= array[:, 0] < end_ns*1e-9
    delta = predicted[selected]-array[selected, output_col]
    if not len(delta):raise ValueError('Empty driver evaluation window')
    return dict(samples=len(delta), rms_v=float(np.sqrt(np.mean(delta**2))),
        maximum_absolute_v=float(np.max(np.abs(delta))))


def limited_controls():
    from scipy.integrate import solve_ivp
    times = np.linspace(0., 10e-9, 2001)
    inputs = np.interp(times, [0., 1e-9, 1.2e-9, 5e-9, 5.2e-9, 10e-9],
        [0., 0., 3.3, 3.3, 0., 0.])
    predicted = predict(np.column_stack([times, inputs]), 1, 10., 3.3,
        [100., 80., .3, .4, 10., 12.])
    observed = np.zeros(len(times));value = [0.]
    for start, end, high in ((0., 1.4e-9, False), (1.4e-9, 5.5e-9, True), (5.5e-9, 10e-9, False)):
        def rhs(t, y):
            current = min(.010, max(0., (3.3-y[0])/100)) if high else -min(.012, max(0., y[0]/80))
            return [current/10e-12]
        solve = solve_ivp(rhs, (start, end), value, dense_output=True,
            rtol=1e-10, atol=1e-12, max_step=10e-12)
        if not solve.success:raise AssertionError(solve.message)
        selected = (times >= start) & (times <= end)
        observed[selected] = solve.sol(times[selected])[0]
        value = solve.y[:, -1]
    error = float(np.max(np.abs(predicted-observed)))
    assert error < 1e-7, error
    return dict(maximum_independent_current_ode_error_v=error)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--current-limited', action='store_true')
    args = parser.parse_args()
    bank_evidence = P/'evidence/native-host-bank-rc-screen.json'
    bank = json.loads(bank_evidence.read_text())
    archive = ROOT/bank['archive_path']
    if hashlib.sha256(archive.read_bytes()).hexdigest() != bank['archive_sha256']:
        raise ValueError('Bank archive identity mismatch')
    row = next(r for r in bank['cases'] if r['case']=='ideal_bank')
    training = waveform(archive, row['case'], row)
    selected = (training[:, 0] >= 4e-9) & (training[:, 0] < 17e-9)
    initial = [120., 80., 2., 2.];lower = [5., 5., 0., 0.];upper = [300., 300., 3., 3.]
    if args.current_limited:
        initial += [15., 20.];lower += [1., 1.];upper += [100., 100.]
    fit = least_squares(lambda parameters:(predict(training, 1, 10., 3.3, parameters)-training[:, 7])[selected],
        initial, bounds=(lower, upper))
    if not fit.success:raise RuntimeError(fit.message)
    prediction = predict(training, 1, 10., 3.3, fit.x)
    # Two held-out periods. VD supplies all eleven output stages plus the
    # explicitly imposed 44 mA background; VC supplies pre-drivers separately.
    window = (training[:, 0] >= 18e-9) & (training[:, 0] <= 30.8e-9)
    times = training[window, 0]
    measured_per_pad = (-training[window, 5]-.044)/11
    charging = 10e-12*np.maximum(0., np.gradient(prediction, training[:, 0]))[window]
    native_charging = 10e-12*np.maximum(0., np.gradient(training[:, 7], training[:, 0]))[window]
    def charge(values):return float(np.sum((values[1:]+values[:-1])*.5*np.diff(times)))
    measured_charge = charge(measured_per_pad);charging_charge = charge(charging)
    current_diagnostic = dict(begin_s=float(times[0]), end_s=float(times[-1]),
        measured_driver_supply_charge_per_pad_c=measured_charge,
        predicted_external_capacitor_charging_charge_per_pad_c=charging_charge,
        native_external_capacitor_positive_charge_per_pad_c=charge(native_charging),
        unaccounted_charge_per_pad_c=measured_charge-charging_charge,
        unaccounted_average_current_per_pad_a=(measured_charge-charging_charge)/(times[-1]-times[0]),
        scope='Diagnostic residual includes internal pad charge, bias and voltage-model error; not an extracted internal-current law. Core pre-driver current is separate.')
    cases = [dict(case='10pf_bank_later_cycles', fitting_data=False,
        **errors(training, 7, prediction, 18.))]
    # Unused 8 pF data is a load-change control, not a second fitting window.
    weak_evidence = P/'evidence/weak-drive-screen.json'
    weak = json.loads(weak_evidence.read_text())
    weak_archive = ROOT/'scratch/transceiver-weak-drive-waveforms.tar.gz'
    row = next(r for r in weak['results'] if r['case']=='typical_25_8_alternating_drive8')
    changed_load = waveform(weak_archive, row['case'], row)
    cases.append(dict(case='8pf_pair_data', fitting_data=False,
        **errors(changed_load, 3, predict(changed_load, 1, 8., 3.3, fit.x), 45.6, 109.6)))
    report = dict(status='characterization_completed', physical_qualification=False,
        model='current_limited_resistor' if args.current_limited else 'linear_resistor',
        integrated_into_chip=False, full_chip_closure=False,
        parameters=dict(pullup_r_ohm=float(fit.x[0]), pulldown_r_ohm=float(fit.x[1]),
            rising_delay_ns=float(fit.x[2]), falling_delay_ns=float(fit.x[3])),
        training=errors(training, 7, prediction, 4., 17.), held_out=cases,
        supply_current_diagnostic=current_diagnostic,
        limitations=['Only ideal-supply output voltage is fitted; no supply-current or ground-current fit.',
            'Voltage dependence, finite gate slew, overlap/internal current and nonideal-feed behavior are not qualified.',
            'Do not install these parameters merely because optimization converged; retain waveform error as model uncertainty.'],
        source_sha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in (Path(__file__), bank_evidence, weak_evidence)},
        archive_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in (archive, weak_archive)})
    if args.current_limited:
        report['parameters'].update(pullup_limit_ma=float(fit.x[4]), pulldown_limit_ma=float(fit.x[5]))
        report['controls']=limited_controls()
    filename = 'host-driver-current-limited-fit.json' if args.current_limited else 'host-driver-fit.json'
    (P/'evidence'/filename).write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':main()
