"""Apply independently measured nominal AC/DC coefficients to the new amplitude.

This diagnostic was specified after the validation waveform completed. It is
not one of the pre-registered frozen fits, and it does not fit that waveform.
"""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

P = Path(__file__).resolve().parents[1]
R = P.parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    # Fresh parent gates validate raw artifacts, PDK identity and frozen models.
    subprocess.run([sys.executable, str(P/'system_model/reference_ac_dc_charge_prediction.py')], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, str(P/'verification/score_reference_charge_validation.py')], check=True,
                   stdout=subprocess.DEVNULL)
    paths = {name:P/'evidence'/name for name in (
        'reference-ac-dc-charge-prediction.json', 'reference-ac-charge-prediction.json',
        'reference-charge-validation.json')}
    before = {name:sha(path) for name,path in paths.items()}
    reports = {name:json.loads(path.read_text()) for name,path in paths.items()}
    model = reports['reference-ac-dc-charge-prediction.json']
    ac = reports['reference-ac-charge-prediction.json']
    validation = reports['reference-charge-validation.json']
    coefficients = {}
    for rail in ('xhigh', 'xlow'):
        dc_row, = [r for r in model['summaries'] if r['rail'] == rail]
        ac_row, = [r for r in ac['summaries'] if r['rail'] == rail]
        coefficients[rail] = dict(drain_derivative_f=ac_row['drain_derivative_f'],
            gate_derivative_f=ac_row['gate_derivative_f'],
            excess_current_a=dc_row['nominal_excess_current_a'])
    rows = []
    for row in validation['rows']:
        c = coefficients[row['rail']]
        dt = {'preclock': .2e-9, 'switching': 1.1e-9}[row['window']]
        ac_charge = c['drain_derivative_f']*row['drain_delta_v']+c['gate_derivative_f']*row['gate_delta_v']
        predicted = ac_charge+c['excess_current_a']*dt
        rows.append(dict(row, ac_prediction_c=ac_charge,
            ac_error_c=ac_charge-row['observed_charge_c'], ac_dc_prediction_c=predicted,
            ac_dc_error_c=predicted-row['observed_charge_c']))
    assert len(rows) == len({(r['rail'],r['hold_ns'],r['bit'],r['window']) for r in rows}) == 96
    summaries = []
    for rail in coefficients:
        group = [r for r in rows if r['rail'] == rail]
        metrics = {}
        for key in ('constant_error_c', 'two_terminal_error_c', 'ac_error_c', 'ac_dc_error_c'):
            errors = [r[key] for r in group]
            metrics[key] = dict(maximum_abs_c=max(map(abs,errors)),
                               rms_c=math.sqrt(sum(e*e for e in errors)/len(errors)))
        worst = max(group, key=lambda r:abs(r['ac_dc_error_c']))
        summaries.append(dict(rail=rail, metrics=metrics,
            worst_window={key:worst[key] for key in ('hold_ns','bit','window','ac_dc_error_c')},
            max_full_kcl_residual_c=max(abs(r['full_terminal_kcl_residual_c']) for r in group)))
    assert before == {name:sha(path) for name,path in paths.items()}
    report = dict(coefficients=coefficients, summaries=summaries, rows=rows,
        source_hashes=dict(before, **{Path(__file__).name:sha(Path(__file__))}),
        coefficients_fitted_to_validation=False, preregistered_comparator=False,
        physical_qualification=False, limitations=[
            'Post-completion diagnostic with independent AC/DC coefficients; not a blind pre-registered comparison.',
            'Measured endpoint voltages are inputs; no autonomous rail or converter prediction.',
            'Nominal DC current and AC derivatives omit drain/gate bias dependence.',
            'No error acceptance budget or silicon/corner qualification is established.'])
    (P/'evidence/reference-ac-dc-validation.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summaries,indent=2))

if __name__ == '__main__':
    main()
