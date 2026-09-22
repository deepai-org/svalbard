"""Extract scoped same-clock diagnostics; reject tool errors and incomplete runs."""
import hashlib
import json
from pathlib import Path
import re
import sys

out=Path(sys.argv[1])
project=Path(__file__).resolve().parents[1]
reports=[]
verilog=(out/'pt_digital_mapped.v').read_text()
def register_output(instance):
    match=re.search(r'\s'+re.escape(instance)+r'\s*\((.*?)\n  \);',verilog,re.S)
    q=re.search(r'\.Q\((.*?)\)',match[1]) if match else None
    return q[1].strip() if q else 'unresolved'

for mode in (0,1):
    path=out/f'timing-mode{mode}.log'
    text=path.read_text()
    if re.search(r'^Error:',text,re.M) or 'CONSTRAINT_AUDIT_END' not in text:
        raise SystemExit(f'Failed/incomplete STA run: {path}')
    domains={}
    critical_registers={}
    for name,body in re.findall(r'DOMAIN_BEGIN (\w+)\n(.*?)DOMAIN_END \1',text,re.S):
        groups={}
        for block in body.split('Startpoint:')[1:]:
            group=re.search(r'Path Group: (\S+)',block)
            slack=re.search(r'(-?\d+\.\d+)\s+slack \((?:MET|VIOLATED)\)',block)
            if group and slack:
                groups.setdefault(group[1],[]).append(float(slack[1]))
        if not groups:
            raise SystemExit(f'No timed paths in {name}')
        domains[name]={g:min(v) for g,v in groups.items()}
        for block in body.split('Startpoint:')[1:]:
            if f'Path Group: {name}\n' in block:
                start=block.split()[0];end=re.search(r'Endpoint: (\S+)',block)[1]
                critical_registers[name]={'start_Q':register_output(start),'end_Q':register_output(end)}
                break
    if len(domains)!=8 or 'ELECTRICAL_AUDIT_END' not in text:
        raise SystemExit('Incomplete domain/electrical audit')
    electrical=text.split('ELECTRICAL_AUDIT_BEGIN')[1].split('ELECTRICAL_AUDIT_END')[0]
    reports.append({'mode':mode,'critical_register_outputs':critical_registers,'worst_reported_slack_ns_by_domain_and_group':domains,
                    'reported_electrical_violation_rows':electrical.count('(VIOLATED)'),
                    'warnings':re.findall(r'^Warning:.*$',text,re.M),
                    'log_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
netlist=json.loads((out/'pt_digital_mapped.json').read_text())['modules']['pt_digital']
loads={}
for name,cell in netlist['cells'].items():
    for port,bits in cell['connections'].items():
        if cell.get('port_directions',{}).get(port)=='input':
            for bit in bits:
                if isinstance(bit,int):loads[bit]=loads.get(bit,0)+1
fanout=[]
for bit,count in sorted(loads.items(),key=lambda p:-p[1])[:8]:
    aliases=[n for n,v in netlist['netnames'].items() if v['bits']==[bit]]
    fanout.append({'input_pin_loads':count,'scalar_net_aliases':aliases})
failed=any(p['reported_electrical_violation_rows'] or any(s<0 for groups in p['worst_reported_slack_ns_by_domain_and_group'].values() for s in groups.values()) for p in reports)
report={'scope':'Unplaced TT 25C 3.3V same-domain timing diagnostics; not signoff or fmax bounds',
        'area_screen':json.loads((out/'area-screen.json').read_text()),
        'timing_script_sha256':hashlib.sha256((project/'verification/timing_screen.tcl').read_bytes()).hexdigest(),
        'profiles':reports,'largest_unbuffered_net_fanouts':fanout,
        'limitations':['Ideal clocks, no extracted interconnect, no timing-driven physical buffering or sizing.',
                       'Electrical violations and library extrapolation invalidate interpreting extreme slacks as physical delay predictions.',
                       'Unconstrained external interfaces remain explicit; no blanket false-path exceptions were added.',
                       'Same-domain reports exclude CDC qualification, reset distribution closure and protocol timing.',
                       'SPI 10MHz and reference 40MHz are provisional service clocks.',
                       'No jitter/skew allowance or operating-envelope/process sweep.'],
        'result':('FAIL: reported timing or electrical violations remain' if failed else 'No reported violations in this limited screen; not timing signoff')}
(out/'timing-screen.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'result':report['result'],'largest_fanout':fanout[0],'profiles':reports},indent=2))
