"""Compare Magic's extracted device graph independently of ext2spice conversion.

This cross-check does not replace LVS or waive a disagreement between tools.
Read body terminals from the physical extractor, never overwrite them from the
intended schematic. Keep exact device sizes and labeled net connectivity.
"""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json
import shlex
from circuits import build,FAMILIES


def key(model,nodes,width,length):
    # Normal MOS source/drain permutation is permitted by the PDK LVS setup.
    # Asymmetric drain-SAB protection is directional and must not be permuted.
    if len(nodes)==3:
        a,b,bulk=nodes
        return (model,*sorted((a,b)),bulk,round(width,5),round(length,5))
    d,g,s,b=nodes
    if not model.endswith('_dss'):
        d,s=sorted((d,s))
    return (model,d,g,s,b,round(width,5),round(length,5))


def extracted_graph(path):
    lines=[shlex.split(line) for line in path.read_text().splitlines()]
    aliases={}
    for fields in lines:
        if fields and fields[0]=='equiv':
            aliases[fields[1]]=fields[2]
    def resolve(net):
        visited=set()
        while net in aliases:
            if net in visited:raise ValueError('Alias cycle in extraction')
            visited.add(net);net=aliases[net]
        return net
    result=Counter()
    for fields in lines:
        if not fields or fields[0]!='device':continue
        if fields[1] not in ('msubckt','rsubckt','ndiode','csubckt'):
            raise ValueError('Unsupported extracted device '+fields[1])
        model=fields[2]
        index=7; dimensions={}
        while '=' in fields[index]:
            name,value=fields[index].split('=');dimensions[name]=float(value)
            index+=1
        if fields[1]=='ndiode':
            # Antenna diode (analog/antenna_diodes.py): substrate, cathode ..., anode records.
            result[diode_key(model,resolve(fields[index+4]),resolve(fields[index+1]),
                             dimensions['a']*.005*.005,dimensions['p']*.005)]+=1
            continue
        if fields[1]=='csubckt':   # PD46 MIM: substrate, top (gate slot), bottom (first terminal); ordered, square
            result[cap_key(model,resolve(fields[index+1]),resolve(fields[index+4]),dimensions['w']*.005,dimensions['l']*.005)]+=1
            continue
        body,gate=fields[index:index+2]
        source,drain=fields[index+4],fields[index+7]
        nodes=(drain,source,body) if fields[1]=='rsubckt' else (drain,gate,source,body)
        result[key(model,[resolve(n) for n in nodes],
                   dimensions['w']*.005,dimensions['l']*.005)]+=1
    return result


def cap_key(model,top,bottom,w_um,l_um):
    return (model,top,bottom,*sorted((round(w_um,5),round(l_um,5))))


def diode_key(model,anode,cathode,area_um2,perimeter_um):
    return (model,anode,cathode,round(area_um2,4),round(perimeter_um,4))


def converted_graph(path):
    result=Counter()
    for line in path.read_text().splitlines():
        if line.startswith('D'):
            f=line.split();d=dict(item.split('=') for item in f[4:] if '=' in item)
            result[diode_key(f[3],f[1],f[2],float(d['area'].removesuffix('p')),float(d['pj'].removesuffix('u')))]+=1
            continue
        if not line.startswith('X'):continue
        fields=line.split()
        if len(fields)>3 and fields[3].startswith('cap_mim'):
            d=dict(item.split('=') for item in fields[4:] if '=' in item)
            result[cap_key(fields[3],fields[1],fields[2],float(d['c_width'].removesuffix('u')),float(d['c_length'].removesuffix('u')))]+=1
            continue
        resistor=fields[4].startswith('ppoly')
        pos=4 if resistor else 5
        dimensions=dict(item.split('=') for item in fields[pos+1:] if '=' in item)
        w,l=('r_width','r_length') if resistor else ('w','l')
        result[key(fields[pos],fields[1:pos],float(dimensions[w].removesuffix('u')),
                   float(dimensions[l].removesuffix('u')))]+=1
    return result


def export_extracted(path,output,*,capacitance=True):
    """Small explicit exporter of physical .ext records, with no schematic input.

    Supports only this generator's MOS/resistor records and rejects unknown
    devices/hierarchy. Geometry, body nodes, junction areas and capacitances
    come from Magic extraction. Interconnect resistance is NOT reconstructed.
    """
    records=[shlex.split(line) for line in path.read_text().splitlines()]
    aliases={r[1]:r[2] for r in records if r and r[0]=='equiv'}
    def net(n):
        visited=set()
        while n in aliases:
            if n in visited:raise ValueError('Alias cycle')
            visited.add(n);n=aliases[n]
        return n
    scale=next(r for r in records if r and r[0]=='scale')
    length_um=float(scale[3])*.01
    cap_f=float(scale[2])*1e-18
    ports=[net(r[1]) for r in sorted((r for r in records if r and r[0]=='port'),key=lambda r:int(r[2]))]
    if len(set(ports))!=len(ports):raise ValueError('Extracted ports are shorted')
    substrate=next(net(r[1]) for r in records if r and r[0]=='substrate')
    name=path.stem+'_physical'
    lines=['* Independent exporter of physical Magic .ext; no schematic substitutions.',
           '* Extracted capacitance included; distributed wire resistance remains absent.',
           '.subckt '+name+' '+' '.join(ports)]
    count=0; caps=[]
    for r in records:
        if not r:continue
        if r[0]=='use':raise ValueError('Flatten hierarchy before export')
        if r[0]=='device':
            if r[1] not in ('msubckt','rsubckt','ndiode','csubckt'):raise ValueError('Unsupported device')
            index=7;dim={}
            while '=' in r[index]:
                k,v=r[index].split('=');dim[k]=float(v);index+=1
            if r[1]=='ndiode':
                # Antenna diode (N+/Psub, analog/antenna_diodes.py): substrate, cathode, anode records.
                cathode,anode=r[index+1],r[index+4]
                lines.append(f"D{count} {net(anode)} {net(cathode)} {r[2]} area={dim['a']*length_um**2:.8g}p "
                             f"pj={dim['p']*length_um:.8g}u");count+=1
                continue
            if r[1]=='csubckt':   # PD46 MIM (top, bottom)
                lines.append(f"X{count} {net(r[index+1])} {net(r[index+4])} {r[2]} c_width={dim['w']*length_um:.8g}u c_length={dim['l']*length_um:.8g}u");count+=1
                continue
            body,gate=r[index:index+2]
            source,drain=r[index+4],r[index+7]
            w,l=dim['w']*length_um,dim['l']*length_um
            if r[1]=='rsubckt':
                line=f"X{count} {net(drain)} {net(source)} {net(body)} {r[2]} r_width={w:.8g}u r_length={l:.8g}u"
            else:
                sa,sp=map(float,r[index+6].split(','));da,dp=map(float,r[index+9].split(','))
                line=(f"X{count} {net(drain)} {net(gate)} {net(source)} {net(body)} {r[2]} "
                      f"w={w:.8g}u l={l:.8g}u ad={da*length_um**2:.8g}p as={sa*length_um**2:.8g}p "
                      f"pd={dp*length_um:.8g}u ps={sp*length_um:.8g}u")
                if r[2].endswith('_dss'):
                    line+=f" d_sab={dim['l2']*length_um:.8g}u s_sab={dim['l1']*length_um:.8g}u"
            lines.append(line);count+=1
        elif r[0]=='cap':caps.append((net(r[1]),net(r[2]),float(r[3])*cap_f))
        elif r[0]=='node':caps.append((net(r[1]),substrate,float(r[3])*cap_f))
    if capacitance:
        for i,(a,b,value) in enumerate(caps):
            if value<0:raise ValueError('Negative extracted capacitance')
            if a!=b and value:lines.append(f'C{i} {a} {b} {value:.12g}')
    lines+=['.ends '+name,'']
    output.write_text('\n'.join(lines))
    return name


def audit(work,family='wired_transmit'):
    c=build(family)
    flat='pad_tx_flat' if family=='wired_transmit' else c.name+'_flat'
    expected=Counter(key(d.model,d.nodes,d.w_um,d.l_um) for d in c.devices)
    extracted=extracted_graph(work/(flat+'.ext'))
    layout_report=work/'layout-report.json'
    stock_returncode=json.loads(layout_report.read_text()).get('stock_export_returncode',0) if layout_report.exists() else 0
    converted=converted_graph(work/(flat+'.spice')) if stock_returncode==0 else None
    export_extracted(work/(flat+'.ext'),work/'physical.spice')
    export_extracted(work/(flat+'.ext'),work/'physical-lvs.spice',capacitance=False)
    physical=converted_graph(work/'physical.spice')
    def difference(a,b):
        return [dict(device=list(k),count=v) for k,v in (a-b).items()]
    report=dict(status='independent_extractor_graph_audit_not_LVS_waiver',
                schematic_device_count=sum(expected.values()),extracted_device_count=sum(extracted.values()),
                extractor_matches_schematic=extracted==expected,
                stock_export_returncode=stock_returncode,
                ext2spice_matches_extractor=converted==extracted if converted is not None else None,
                independent_export_matches_extractor=physical==extracted,
                independent_export_scope='Capacitance, device geometry and connectivity; distributed interconnect R absent.',
                extracted_missing=difference(expected,extracted),
                extracted_extra=difference(extracted,expected),
                converted_missing=difference(extracted,converted) if converted is not None else None,
                converted_extra=difference(converted,extracted) if converted is not None else None,
                source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (work/(flat+'.ext'),work/(flat+'.spice'),work/'physical.spice',
                                         Path(__file__),Path(__file__).with_name('circuits.py')) if p.exists()})
    (work/'extraction-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('work',type=Path)
    p.add_argument('--family',choices=FAMILIES,default='wired_transmit')
    args=p.parse_args()
    audit(args.work,args.family)
