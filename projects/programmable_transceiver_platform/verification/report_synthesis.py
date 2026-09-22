"""Report actual mapped area without confusing it with placed/timed area."""
import hashlib
import json
from pathlib import Path
import sys

project = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1])
stat = json.loads((out / 'mapped-stat.json').read_text())
module = stat['modules']['\\pt_digital']
cells = module['num_cells_by_type']
unknown = [name for name in cells if not name.startswith('gf180mcu_fd_sc_mcu7t5v0__') and name != '$scopeinfo']
if unknown or module['num_memories'] or module['num_processes']:
    raise SystemExit(f'Incomplete technology mapping: {unknown}')
contract = json.loads((project / 'spec/contract.json').read_text())
budget = sum(contract['area_um2'][k] for k in ('digital', 'memory'))
area = module['area']
source_files = sorted((project / 'rtl').glob('*')) + [project / 'verification/synthesis_container.sh']
report = {
    'scope': 'Nominal TT 25C 3.3V standard-cell mapping area; no STA, placement or power qualification',
    'tool': stat['creator'],
    'library_sha256': (out / 'library.sha256').read_text().split()[0],
    'source_sha256': {str(p.relative_to(project)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files},
    'mapped_netlist_sha256': hashlib.sha256((out / 'pt_digital_mapped.v').read_bytes()).hexdigest(),
    'physical_cell_count': sum(n for k,n in cells.items() if k != '$scopeinfo'),
    'flip_flop_count': sum(n for k,n in cells.items() if '__dff' in k),
    'cell_area_um2': area,
    'sequential_cell_area_um2': module['sequential_area'],
    'combined_digital_memory_allocation_um2': budget,
    'minimum_utilization_to_fit_before_physical_overhead': area / budget,
    'illustrative_utilization_sensitivity_not_proven_bounds': [
        {'utilization': u, 'required_region_um2': area/u, 'headroom_um2': budget-area/u}
        for u in (0.35, 0.5, 0.65)
    ],
    'limitations': [
        'No timing target supplied to ABC: area screen cannot establish the 3.2ns host word period.',
        'No clock tree, hold fixes, routing congestion, tap/filler/decap cells, level shifters or physical macro interfaces included.',
        'Memory arrays mapped to flip-flops and muxes; no SRAM assumed.',
        'Mapped netlist has not undergone formal equivalence or gate-level simulation.',
        'Operating voltage is a mapping choice, not a frozen or qualified operating envelope.',
        'No power or CORE supply-current estimate; clocking thousands of flip-flops remains an open concern.'
    ],
    'status': 'area estimate obtained; physical fit and timing unproven'
}
if (out / 'buffered.report.json').exists():
    report['buffering_transformation'] = json.loads((out / 'buffered.report.json').read_text())
    report['buffering_script_sha256'] = hashlib.sha256((project / 'verification/buffer_netlist.py').read_bytes()).hexdigest()
if (out / 'mapping-options.json').exists():
    report['mapping_options'] = json.loads((out / 'mapping-options.json').read_text())
    if report['mapping_options']['abc_delay_target_ps'] is not None:
        report['limitations'][0] = 'ABC global delay target supplied; this is not a multi-clock STA constraint, timing closure, or allowance for clock-to-Q/setup/skew.'
(out / 'area-screen.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('physical_cell_count','flip_flop_count','cell_area_um2','status')}, indent=2))
