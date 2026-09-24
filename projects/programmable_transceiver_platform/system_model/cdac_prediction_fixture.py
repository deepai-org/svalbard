"""Shared independent waveform comparison; electrical response models stay separate."""
import hashlib
import numpy as np


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prediction_metrics(t, predicted, observed):
    metrics = {}
    for mode, weight in [('differential', np.array([1.0, -1.0])), ('common_mode', np.array([0.5, 0.5]))]:
        x = predicted @ weight
        y = observed @ weight
        error = x - y
        metrics[mode] = dict(predicted_peak_v=float(max(abs(x))), observed_peak_v=float(max(abs(y))), max_error_v=float(max(abs(error))), time_weighted_rms_error_v=float(np.sqrt(np.trapezoid(error ** 2, t) / (t[-1] - t[0]))))
    return metrics

def compare_prediction(d, R, response):
    arrays = {}
    for name, folder in [('adc-kickback-fine-clamped.json', 'transceiver-adc-kickback-fine'), ('adc-cdac-kickback.json', 'transceiver-adc-cdac-kickback')]:
        for case in d[name]['cases']:
            if abs(case['differential_v']) != 0.001:
                continue
            p = R / 'scratch' / folder / (case['name'] + '.dat')
            assert sha(p) == case['artifacts_sha256']['.dat']
            arrays[name, case['differential_v'], case['clocked']] = np.loadtxt(p, skiprows=1)
    rows = []
    for diff in [-0.001, 0.001]:
        a = arrays['adc-kickback-fine-clamped.json', diff, True]
        b = arrays['adc-kickback-fine-clamped.json', diff, False]
        f = arrays['adc-cdac-kickback.json', diff, True]
        g = arrays['adc-cdac-kickback.json', diff, False]
        t = np.linspace(2e-09, 4.9e-09, 290001)
        current = np.column_stack([np.interp(t, a[:, 0], a[:, k]) - np.interp(t, b[:, 0], b[:, k]) for k in [1, 2]])
        predicted = response(current, t[1] - t[0])
        coarse = response(current[::2], t[2] - t[0])
        refinement = float(np.max(abs(coarse - predicted[::2])))
        observed = np.column_stack([np.interp(t, f[:, 0], f[:, k]) - np.interp(t, g[:, 0], g[:, k]) for k in [1, 2]])
        metrics = prediction_metrics(t, predicted, observed)
        rows.append(dict(input_differential_v=diff, metrics=metrics, step_refinement_max_port_difference_v=refinement))
    return rows
