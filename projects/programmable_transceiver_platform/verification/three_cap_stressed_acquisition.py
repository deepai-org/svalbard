"""Edge-driven follow-up to exploratory worst-margin loading/component stress."""
import hashlib, json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'system_model/connected'))
from chip_model import P
from three_cap_acquisition_screen import run_acquisition_cases

def main():
    directory = P / 'system_model/connected'
    hashes = {str(p.relative_to(P)): hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob('*.py')}
    source = P / 'evidence/three-cap-sensitivity.json'
    stress = json.loads(source.read_text())
    case = stress['rows'][-1]
    candidate = case['worst_margin_case']
    scales = candidate['scales']
    values = {k: v * scales[k] for k, v in stress['nominal_filter'].items()}
    values['c3'] += case['added_tuning_capacitance_f']
    selection = 'worst_linear_margin_2pf_exploratory_stress'
    output = P / 'evidence/three-cap-stressed-acquisition-screen.json'
    report = dict(status='running', selection=selection, linear_candidate=candidate, ranking_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), filter_values=values, source_sha256=hashes, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), gain_scales={k: scales[k] for k in ('icp', 'kvco')}, cases=[], limitations=['Isolated PLL with held driver rail; not full-chip quality or physical phase-noise qualification.', 'Original divider sequence, seeded frequency noise and lock gates retained.', 'Component and load stress is exploratory, not a PDK corner or yield estimate.', 'Reference-edge phase samples omit inter-edge ripple; startup differs from integrated coarse acquisition.'])

    def save():
        output.write_text(json.dumps(report, indent=2) + '\n')
    save()
    run_acquisition_cases(values, report, save, gain_scales=scales)
    report['source_hashes_match'] = all((hashlib.sha256((P / p).read_bytes()).hexdigest() == h for p, h in hashes.items()))
    report['status'] = 'characterized' if report['source_hashes_match'] else 'invalid_source_change'
    save()
if __name__ == '__main__':
    main()
