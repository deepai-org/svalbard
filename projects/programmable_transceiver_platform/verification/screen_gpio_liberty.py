"""Read-only screen of selected installed GF180 I/O Liberty tables.

Deliberately not STA, waveform/eye simulation, or a universal Liberty parser.
"""
import hashlib
import json
import re
from pathlib import Path


def groups(text, kind):
    pattern = re.compile(r'\b'+re.escape(kind)+r'\s*\(\s*"?([^"()]*?)"?\s*\)\s*\{')
    for m in pattern.finditer(text):
        depth, quote, escape = 1, False, False
        for i in range(m.end(),len(text)):
            char=text[i]
            if quote:
                if escape: escape=False
                elif char=='\\': escape=True
                elif char=='"': quote=False
            elif char=='"': quote=True
            elif char=='{': depth+=1
            elif char=='}':
                depth-=1
                if depth==0:
                    yield m.group(1).strip(),text[m.end():i]
                    break
        else: raise ValueError('unclosed Liberty group')


def attr(text, name):
    m=re.search(r'\b'+re.escape(name)+r'\s*:\s*([^;]+);',text)
    if not m: raise ValueError('missing '+name)
    return m.group(1).strip().strip('"')


def numbers(text, name):
    m=re.search(r'\b'+name+r'\s*\((.*?)\);',text,re.S)
    if not m: raise ValueError('missing '+name)
    return [float(x) for x in re.findall(r'[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?',m.group(1))]


def bracket(axis,value):
    if not axis[0] <= value <= axis[-1]: raise ValueError('extrapolation prohibited')
    for i in range(len(axis)-1):
        if axis[i] <= value <= axis[i+1]:
            return i,(value-axis[i])/(axis[i+1]-axis[i])
    raise ValueError('invalid axis')


def interpolate(table,slew,load):
    x,y=numbers(table,'index_1'),numbers(table,'index_2')
    v=numbers(table,'values')
    if len(v)!=len(x)*len(y): raise ValueError('table dimensions')
    i,a=bracket(x,slew);j,b=bracket(y,load)
    row=lambda r: (1-b)*v[r*len(y)+j]+b*v[r*len(y)+j+1]
    return (1-a)*row(i)+a*row(i+1)


def screen(path):
    raw=path.read_bytes();text=raw.decode()
    if attr(text,'time_unit')!='1ns': raise ValueError('unexpected time unit')
    if not re.search(r'capacitive_load_unit\(1\.000000,\s*\\?\s*"pf"\)',text):
        raise ValueError('unexpected capacitance unit')
    cells=dict(groups(text,'cell'))
    rows=[]
    for name in ['gf180mcu_fd_io__bi_24t','gf180mcu_fd_io__bi_t']:
        pins=dict(groups(cells[name],'pin'))
        pad=pins['PAD']
        for _,arc in groups(pad,'timing'):
            if attr(arc,'related_pin')!='A' or attr(arc,'timing_type')!='combinational': continue
            tables={kind:dict(groups(arc,kind)) for kind in ['cell_rise','cell_fall','rise_transition','fall_transition']}
            if any(len(t)!=1 for t in tables.values()): raise ValueError('ambiguous timing table')
            for load in [5.0,10.0,15.0]:
                values={kind:interpolate(next(iter(t.values())),0.5,load) for kind,t in tables.items()}
                rows.append({'cell':name,'condition':attr(arc,'when'),'input_slew_ns':0.5,
                             'table_load_coordinate_pf':load,'pad_capacitance_pf':float(attr(pad,'capacitance')),
                             **{k+'_ns':round(v,6) for k,v in values.items()},
                             'rise_fall_delay_difference_ns':round(abs(values['cell_rise']-values['cell_fall']),6),
                             'max_transition_fraction_of_3p2ns_ui':round(max(values['rise_transition'],values['fall_transition'])/3.2,6)})
    return {'file':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'rows':rows}


if __name__=='__main__':
    base=Path('/pdk/gf180mcuD/libs.ref/gf180mcu_fd_io/lib')
    suffixes=['tt_025C_3v30','ss_125C_2v97','ff_n40C_3v63','ff_125C_3v63']
    reports=[screen(base/f'gf180mcu_fd_io__{s}.lib') for s in suffixes]
    print(json.dumps({'scope':'candidate installed Liberty output-arc screen only',
        'image_id':'sha256:9253a51f5fdcc7202a164aa26274b4b95533ecdedeb7eb47d6605f5881bfef17',
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'ui_ns':3.2,'caveats':['No package/PCB/FPGA/SSO/input-path modeling.',
        'Load values are Liberty table coordinates, not verified external-load-only values.',
        'Absolute propagation delay greater than UI does not by itself disqualify source-synchronous operation.',
        'No extrapolation; 0.5 ns input slew is an assumption, not a closed internal driver.',
        'Installed PDK is exploratory; fabrication process.lock remains unresolved.'],
        'libraries':reports},indent=2))
