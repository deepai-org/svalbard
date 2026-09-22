"""Clock input load screen: CVf current, excluding cell-internal and tree power."""
import hashlib
import json
from pathlib import Path
import re

out=Path('/out')
lib=Path('/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib')
text=lib.read_text()
assert re.search(r'capacitive_load_unit\s*\(\s*1\s*,\s*pf\s*\)',text,re.I), 'unexpected capacitance units'
assert re.search(r'nom_voltage\s*:\s*3\.3\s*;',text), 'unexpected voltage'

def blocks(text,kind):
    for match in re.finditer(r'\b'+kind+r'\s*\(\s*([^()]+?)\s*\)\s*\{',text):
        depth=1;end=match.end()
        while depth:
            if text[end]=='{':depth+=1
            elif text[end]=='}':depth-=1
            end+=1
        yield match[1].strip('"'),text[match.end():end-1]

j=json.loads((out/'pt_digital_mapped.json').read_text())['modules']['pt_digital']
used_types={cell['type'] for cell in j['cells'].values()}
clock_pins={}
for name,body in blocks(text,'cell'):
    if name not in used_types:continue
    for pin,pbody in blocks(body,'pin'):
        if re.search(r'\bclock\s*:\s*true\s*;',pbody):
            cap=re.search(r'\bcapacitance\s*:\s*([0-9.eE+-]+)\s*;',pbody)
            assert cap,(name,pin)
            clock_pins[name,pin]=float(cap[1])
assert clock_pins, 'no characterized clock pins found'
j=json.loads((out/'pt_digital_mapped.json').read_text())['modules']['pt_digital']
clocks={port['bits'][0]:name for name,port in j['ports'].items() if name.endswith('_clk') or name=='host_sclk'}
loads={name:{'pin_count':0,'capacitance_pf':0.0} for name in clocks.values()}
for cell in j['cells'].values():
    for pin,bits in cell['connections'].items():
        if (cell['type'],pin) in clock_pins:
            assert len(bits)==1 and bits[0] in clocks, ('unresolved clock source',cell['type'],pin,bits)
            row=loads[clocks[bits[0]]];row['pin_count']+=1;row['capacitance_pf']+=clock_pins[cell['type'],pin]
        elif '__dff' in cell['type'] and pin=='CLK':
            raise AssertionError(('missing clock characterization',cell['type']))
expected_flops=sum('__dff' in c['type'] for c in j['cells'].values())
assert expected_flops>0 and sum(x['pin_count'] for x in loads.values())==expected_flops, 'clock-pin coverage does not match mapped flops'
profiles=[]
for mode,hz,whz,rhz in [(0,250e6,125e6,40e6),(1,312.5e6,250e6,20e6)]:
    frequencies=dict(host_tx_clk=hz,host_rx_clk=hz,wire_rx_clk=whz,wire_tx_clk=whz,rf_rx_clk=rhz,rf_tx_clk=rhz,host_sclk=10e6,ref_clk=40e6)
    rows=[]
    for name,row in loads.items():
        # One rising charge per clock cycle. pF * Hz * V converts to mA with 1e-9.
        current=row['capacitance_pf']*frequencies[name]*3.3*1e-9
        rows.append(dict(clock=name,**row,frequency_hz=frequencies[name],charging_current_ma=current))
    total=sum(r['charging_current_ma'] for r in rows)
    profiles.append({'mode':mode,'domains':rows,'clock_pin_charging_current_ma':total,
                     'clock_pin_charging_power_mw':total*3.3,'remaining_from_48ma_before_other_loads':48-total,
                     'clock_pin_load_alone_exceeds_budget':total>48})
report={'scope':'Nominal lumped Liberty clock-input capacitance charging estimate; not total power or a PVT bound',
        'voltage_v':3.3,'core_budget_ma':48,'library_sha256':hashlib.sha256(lib.read_bytes()).hexdigest(),
        'netlist_sha256':hashlib.sha256((out/'pt_digital_mapped.json').read_bytes()).hexdigest(),
        'formula':'I=C*V*f; one 0-to-1 charge per clock cycle',
        'profiles':profiles,
        'limitations':['No internal flip-flop power, data/control switching, clock tree, wire capacitance, leakage or GPIO pre-driver load.',
                       'Nominal scalar Liberty input capacitance; nonlinear voltage behavior and rise/fall capacitance differences are not bounded.',
                       'All implemented clock domains active; SPI/reference frequencies are provisional.',
                       'Clock sources are assigned to CORE for budget accounting; final rail ownership must be explicit.',
                       'Even a result below 48mA would not close the core budget.']}
(out/'clock-power-screen.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps([{k:v for k,v in r.items() if k!='domains'} for r in profiles],indent=2))
