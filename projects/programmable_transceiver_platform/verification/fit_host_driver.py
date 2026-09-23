"""Characterize a simple delayed-RC driver against retained native-pad traces.

This deliberately reports model error rather than promoting fitted parameters
to the full-chip supply model. Supply current and rail dependence remain open.
"""
import hashlib
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
        output[mask] = target+(value-target)*np.exp(-(times[mask]-previous)/tau)
        value = target+(value-target)*np.exp(-(end-previous)/tau)
        previous = end;level = new
    return output


def errors(array, output_col, predicted, begin_ns, end_ns=None):
    selected = array[:, 0] >= begin_ns*1e-9
    if end_ns is not None:selected &= array[:, 0] < end_ns*1e-9
    delta = predicted[selected]-array[selected, output_col]
    if not len(delta):raise ValueError('Empty driver evaluation window')
    return dict(samples=len(delta), rms_v=float(np.sqrt(np.mean(delta**2))),
        maximum_absolute_v=float(np.max(np.abs(delta))))


def main():
    bank_evidence = P/'evidence/native-host-bank-rc-screen.json'
    bank = json.loads(bank_evidence.read_text())
    archive = ROOT/bank['archive_path']
    if hashlib.sha256(archive.read_bytes()).hexdigest() != bank['archive_sha256']:
        raise ValueError('Bank archive identity mismatch')
    row = next(r for r in bank['cases'] if r['case']=='ideal_bank')
    training = waveform(archive, row['case'], row)
    selected = (training[:, 0] >= 4e-9) & (training[:, 0] < 17e-9)
    fit = least_squares(lambda parameters:(predict(training, 1, 10., 3.3, parameters)-training[:, 7])[selected],
        [120., 80., 2., 2.], bounds=([5., 5., 0., 0.], [300., 300., 3., 3.]))
    if not fit.success:raise RuntimeError(fit.message)
    prediction = predict(training, 1, 10., 3.3, fit.x)
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
        integrated_into_chip=False, full_chip_closure=False,
        parameters=dict(pullup_r_ohm=float(fit.x[0]), pulldown_r_ohm=float(fit.x[1]),
            rising_delay_ns=float(fit.x[2]), falling_delay_ns=float(fit.x[3])),
        training=errors(training, 7, prediction, 4., 17.), held_out=cases,
        limitations=['Only ideal-supply output voltage is fitted; no supply-current or ground-current fit.',
            'Voltage dependence, finite gate slew, overlap/internal current and nonideal-feed behavior are not qualified.',
            'Do not install these parameters merely because optimization converged; retain waveform error as model uncertainty.'],
        source_sha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in (Path(__file__), bank_evidence, weak_evidence)},
        archive_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in (archive, weak_archive)})
    (P/'evidence/host-driver-fit.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':main()
