"""Independently compare RF protection devices to physical extraction.

Explicit nonlinear well replacement and interconnect parasitics remain separate
obligations; device connectivity is not protection or reliability qualification.
"""
import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path
import shlex
from tempfile import TemporaryDirectory
from extract_audit import extracted_graph, converted_graph


def supplemental_graphs(records, model):
    rows=[shlex.split(line) for line in records]
    aliases={r[1]:r[2] for r in rows if r and r[0]=='equiv'}
    def net(value):
        seen=set()
        while value in aliases:
            if value in seen:raise ValueError('Extraction alias cycle')
            seen.add(value);value=aliases[value]
        return value
    scale=next(r for r in rows if r and r[0]=='scale')
    unit=float(scale[3])*.01
    actual=Counter();simulated=Counter();well=[]
    for r in rows:
        if not r or r[0]!='device' or r[1] in ('msubckt','rsubckt'):continue
        if r[1] not in ('ndiode','pdiode','csubckt'):
            raise ValueError('Unsupported protection device: '+r[1])
        index=7;dimensions={}
        while '=' in r[index]:
            name,value=r[index].split('=');dimensions[name]=float(value);index+=1
        body,first,second=net(r[index]),net(r[index+1]),net(r[index+4])
        if r[1]=='csubckt':
            if body!='None':raise ValueError('Unexpected MIM body')
            key=(r[2],first,second,round(dimensions['w']*unit,5),round(dimensions['l']*unit,5))
        else:
            if body!=second:raise ValueError('Unexpected diode body/terminal topology')
            anode,cathode=(body,first) if r[1]=='ndiode' else (first,body)
            key=(r[2],anode,cathode,round(dimensions['a']*unit**2,5),round(dimensions['p']*unit,5))
        actual[key]+=1
    def number(value):
        match=re.fullmatch(r'([0-9.eE+-]+)([munpf]?)',value)
        if not match:raise ValueError('Unsupported numeric value: '+value)
        return float(match[1])*{'':1.,'m':1e-3,'u':1e-6,'n':1e-9,'p':1e-12,'f':1e-15}[match[2]]
    for line in model.read_text().splitlines():
        r=line.split()
        if not r:continue
        if r[0]=='DWELL_ARRAY':
            well.append(line);continue
        if r[0].startswith('D'):
            dim=dict(x.split('=') for x in r[4:])
            key=(r[3],r[1],r[2],round(number(dim['area'])*1e12,5),round(number(dim['pj'])*1e6,5))
        elif r[0].startswith('X') and len(r)>3 and r[3].startswith('cap_mim'):
            dim=dict(x.split('=') for x in r[4:])
            key=(r[3],r[1],r[2],round(number(dim['c_width'])*1e6,5),round(number(dim['c_length'])*1e6,5))
        else:continue
        simulated[key]+=1
    return actual,simulated,well


def well_replacement(extraction, raw, model):
    """Audit the isolated array wells and conservation of extracted capacitance."""
    rows=[shlex.split(line) for line in extraction.read_text().splitlines()]
    scale=float(next(r[3] for r in rows if r and r[0]=='scale'))*.01
    areas=[];perimeters=[]
    for r in rows:
        if not r or r[:3]!=['device','pdiode','diode_pd2nw_06v0']:continue
        index=7
        while '=' in r[index]:index+=1
        if r[index]!='ESD_RAIL' or r[index+4]!='ESD_RAIL':
            raise ValueError('Array well is not on isolated protection rail')
        area,perimeter=map(float,r[index+6].split(','))
        areas.append(area*scale**2);perimeters.append(perimeter*scale)
    if not areas:raise ValueError('No extracted array wells')
    def number(value):
        m=re.fullmatch(r'([0-9.eE+-]+)([munpf]?)',value)
        if not m:raise ValueError('Unsupported numeric value: '+value)
        return float(m[1])*{'':1.,'m':1e-3,'u':1e-6,'n':1e-9,'p':1e-12,'f':1e-15}[m[2]]
    lines=[line.split() for line in model.read_text().splitlines()]
    wells=[r for r in lines if r and r[0]=='DWELL_ARRAY']
    if len(wells)!=1 or wells[0][1:4]!=['VSS','ESD_RAIL','diode_nw2ps_06v0']:
        raise ValueError('Wrong well-replacement polarity, model or multiplicity')
    dim=dict(x.split('=') for x in wells[0][4:])
    if abs(number(dim['area'])*1e12-sum(areas))>1e-6 or abs(number(dim['pj'])*1e6-sum(perimeters))>1e-6:
        raise ValueError('Well replacement dimensions differ from extracted well terminals')
    def caps(path):
        result=Counter()
        for line in path.read_text().splitlines():
            r=line.split()
            if r and r[0].startswith('C'):
                result[tuple(sorted(r[1:3]))]+=number(r[3])*1e15
        return result
    before=caps(raw);after=caps(model);key=tuple(sorted(('VSS','ESD_RAIL')))
    # Pinned Magic GF180 extraction coefficient: 120 aF/um2.
    correction=sum(areas)*.120
    changes={k:before[k]-after[k] for k in set(before)|set(after)}
    if any(abs(v-(correction if k==key else 0.))>1e-5 for k,v in changes.items()):
        raise ValueError('Well replacement changed unrelated capacitance or double-counted area')
    return dict(extracted_well_area_um2=sum(areas),extracted_well_perimeter_um=sum(perimeters),
        linear_capacitance_removed_ff=changes[key],expected_removal_ff=correction,
        other_extracted_capacitances_unchanged=True,
        scope='Terminal well areas assume isolated, nonshared array wells as established by array geometry; no nonlinear junction accuracy or ESD qualification.',
        raw_spice_sha256=hashlib.sha256(raw.read_bytes()).hexdigest())


def check(extraction, model, output, raw=None):
    records=extraction.read_text().splitlines()
    excluded=Counter()
    kept=[]
    for line in records:
        fields=shlex.split(line)
        if fields and fields[0]=='device' and fields[1] not in ('msubckt','rsubckt'):
            excluded[fields[1]+':'+fields[2]]+=1
        else:kept.append(line)
    devices=[]
    for line in model.read_text().splitlines():
        fields=line.split()
        if not fields or not fields[0].startswith('X'):continue
        if any(x.startswith(('w=','r_width=')) for x in fields):
            scales={'':1e6,'m':1e3,'u':1.,'n':1e-3,'p':1e-6}
            line=re.sub(r'\b(w|l|r_width|r_length)=([0-9.eE+-]+)([munp]?)(?=\s|$)',
                lambda m:f'{m[1]}={float(m[2])*scales[m[3]]:.12g}u',line)
            devices.append(line)
    with TemporaryDirectory() as directory:
        root=Path(directory)
        (root/'physical.ext').write_text('\n'.join(kept)+'\n')
        (root/'model.spice').write_text('\n'.join(devices)+'\n')
        actual=extracted_graph(root/'physical.ext')
        simulated=converted_graph(root/'model.spice')
    extra_actual,extra_simulated,well=supplemental_graphs(records,model)
    actual+=extra_actual;simulated+=extra_simulated
    result=dict(status='physical_MOS_resistor_diode_MIM_graph_comparison',
        device_graph_matches=actual==simulated,physical_devices=sum(actual.values()),
        simulated_devices=sum(simulated.values()),
        missing=[dict(key=list(k),count=v) for k,v in (actual-simulated).items()],
        unexpected=[dict(key=list(k),count=v) for k,v in (simulated-actual).items()],
        supplemental_device_counts=dict(excluded),excluded_devices={'explicit_well_replacement':well},
        scope='MOS/resistor bodies and sizes, steering-diode polarity/area/perimeter, and ordered MIM terminals/dimensions checked. Explicit well replacement and parasitic values not certified; no ESD rating.',
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (extraction,model,Path(__file__),Path(__file__).with_name('extract_audit.py'))})
    if raw is not None:
        result['well_replacement']=well_replacement(extraction,raw,model)
        result['source_sha256'][str(raw.resolve())]=hashlib.sha256(raw.read_bytes()).hexdigest()
    output.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--extraction',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--raw-spice',type=Path)
    a=p.parse_args();r=check(a.extraction,a.model,a.output,a.raw_spice)
    print(json.dumps({k:r[k] for k in ('device_graph_matches','physical_devices','simulated_devices','excluded_devices')}))
    if not r['device_graph_matches']:raise SystemExit(1)
