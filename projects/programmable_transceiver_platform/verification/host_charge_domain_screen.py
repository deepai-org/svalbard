"""Finite host charging demand on the candidate seven-domain RC network.

This is an architectural load sensitivity screen, not a pad-driver or package
simulation. The demanded output swing and edge duration are hypotheses.
"""
import hashlib
import io
import json
import math
import sys
import tarfile
from pathlib import Path

import numpy as np

P = Path(__file__).resolve().parents[1]
D = P / 'system_model/connected'
sys.path.insert(0, str(D))
from shared_supply_lifecycle import DomainSupply

NAMES = ('CORE', 'HOST_A', 'HOST_B', 'WIRE_A', 'WIRE_B', 'RF', 'PLL')
BACKGROUND = np.array([.020, .002, .002, 0., 0., .012, .008])


def native_trace_audit():
    """Retained transistor traces constrain charge scale, not rail feedback."""
    archive = P.parents[1]/'scratch/transceiver-weak-drive-waveforms.tar.gz'
    evidence = P/'evidence/weak-drive-screen.json'
    retained = json.loads(evidence.read_text())
    cases = []
    with tarfile.open(archive, 'r:gz') as bundle:
        for record in retained['results']:
            if record['pattern'] != 'alternating':
                continue
            contents = {}
            for name, key in (('wave.txt', 'waveform_sha256'), ('tb.spice', 'deck_sha256'), ('run.log', 'log_sha256')):
                content = bundle.extractfile(record['case']+'/'+name).read()
                # The retained runner hashes read_text().encode() for logs;
                # reproduce its universal-newline handling of progress CRs.
                hashed = content.decode().replace('\r\n', '\n').replace('\r', '\n').encode() if name == 'run.log' else content
                if hashlib.sha256(hashed).hexdigest() != record[key]:
                    raise ValueError('Retained native-pad artifact hash mismatch: '+name)
                contents[name] = content
            waveform = np.loadtxt(io.BytesIO(contents['wave.txt']), skiprows=1)
            if waveform.shape[1] != 7 or np.any(np.diff(waveform[:, 0]) <= 0):
                raise ValueError('Unexpected native-pad waveform format')
            # Same settled 20-bit measurement window as run_gpio_transient.py.
            selected = waveform[(waveform[:, 0] >= 45.6e-9) & (waveform[:, 0] <= 109.6e-9)]
            times = selected[:, 0]
            currents = -selected[:, 5]
            dt = np.diff(times)
            charge = float(np.sum((currents[1:]+currents[:-1])*.5*dt))
            average = charge/(times[-1]-times[0])
            if abs(average-record['two_pad_dvdd_average_a']) > 1e-12:
                raise ValueError('Retained native current measurement not reproduced')
            rising = sum(int(np.count_nonzero((selected[:-1, col] < 1.65) &
                (selected[1:, col] >= 1.65))) for col in (3, 4))
            if rising != 20:
                raise ValueError('Unexpected output rise count in native window')
            # A frozen ideal-supply trace is only a forcing sensitivity model.
            # Scaling a pair by 2.5 / 3 does not establish five/six-pin SSO.
            supply = DomainSupply(NAMES, [3.3]*7, [2.]*7, [100e-12]*7, .1)
            mean = BACKGROUND.copy();mean[1:3] += np.array([2.5, 3.])*average
            supply.voltage = supply.steady(mean);supply.time = float(times[0])
            initial_energy = .5*np.sum(supply.c*supply.voltage**2)
            minimum = np.full(7, np.inf)
            for i, time in enumerate(times[1:]):
                load = BACKGROUND.copy()
                load[1:3] += np.array([2.5, 3.])*max(0., (currents[i]+currents[i+1])/2)
                voltage = supply.advance(float(time), load)
                if time >= times[0]+12.8e-9:
                    minimum = np.minimum(minimum, voltage)
            residual = (supply.source_energy_j-supply.feed_loss_j-supply.load_energy_j
                -.5*np.sum(supply.c*supply.voltage**2)+initial_energy)
            assert abs(residual) < 1e-18, residual
            cases.append(dict(case=record['case'], load_pf=record['external_lumped_capacitance_pf_per_output'],
                artifact_hashes_verified=True, two_pad_average_a=average,
                two_pad_peak_a=float(np.max(currents)), output_rises=rising,
                total_supply_charge_c=charge,
                average_supply_charge_per_output_rise_c=charge/rising,
                ratio_to_50fc_fixture=charge/rising/50e-15,
                replicated_pair_rail_minimum_v=minimum.tolist(),
                replay_energy_residual_j=float(residual),
                negative_current_clipped=bool(np.any(currents < 0)),
                scope='Supply charge includes internal current and bias; not an isolated transition law. Frozen ideal-supply pair replay excludes voltage feedback and true bank interaction.'))
    return dict(archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(), cases=cases)


def screen(load_pf, edge_ns, samples=128, common_return=.1):
    supply = DomainSupply(NAMES, [3.3]*7, [2.]*7, [100e-12]*7, common_return)
    # Begin at the explicit DC operating point, not uncharged/nominal rails.
    supply.voltage = supply.steady(BACKGROUND)
    initial = supply.voltage.copy()
    width = edge_ns*1e-9
    charge = np.zeros(7)
    charge[1:3] = np.array([5, 6])*load_pf*1e-12*3.3
    pulse = charge/width
    minimum = initial.copy()
    min_times = np.zeros(7)
    initial_energy = .5*np.sum(supply.c*initial**2)
    for end, current in ((width, BACKGROUND+pulse), (width+5e-9, BACKGROUND)):
        start = supply.time
        for t in np.linspace(start, end, samples+1)[1:]:
            voltage = supply.advance(float(t), current)
            improved = voltage < minimum
            min_times[improved] = t
            minimum = np.minimum(minimum, voltage)
    residual = (supply.source_energy_j-supply.feed_loss_j-supply.load_energy_j
                -.5*np.sum(supply.c*supply.voltage**2)+initial_energy)
    assert abs(residual) < 1e-18, residual
    return dict(load_pf=load_pf, edge_ns=edge_ns,
        charge_per_rising_output_c=load_pf*1e-12*3.3,
        ratio_to_50fc_fixture=load_pf*1e-12*3.3/50e-15,
        group_charge_c=charge.tolist(), added_pulse_current_a=pulse.tolist(),
        initial_voltage_v=initial.tolist(), minimum_voltage_v=minimum.tolist(),
        minimum_time_s=min_times.tolist(), energy_residual_j=float(residual),
        above_2p5v_model_floor=bool(np.all(minimum>2.5)),
        above_95_percent_nominal=bool(np.all(minimum>3.3*.95)))


def main():
    cases = [screen(load, edge) for load in (5., 10.)
             for edge in (.25, .5, 1., 2.)]
    # The uncoupled scalar solution checks both integrated pulse charge and the
    # finite edge-time response without using the matrix propagator as oracle.
    scalar = screen(10., 1., common_return=0.)
    expected = 3.3-2*.002-2*(6*10e-12*3.3/1e-9)*(1-math.exp(-1e-9/(2*100e-12)))
    scalar_error = abs(scalar['minimum_voltage_v'][2]-expected)
    assert scalar_error < 1e-12, scalar_error
    refined = [screen(row['load_pf'], row['edge_ns'], samples=256) for row in cases]
    refinement = max(float(np.max(np.abs(np.array(a['minimum_voltage_v'])-
        b['minimum_voltage_v']))) for a, b in zip(cases, refined))
    assert refinement < .001, refinement
    # A sufficiently demanding edge must not be silently treated as qualified.
    assert any(not row['above_2p5v_model_floor'] for row in cases)
    report = dict(status='screen_completed', full_chip_closure=False,
        physical_qualification=False, names=NAMES,
        assumptions=dict(supply_v=3.3, feed_r_ohm=2., local_capacitance_f=100e-12,
            common_return_r_ohm=.1, background_current_a=BACKGROUND.tolist(),
            simultaneous_rising_outputs=dict(HOST_A=5, HOST_B=6),
            pulse_shape='constant current over the declared edge duration'),
        controls=dict(scalar_voltage_error_v=scalar_error,
            minimum_sampling_refinement_v=refinement,
            below_floor_case_detected=True), cases=cases,
        native_pad_trace_audit=native_trace_audit(),
        limitations=[
            'One isolated simultaneous rising edge, not sustained bank traffic or average-current qualification.',
            'Q=Cload*3.3V is the charge demanded by the target swing; an actual driver may slow or lose swing as rails sag.',
            'The former 20 mA host backgrounds are replaced by assumed 2 mA idle loads; no 50 fC event is added again.',
            'Other backgrounds remain illustrative. Internal pad current, input switching, falling-edge return current, package inductance and substrate coupling are absent.',
            'The 95% voltage threshold is a sensitivity indicator, not a selected chip operating specification.',
            'Voltage-floor failures reject these load/edge/PDN combinations, not GF180 or the architecture as a whole.'],
        source_sha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in (Path(__file__), D/'shared_supply_lifecycle.py')})
    (P/'evidence/host-charge-domain-screen.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(controls=report['controls'], cases=[dict(load_pf=r['load_pf'],
        edge_ns=r['edge_ns'], host_b_min_v=r['minimum_voltage_v'][2],
        pll_min_v=r['minimum_voltage_v'][6], above_floor=r['above_2p5v_model_floor'])
        for r in cases]), indent=2))


if __name__ == '__main__':
    main()
