"""Report a deliberately limited nominal, unplaced register timing screen."""
import hashlib
import json
import pathlib
import re
root = pathlib.Path(__file__).resolve().parents[3]
project = root / 'projects/programmable_transceiver_platform'
out = root / 'scratch/transceiver-block-fifo-mapping'
stat = json.loads((out / 'stat.json').read_text())['design']
log = (out / 'timing.log').read_text()
assert 'Error:' not in log
slacks = {}
for domain in ('wr_clk', 'rd_clk'):
    section = log.split('DOMAIN_BEGIN ' + domain)[1].split('DOMAIN_END')[0]
    for group in (domain, 'asynchronous'):
        values = []
        for path in section.split('Startpoint:')[1:]:
            if 'Path Group: ' + group + '\n' in path:
                values += [float(x) for x in re.findall(r'([-\d.]+)\s+slack \(', path)]
        if values:
            slacks[domain + ':' + group] = min(values)
    assert domain + ':' + domain in slacks
cells = stat['num_cells_by_type']
assert stat['num_memories'] == 0
ff = sum(n for k, n in cells.items() if '__dff' in k)
assert ff == 707
assert not log.split('ELECTRICAL_BEGIN')[1].split('ELECTRICAL_END')[0].strip()
files = [project / 'rtl/pt_fifo.sv', project / 'rtl/pt_block_fifo.sv',
         project / 'verification/block_fifo_timing.tcl',
         project / 'verification/run_block_fifo_mapping.sh',
         out / 'mapped.v', out / 'stat.json', out / 'timing.log', out / 'library.sha256']
report = dict(pass_number=58, standard_cells=sum(n for k,n in cells.items() if k.startswith('gf180')),
              flip_flops=ff, cell_area_um2=stat['area'], period_ns=25.6,
              same_domain_min_slack_ns=slacks, electrical_violation_rows=0,
              unconstrained_output_endpoints=87,
              scope='TT 25C 3.3V; ideal clocks; no wire RC; register paths only. Data output, IO budgets, CDC, hold, reset distribution and physical implementation not qualified.',
              sha256={str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
(project / 'evidence/block-fifo-mapping.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='sha256'}, indent=2))
