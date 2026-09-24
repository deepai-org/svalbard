"""Shared mapping-report parser; variant timing expectations remain explicit."""
from timing_log import reported_paths

def main(variant):
    if variant not in ('baseline', 'pipe', 'mask', 'rank', 'prefix', 'commit'):
        raise ValueError('Unknown receiver mapping variant')
    suffix = '' if variant == 'baseline' else '_' + variant
    output_suffix = suffix.replace('_', '-')
    positive_setup = variant in ('prefix', 'commit')
    route_suffix = '_prefix' if variant == 'commit' else (suffix if variant in ('mask', 'rank', 'prefix') else '')
    import pathlib, json, re, hashlib
    root = pathlib.Path(__file__).resolve().parents[3]
    p = root / 'projects/programmable_transceiver_platform'
    out = root / f'scratch/transceiver-block-rx{output_suffix}-mapping'
    s = (out / 'timing.log').read_text()
    assert 'Error:' not in s and 'not found' not in s
    stat = json.loads((out / 'stat.json').read_text())['design']
    cases = {}
    for mode in (0, 1):
        paths = {}
        for delay in ('max', 'min'):
            section = s.split(f'PATH_BEGIN {mode} {delay}\n')[1].split('PATH_END')[0]
            found = reported_paths(section)
            paths[delay] = min(found, key=lambda x: x['slack_ns'])
        assert (paths['max']['slack_ns'] > 0 if positive_setup else paths['max']['slack_ns'] < (-8 if variant == 'baseline' else 0))
        cases[mode] = paths
    assert not s.split('ELECTRICAL_BEGIN')[1].split('ELECTRICAL_END')[0].strip()
    assert 'unconstrained endpoints' not in s
    rtl_files = [f'pt_block_rx{suffix}.sv', 'pt_block_header.sv', f'pt_block_route{route_suffix}.sv', 'pt_lane_compact.sv', 'pt_schedule.vh']
    if variant in ('mask', 'rank', 'prefix'):
        rtl_files.append('pt_block_rx_routed.vh')
    files = [p / 'rtl' / f for f in rtl_files] + [p / 'verification' / f for f in (f'block_rx{suffix}_timing.tcl', f'run_block_rx{suffix}_mapping.sh', f'report_block_rx{suffix}_mapping.py')] + [out / f for f in ('mapped.v', 'mapped.json', 'stat.json', 'timing.log', 'library.sha256')]
    files.append(pathlib.Path(__file__).resolve())
    files.append(p / 'verification/run_block_rx_mapping.sh')
    files.append(p / 'verification/block_rx_timing_constraints.tcl')
    files.append(p / 'verification/timing_log.py')
    r = {'pass': {'baseline': 75, 'pipe': 77, 'mask': 79, 'rank': 81, 'prefix': 83, 'commit': 86}[variant], 'status': ('nominal unplaced setup screen passes both modes' if positive_setup else 'setup fails both modes'), 'cell_area_um2': stat['area'], 'flip_flops': sum((n for k, n in stat['num_cells_by_type'].items() if '__dff' in k)), 'paths': cases, 'period_ns': 25.6, 'input_max_delay_ns': 4, 'output_max_delay_ns': 4, 'scope': 'Nominal TT25C3.3V unplaced ideal clocks/no wire RC. No mapped equivalence, queues or physical signoff.', 'sha256': {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
    (p / f'evidence/block-rx{output_suffix}-mapping.json').write_text(json.dumps(r, indent=2) + '\n')
    print(json.dumps({k: v for k, v in r.items() if k != 'sha256'}, indent=2))
