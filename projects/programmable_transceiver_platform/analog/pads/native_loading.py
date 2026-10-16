"""Extract selected native supply-clamp wire capacitance without replacing devices.

Maps the four clamp-control nets by transistor topology and summed width. This
is a partial capacitance augmentation, not native-cell LVS or full PEX.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import shlex
from layout import IMAGE, magic


def capacitances(path, cell):
    records=[shlex.split(line) for line in path.read_text().splitlines()]
    scale=next(r for r in records if r and r[0]=='scale')
    unit_um=float(scale[3])*.01; unit_f=float(scale[2])*1e-18
    groups=defaultdict(float)
    for r in records:
        if r[:2]!=['device','msubckt']:continue
        i=7;dimensions={}
        while '=' in r[i]:
            k,v=r[i].split('=');dimensions[k]=float(v);i+=1
        if abs(dimensions['l']*unit_um-.7)>1e-9:
            raise ValueError('Unexpected native clamp gate length')
        body,gate=r[i:i+2];ends=tuple(sorted((r[i+4],r[i+7])))
        groups[(r[2],gate,ends,body)]+=dimensions['w']*unit_um
    def gate(model,width,a,b,body):
        found=[g for (m,g,ends,bulk),w in groups.items() if m==model and
               abs(w-width)<1e-9 and ends==tuple(sorted((a,b))) and bulk==body]
        if len(found)!=1:raise ValueError('Ambiguous native clamp topology')
        return found[0]
    n4=gate('nfet_06v0',4000,'DVDD','DVSS','DVSS')
    n6=gate('pfet_06v0',120,'DVDD',n4,'DVDD')
    n7=gate('pfet_06v0',15,'DVDD',n6,'DVDD')
    n8=gate('pfet_06v0',20,'DVDD',n7,'DVDD')
    if gate('nfet_06v0',30,'DVSS',n4,'DVSS')!=n6 or \
       gate('nfet_06v0',30,'DVSS',n6,'DVSS')!=n7 or \
       gate('nfet_06v0',5,'DVSS',n7,'DVSS')!=n8:
        raise ValueError('Native clamp inverter chain does not match supplied schematic')
    mapping={n4:'n4',n6:'n6',n7:'n7',n8:'n8','DVDD':'DVDD','DVSS':'DVSS'}
    mapping['VSS' if cell.endswith('dvdd') else 'VDD']='VSS' if cell.endswith('dvdd') else 'VDD'
    internal={n4,n6,n7,n8};caps=[];excluded=[]
    substrate=next(r[1] for r in records if r and r[0]=='substrate')
    for r in records:
        if not r:continue
        if r[0]=='cap':a,b,value=r[1],r[2],float(r[3])*unit_f
        elif r[0]=='node' and r[1] in internal:a,b,value=r[1],substrate,float(r[3])*unit_f
        else:continue
        if not ({a,b}&internal) or value==0:continue
        if a in mapping and b in mapping:
            caps.append(dict(a=mapping[a],b=mapping[b],capacitance_f=value))
        else:excluded.append(dict(a=a,b=b,capacitance_f=value))
    if not caps:raise ValueError('No native clamp capacitance extracted')
    for c in caps:c['a'],c['b']=sorted((c['a'],c['b']))
    caps.sort(key=lambda c:(c['a'],c['b'],c['capacitance_f']))
    return dict(cell=cell,physical_to_schematic_nodes=mapping,capacitors=caps,
        excluded_unmapped_couplings=excluded,
        n6_added_incident_capacitance_f=sum(c['capacitance_f'] for c in caps if 'n6' in (c['a'],c['b'])),
        transistor_groups=[dict(model=m,gate=g,ends=ends,body=body,total_width_um=w)
                           for (m,g,ends,body),w in groups.items()],
        extraction_sha256=hashlib.sha256(path.read_bytes()).hexdigest())



def verify_schematic(body):
    """Reject renamed/control-altered native schematics before attaching C."""
    statements=re.sub(r'\n\+', ' ', body).splitlines();groups={}
    for line in statements:
        f=line.split()
        if len(f)<7 or not f[0].startswith('X') or f[5] not in ('nfet_06v0','pfet_06v0'):continue
        parameters=dict(word.split('=',1) for word in f[6:] if '=' in word)
        if abs(float(parameters['l'])*1e6-.7)>1e-9 or float(parameters['m'])!=1:
            raise ValueError('Native MOS dimensions/multiplicity changed')
        key=(f[5],f[2],tuple(sorted((f[1],f[3]))),f[4])
        groups[key]=groups.get(key,0)+float(parameters['w'])*1e6
    expected={
        ('nfet_06v0','n4',('DVDD','DVSS'),'DVSS'):4000.,
        ('nfet_06v0','n6',('DVSS','n4'),'DVSS'):30.,
        ('nfet_06v0','n7',('DVSS','n6'),'DVSS'):30.,
        ('nfet_06v0','n8',('DVSS','n7'),'DVSS'):5.,
        ('pfet_06v0','n6',('DVDD','n4'),'DVDD'):120.,
        ('pfet_06v0','n7',('DVDD','n6'),'DVDD'):15.,
        ('pfet_06v0','n8',('DVDD','n7'),'DVDD'):20.}
    if set(groups)!=set(expected) or any(abs(groups[k]-v)>1e-8 for k,v in expected.items()):
        raise ValueError('Native schematic control topology/width mismatch')


def build(work,library):
    if work.exists() and any(work.iterdir()):raise ValueError('Use an empty work directory')
    work.mkdir(parents=True,exist_ok=True);results={};text=library.read_text()
    for suffix in ('dvdd','dvss'):
        cell='gf180mcu_fd_io__'+suffix;root=work/suffix;root.mkdir()
        script=('crashbackups stop\nset ::env(PDKPATH) /pdk/gf180mcuD\n'
                'path search +/pdk/gf180mcuD/libs.ref/gf180mcu_fd_io/mag\n'
                f'load {cell}\nselect top cell\nflatten native_flat\nload native_flat\nsave\nextract all\nquit -noprompt\n')
        (root/'extract.tcl').write_text(script);magic(root,'extract.tcl')
        info=capacitances(root/'native_flat.ext',cell);results[cell]=info
        pattern=rf'(^\.SUBCKT {cell}[^\n]*\n)(.*?)(^\.ENDS[^\n]*)'
        matches=list(re.finditer(pattern,text,re.M|re.S|re.I))
        if len(matches)!=1:raise ValueError('Native library declaration mismatch')
        match=matches[0]
        verify_schematic(match.group(2))
        # Preserve all original native device records; add only mapped C.
        extra='* Selected layout-derived wire capacitance; incomplete PEX.\n'
        extra+=''.join(f"Cwire{i} {c['a']} {c['b']} {c['capacitance_f']:.12g}\n"
                       for i,c in enumerate(info['capacitors']))
        text=text[:match.start(3)]+extra+text[match.start(3):]
    restored=re.sub(r'(?m)^Cwire[^\n]*\n|^\* Selected layout-derived wire capacitance; incomplete PEX\.\n','',text)
    if restored!=library.read_text():raise ValueError('Native device records changed during augmentation')
    augmented=work/'native-with-wire-c.spice';augmented.write_text(text)
    report=dict(status='selected_native_clamp_capacitance_augmentation_not_full_PEX',
        image=IMAGE,cells=results,
        limitations=['No native-cell LVS claim: topology/width checks identify four control nodes only.',
            'Unmapped RC-chain couplings are explicitly excluded, not grounded or invented.',
            'All native devices retained; no extracted resistance, package or full-ring coupling.',
            'Interconnect capacitance uses installed extraction rules, not measured silicon.'],
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),library]},
        augmented_library_sha256=hashlib.sha256(augmented.read_bytes()).hexdigest())
    (work/'native-loading.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v['n6_added_incident_capacitance_f'] for k,v in results.items()}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--library',type=Path,required=True);a=parser.parse_args()
    build(a.output_dir.resolve(),a.library.resolve())
