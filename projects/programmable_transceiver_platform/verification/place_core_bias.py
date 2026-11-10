#!/usr/bin/env python3
"""Place the real core-reference cells with their complete electrical pin map.

This produces an unrouted physical assembly for floorplanning. Qualified input
GDS is preserved; wiring, boundary pins, PDN and assembled signoff remain open.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT/'integration'))
from core_bias import build
from check_chip_power import ports

IMAGE = 'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'

LAYOUT = '''
import json,pya,sys
from pathlib import Path
sys.path.insert(0,'/work')
from audit_macro_pins import audit
manifest=json.loads(Path('/work/placement-inputs.json').read_text())
layout=pya.Layout();layout.dbu=.001
top=layout.create_cell('pt_core_bias_placement')
masters={}
for name,info in manifest['masters'].items():
    source=pya.Layout();source.read('/work/'+info['file'])
    original=source.cell(name);assert original is not None,name
    assert source.dbu==layout.dbu,(name,source.dbu)
    cell=layout.create_cell(name);cell.copy_tree(original);masters[name]=cell
placements=[];gap=20;edge=20;y=edge
plan=manifest.get('plan') or {}
die=plan.get('die_um',[1000.,400.]);row_gap=plan.get('row_gap_um',gap);gaps=plan.get('gap_um',{})
bands={i['name']:'and' for i in manifest['instances'] if i['master']=='bringup_and'}
groups=plan.get('rows') or [['Xbiasgen','Xbandgap'],['Xroot','Xvref'],
        [i['name'] for i in manifest['instances'] if i['name'].startswith('Xbank_')],
        [i['name'] for i in manifest['instances'] if i['master']=='bringup_and']]
groups=[sum(([n for i in manifest['instances'] for n in [i['name']] if i['master']=='bringup_and'] if g=='ANDS' else [g] for g in grp),[]) for grp in groups]
instances={i['name']:i for i in manifest['instances']}
assert sum(map(len,groups))==len(instances) and len(set(sum(groups,[])))==len(instances)
pairgap=lambda a,b: gaps.get('and',gap) if (a in bands and b in bands) else gap
for group in groups:
    x=edge;rowheight=0;prev=None
    for name in group:
        entry=instances[name];cell=masters[entry['master']];b=cell.bbox()
        width=b.width()*layout.dbu;height=b.height()*layout.dbu
        if prev is not None: x+=pairgap(prev,name)-gap
        prev=name
        if x+width>die[0]-edge and x>edge:
            x=edge;y+=rowheight+gap;rowheight=0
        tr=pya.Trans(round(x/layout.dbu)-b.left,round(y/layout.dbu)-b.bottom)
        top.insert(pya.CellInstArray(cell.cell_index(),tr))
        bbox=b.transformed(tr)
        placements.append(dict(name=name,master=entry['master'],
                               bbox_um=[v*layout.dbu for v in [bbox.left,bbox.bottom,bbox.right,bbox.top]],
                               transform_dbu=[tr.disp.x,tr.disp.y]))
        x+=width+gap;rowheight=max(rowheight,height)
    y+=rowheight+row_gap
minimum_gap=float('inf')
for i,a in enumerate(placements):
    ax0,ay0,ax1,ay1=a['bbox_um']
    for b in placements[i+1:]:
        bx0,by0,bx1,by1=b['bbox_um']
        dx=max(bx0-ax1,ax0-bx1,0);dy=max(by0-ay1,ay0-by1,0)
        distance=(dx*dx+dy*dy)**.5
        need=pairgap(a['name'],b['name']) if (a['name'] in bands and b['name'] in bands) else min(gap,row_gap)
        assert distance>=need-1e-6,(a['name'],b['name'],distance)
        minimum_gap=min(minimum_gap,distance)
options=pya.SaveLayoutOptions();options.select_cell(top.cell_index());options.write_context_info=False
layout.write('/work/pt_core_bias_placement.gds',options)
check=pya.Layout();check.read('/work/pt_core_bias_placement.gds')
assert check.dbu==layout.dbu
for name,info in manifest['masters'].items():
    source=pya.Layout();source.read('/work/'+info['file']);a=source.cell(name);b=check.cell(name)
    assert b is not None,name
    layers=set((l.get_info(i).layer,l.get_info(i).datatype) for l in [source,check] for i in l.layer_indexes())
    for layer,datatype in layers:
        ai=source.find_layer(layer,datatype);bi=check.find_layer(layer,datatype)
        ar=pya.Region(a.begin_shapes_rec(ai)) if ai is not None else pya.Region()
        br=pya.Region(b.begin_shapes_rec(bi)) if bi is not None else pya.Region()
        assert (ar^br).is_empty(),(name,layer,datatype)
b=top.bbox()
assert b.right*layout.dbu<=die[0]-edge+1e-6 and b.top*layout.dbu<=die[1]-10+1e-6,(b,die)
result=dict(status='unrouted_placement',instances=placements,die_um=die,plan=plan,source_geometry_xor='zero for every master',
            bbox_um=[v*layout.dbu for v in [b.left,b.bottom,b.right,b.top]],minimum_bbox_gap_um=minimum_gap)
Path('/work/geometry-audit.json').write_text(json.dumps(result,indent=2)+'\\n')
pin_audit=audit(Path('/work/pin-inputs.json'),Path('/work/pin-audit.json'))
pins={}
for pin in pin_audit['pin_details']:
    pins.setdefault(pin['cell'],{})[pin['pin']]=pin
nets={}
for placement in placements:
    entry=instances[placement['name']];available=pins[entry['master']]
    private=set(entry['extracted_private_pins'])
    assert set(entry['connections'])==set(available)|private,(entry['name'],set(entry['connections'])^set(available))
    dx,dy=placement['transform_dbu']
    for pin,definition in available.items():
        assert definition['dbu_um']==layout.dbu
        shapes=[]
        for shape in definition['shapes']:
            x0,y0,x1,y1=shape['box_dbu']
            shapes.append(dict(layer=shape['layer'],box_dbu=[x0+dx,y0+dy,x1+dx,y1+dy]))
        net=entry['connections'][pin]
        nets.setdefault(net,[]).append(dict(instance=entry['name'],pin=pin,shapes=shapes))
assert set(manifest['boundary_pins'])<=set(nets),set(manifest['boundary_pins'])-set(nets)
terminals=dict(status='unrouted_terminals_verified',dbu_um=layout.dbu,nets=nets,
               boundary_pins=manifest['boundary_pins'],terminal_count=sum(map(len,nets.values())))
Path('/work/physical-terminals.json').write_text(json.dumps(terminals,indent=2)+'\\n')
'''


# I9 compact arrangement: vref joins the biasgen/bandgap row, the root joins the enable-gate
# row (gates at 12 um instead of 20 um), each per-island bank stays one intact master.
COMPACT_PLAN = dict(die_um=[950., 330.], row_gap_um=20., gap_um=dict(**{'and': 12.}),
                    rows=[['Xbiasgen', 'Xbandgap', 'Xvref'],
                          ['Xbank_rf', 'Xbank_conv', 'Xbank_pll', 'Xbank_wired', 'Xbank_debug'],
                          ['Xroot', 'ANDS']])


def place(out, plan=None):
    out.mkdir(parents=True, exist_ok=True)
    assert not (out/'report.json').exists(), 'Use a fresh output directory'
    sources = {}
    def read(path):
        path = Path(path).resolve()
        sources[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        return path.read_text()
    for path in [Path(__file__).resolve(), PROJECT/'integration/core_bias.py',
                 PROJECT/'verification/check_chip_power.py']:
        read(path)
    (out/'audit_macro_pins.py').write_text(read(PROJECT/'verification/audit_macro_pins.py'))
    core = build(read)
    (out/'pt_core_bias.spice').write_text(core['text'])
    qualification = json.loads(read(PROJECT/'analog/core_support/evidence/core_support_evidence.json'))
    model_manifest = json.loads(read(PROJECT/'integration/models/core_bias/manifest.json'))
    glue_path = PROJECT/'analog/bringup_control/generated/evidence.json'
    glue = json.loads(read(glue_path))
    assert glue['status'] == 'pass'
    choices = {
        'gf180mcu_ocd_ip__biasgen': ('analog/core_support/biasgen_tapeout/gf180mcu_ocd_ip__biasgen.gds.gz',
                                  model_manifest['models']['biasgen_patched']['qualified_geometry_sha256']),
        'gf180mcu_ocd_ip__bandgap': ('analog/core_support/bandgap/gds/gf180mcu_ocd_ip__bandgap.gds.gz',
                                  model_manifest['models']['bandgap']['qualified_geometry_sha256']),
        'bringup_and': ('analog/bringup_control/generated/leaves/bringup_and.gds',
                        glue['artifact_hashes'][str(PROJECT/'analog/bringup_control/generated/leaves/bringup_and.gds')]),
    }
    for name, info in qualification['distribution']['layout'].items():
        choices[name] = ('analog/core_support/distribution/generated/'+name+'.gds.gz',
                         info['hashes'][name+'.gds'])
    masters = {}
    for name, (ref, digest) in choices.items():
        path = PROJECT/ref
        data = path.read_bytes()
        sources[str(path)] = hashlib.sha256(data).hexdigest()
        # Core support qualifies the compressed upstream deliverables, while
        # distribution qualifies the uncompressed Magic export.
        uncompressed = gzip.decompress(data) if path.suffix == '.gz' else data
        assert digest in (hashlib.sha256(data).hexdigest(), hashlib.sha256(uncompressed).hexdigest()), ref
        filename = name+'.gds'
        (out/filename).write_bytes(uncompressed)
        masters[name] = dict(file=filename, qualified_sha256=digest)
    abstracts = json.loads(read(PROJECT/'analog/core_support/distribution/generated/abstract-evidence.json'))
    for path, digest in abstracts['published_artifact_hashes'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
    for name in masters:
        if name == 'bringup_and':
            continue
        if name == 'gf180mcu_ocd_ip__biasgen':
            lef = PROJECT/'analog/core_support/biasgen_tapeout'/(name+'.lef')
        elif name == 'gf180mcu_ocd_ip__bandgap':
            lef = PROJECT/'analog/core_support/bandgap/lef'/(name+'.lef')
        else:
            lef = PROJECT/'analog/core_support/distribution/generated'/(name+'.lef')
        (out/lef.name).write_text(read(lef))
    leaf = PROJECT/'analog/bringup_control/generated/leaves/bringup_and.mag'
    assert hashlib.sha256(leaf.read_bytes()).hexdigest() == glue['artifact_hashes'][str(leaf)]
    (out/leaf.name).write_text(read(leaf))
    commands = ['crashbackups stop', 'load bringup_and', 'units microns',
                'box values 0 0 1 1', 'property LEFclass BLOCK']
    for number, direction, use in [(1,'input','signal'),(2,'input','signal'),
                                    (3,'output','signal'),(4,'inout','power'),(5,'inout','ground')]:
        commands += [f'port {number} class {direction}', f'port {number} use {use}']
    commands += ['lef write bringup_and.lef -hide', 'quit -noprompt']
    (out/'leaf-abstract.tcl').write_text('\n'.join(commands)+'\n')
    abstract = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--memory', '2g',
                               '--entrypoint', '/bin/bash', '-v', f'{out}:/work', '-w', '/work', IMAGE, '-lc',
                               'magic -dnull -noconsole -rcfile '
                               '/foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc /work/leaf-abstract.tcl'],
                              capture_output=True, text=True, timeout=180)
    (out/'leaf-abstract.log').write_text(abstract.stdout+abstract.stderr)
    abstract.check_returncode()
    pin_inputs = dict(scope='All nine core-reference/distribution/vref/enable-gate masters; routing excluded', cells=[])
    for name, info in masters.items():
        pin_inputs['cells'].append(dict(cell=name, gds=info['file'], lef=name+'.lef',
                                       gds_sha256=hashlib.sha256((out/info['file']).read_bytes()).hexdigest(),
                                       lef_sha256=hashlib.sha256((out/(name+'.lef')).read_bytes()).hexdigest()))
    (out/'pin-inputs.json').write_text(json.dumps(pin_inputs,indent=2)+'\n')
    body = core['text'].split('.subckt pt_core_bias ', 1)[1].splitlines()[1:]
    instances = []
    for line in body:
        if not line.startswith('X'):
            continue
        words = line.split()
        master = words[-1]
        assert master in masters
        connections = dict(zip(ports(core['text'], master), words[1:-1]))
        assert len(ports(core['text'], master)) == len(words)-2
        if master == 'gf180mcu_ocd_ip__biasgen':
            # Qualified hierarchy explicitly shares its substrate ground.
            connections['avss'] = connections['dvss']
        private = [p for p in connections if master == 'bringup_and' and p not in ('A','B','Y','VDD','VSS')]
        instances.append(dict(name=words[0], master=master, connections=connections,
                              extracted_private_pins=private))
    assert len(instances) == 37 and len(core['control_instances']) == 28
    manifest = dict(plan=plan or {}, masters=masters, instances=instances, boundary_pins=core['pins'],
                    control_bindings=core['control_bindings'], observation_bindings=core['observation_bindings'])
    (out/'placement-inputs.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (out/'layout.py').write_text(LAYOUT)
    run = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '4g',
                          '--entrypoint', '/bin/bash', '-v', f'{out}:/work', '-w', '/work', IMAGE,
                          '-lc', 'klayout -b -r /work/layout.py'], capture_output=True, text=True, timeout=180)
    (out/'layout.log').write_text(run.stdout+run.stderr)
    run.check_returncode()
    geometry = json.loads((out/'geometry-audit.json').read_text())
    terminals = json.loads((out/'physical-terminals.json').read_text())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p,h in sources.items())
    result = dict(status='unrouted_placement', instances=len(instances), boundary_pins=len(core['pins']),
                  geometry=geometry, source_hashes=sources, image=IMAGE,
                  physical_terminals=terminals['terminal_count'], physical_nets=len(terminals['nets']),
                  artifact_hashes={f:hashlib.sha256((out/f).read_bytes()).hexdigest() for f in
                                   ['pt_core_bias_placement.gds','pt_core_bias.spice','placement-inputs.json','geometry-audit.json',
                                    'physical-terminals.json','pin-inputs.json','pin-audit.json','bringup_and.lef']},
                  remaining=['route all nets and export accessible boundary pins',
                             'power grid, isolation boundaries, guard rings and substrate routing',
                             'place in the provider core with the rest of the chip',
                             'assembled DRC/LVS, antenna, density and extracted simulation'])
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(status=result['status'], instances=len(instances), boundary_pins=len(core['pins']),
                          bbox_um=geometry['bbox_um']), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'scratch/core-bias-physical-placement')
    parser.add_argument('--compact', action='store_true',
                        help='I9: 950 x 330 um die (fits >= 100 um from the macro); per-island banks kept whole')
    a = parser.parse_args()
    place(a.output_dir.resolve(), COMPACT_PLAN if a.compact else None)
