"""Report a deliberately limited nominal, unplaced register timing screen."""
import argparse
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
parser=argparse.ArgumentParser()
parser.add_argument('--lib',type=pathlib.Path,help='Optional original mapping Liberty for clock-pin-only load accounting')
args=parser.parse_args()
if args.lib:
    library=args.lib.read_text()
    digest=hashlib.sha256(args.lib.read_bytes()).hexdigest()
    assert digest==(out/'library.sha256').read_text().split()[0]
    assert re.search(r'capacitive_load_unit\(1,\s*pf\)',library)
    mapped=json.loads((out/'mapped.json').read_text())['modules']['pt_block_fifo']
    cap={};counts={'wr_clk':{},'rd_clk':{}}
    for cell in mapped['cells'].values():
        if 'CLK' not in cell.get('connections',{}):continue
        kind=cell['type']
        if kind not in cap:
            start=library.index('cell('+kind+')');end=library.find('\n  cell(',start+1)
            body=library[start:end if end!=-1 else len(library)]
            pin=body[body.index('pin(CLK)'):]
            cap[kind]=float(re.search(r'capacitance\s*:\s*([0-9.]+)',pin)[1])*1e-12
        domains=[name for name in counts if cell['connections']['CLK']==mapped['ports'][name]['bits']]
        assert len(domains)==1,'Clock connection must be traced before accounting'
        domain=counts[domains[0]];domain[kind]=domain.get(kind,0)+1
    assert sum(sum(c.values()) for c in counts.values())==ff
    capacitance={name:sum(cap[k]*n for k,n in c.items()) for name,c in counts.items()}
    rows=[]
    for word_hz in (250e6,312.5e6):
        clocks={'wr_clk':word_hz/8,'rd_clk':40e6}
        charge={name:c*3.3 for name,c in capacitance.items()}
        current=sum(charge[name]*clocks[name] for name in clocks)
        rows.append(dict(host_word_hz=word_hz,clock_hz=clocks,charge_per_rising_edge_c=charge,
                         supply_current_a=current,supply_power_w=current*3.3))
    report['clock_pin_load']=dict(library_sha256=digest,voltage_v=3.3,
        capacitance_per_cell_f=cap,cells_per_clock=counts,clock_pin_capacitance_f=capacitance,
        operating_points=rows,
        scope='Nominal mapped clock-pin capacitance only: Q=C*V per rising edge and P=C*V^2*f. Excludes cell internal power, data switching, clock buffers/interconnect, leakage and rail transfer. Not a complete current or physical lower-bound guarantee.')
    report['sha256'][str((out/'mapped.json').relative_to(root))]=hashlib.sha256((out/'mapped.json').read_bytes()).hexdigest()
elif (project/'evidence/block-fifo-mapping.json').exists():
    # Preserve the optional extracted load only when its original inputs still
    # match; a fresh incompatible mapping must supply its own Liberty.
    previous=json.loads((project/'evidence/block-fifo-mapping.json').read_text())
    if 'clock_pin_load' in previous:
        mapped_key=str((out/'mapped.json').relative_to(root))
        mapped_hash=hashlib.sha256((out/'mapped.json').read_bytes()).hexdigest()
        if (previous['sha256'].get(mapped_key)!=mapped_hash or
            previous['clock_pin_load']['library_sha256']!=(out/'library.sha256').read_text().split()[0]):
            raise ValueError('Changed mapping/library: provide --lib to regenerate clock-pin loads')
        report['clock_pin_load']=previous['clock_pin_load']
        report['sha256'][mapped_key]=mapped_hash
report['sha256'][str(pathlib.Path(__file__).resolve().relative_to(root))]=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
(project / 'evidence/block-fifo-mapping.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='sha256'}, indent=2))
