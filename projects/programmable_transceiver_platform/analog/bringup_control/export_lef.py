#!/usr/bin/env python3
"""Export and validate a place-and-route abstract for the control macro.

Uses Magic's LEF writer, then checks pin roles with OpenROAD and compares the
export copy against the qualified GDS with KLayout. Only copies are annotated;
the characterized layout, extraction and running assembled test stay frozen.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent/'timing'))
import layout_engine as le
import timing_flow as tf

TOP = 'pt_wtx_fallback_control'
POWER = {'VDD', 'RAIL_wired'}
OUTPUTS = {'TMDS_REQUEST', 'WIRED_ON', 'FORCE_SELECTED'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


XOR_SCRIPT = '''
import json
import pya
a=pya.Layout(); a.read('/work/reference.gds')
b=pya.Layout(); b.read('/work/pt_wtx_fallback_control.export.gds')
assert a.dbu == b.dbu
ca=a.cell('pt_wtx_fallback_control'); cb=b.cell('pt_wtx_fallback_control')
assert ca is not None and cb is not None
layers=set((x.layer,x.datatype) for l in (a,b) for x in (l.get_info(i) for i in l.layer_indices()))
different=[]
for layer,datatype in sorted(layers):
    info=pya.LayerInfo(layer,datatype)
    ia=a.find_layer(info); ib=b.find_layer(info)
    ra=pya.Region(ca.begin_shapes_rec(ia)) if ia is not None else pya.Region()
    rb=pya.Region(cb.begin_shapes_rec(ib)) if ib is not None else pya.Region()
    delta=ra ^ rb
    if not delta.is_empty(): different.append(dict(layer=layer,datatype=datatype,area_dbu2=delta.area()))
result=dict(status='pass' if not different else 'fail',different_layers=different,
            gds_dbu_um=a.dbu,reference_bbox_dbu=str(ca.bbox()),export_bbox_dbu=str(cb.bbox()))
open('/work/gds-xor.json','w').write(json.dumps(result,indent=2)+'\\n')
assert not different, different
'''


OPENROAD_SCRIPT = '''
import json,odb
db=odb.dbDatabase.create()
odb.read_lef(db,'/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef')
odb.read_lef(db,'/work/pt_wtx_fallback_control.lef')
master=db.findMaster('pt_wtx_fallback_control'); assert master is not None
pins={}
for term in master.getMTerms():
    shapes=sum(len(pin.getGeometry()) for pin in term.getMPins())
    assert shapes>0,term.getName()
    pins[term.getName()]=dict(direction=str(term.getIoType()),use=str(term.getSigType()),shapes=shapes)
obstructions=len(master.getObstructions()); assert obstructions>0
dbu=db.getTech().getDbUnitsPerMicron()
result=dict(status='parsed',pins=pins,obstructions=obstructions,
            size_um=[master.getWidth()/dbu,master.getHeight()/dbu])
open('/work/openroad-pins.json','w').write(json.dumps(result,indent=2)+'\\n')
'''

PREVIEW_SCRIPT = '''
import pya,glob
view=pya.LayoutView()
view.load_layout('/work/reference.gds',0)
properties=sorted(glob.glob('/foss/pdks/gf180mcuD/libs.tech/klayout/**/*.lyp',recursive=True))
if properties: view.load_layer_props(properties[0])
view.add_missing_layers(); view.max_hier()
view.set_config('background-color','#ffffff')
view.set_config('text-visible','false')
view.zoom_fit()
view.save_image('/work/control-layout.png',1920,1200)
'''


def export(generated, work, preview=False):
    evidence_path = generated/'evidence.json'
    physical = json.loads(evidence_path.read_text())
    assert physical['status'] == 'pass'
    before = {**physical['source_hashes'], **physical['artifact_hashes']}
    assert all(sha(p) == h for p, h in before.items()), 'stale physical evidence'
    work.mkdir(parents=True, exist_ok=True)
    for path in generated.glob('*.mag'):
        target = work/path.name
        shutil.copyfile(path, target)
        target.chmod(0o666)
    shutil.copyfile(generated/(TOP+'.gds'), work/'reference.gds')
    commands = ['crashbackups stop', f'load {TOP}', 'units microns',
                'box values 0 0 1 1', 'property LEFclass BLOCK']
    expected = {}
    for i, pin in enumerate(physical['ports'], 1):
        direction = 'inout' if pin in POWER or pin == 'VSS' else ('output' if pin in OUTPUTS else 'input')
        use = 'power' if pin in POWER else ('ground' if pin == 'VSS' else 'signal')
        commands += [f'port {i} class {direction}', f'port {i} use {use}']
        expected[pin] = dict(direction=direction.upper(), use=use.upper())
    commands += [f'lef write {TOP}.lef -hide', 'cif ostyle gdsii',
                 f'gds write {TOP}.export.gds', 'quit -noprompt']
    (work/'export.tcl').write_text('\n'.join(commands)+'\n')
    (work/'xor.py').write_text(XOR_SCRIPT)
    (work/'pins.py').write_text(OPENROAD_SCRIPT)
    def run(image, command, log_name):
        shell = ['/bin/sh', '-c'] if image == le.DIGITAL_IMAGE else ['/bin/bash', '-lc']
        result = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '4g',
            '--entrypoint', shell[0], '-v', f'{work}:/work', '-w', '/work', image, shell[1], command],
            capture_output=True, text=True, timeout=180)
        (work/log_name).write_text(result.stdout+result.stderr)
        result.check_returncode()
    run(tf.ANALOG_IMAGE, 'magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc /work/export.tcl', 'export.log')
    run(tf.ANALOG_IMAGE, 'klayout -b -r /work/xor.py', 'xor.log')
    run(le.DIGITAL_IMAGE, 'openroad -exit -python /work/pins.py', 'pins.log')
    xor = json.loads((work/'gds-xor.json').read_text())
    parsed = json.loads((work/'openroad-pins.json').read_text())
    assert xor['status'] == 'pass'
    assert set(parsed['pins']) == set(expected)
    for pin, roles in expected.items():
        for kind, value in roles.items():
            assert parsed['pins'][pin][kind] == value, (pin, kind, parsed['pins'][pin])
    bbox = [int(v)*xor['gds_dbu_um'] for v in re.findall(r'-?\d+', xor['reference_bbox_dbu'])]
    assert len(bbox) == 4
    lef_text = (work/(TOP+'.lef')).read_text()
    origin = [float(v) for v in re.search(r'\bORIGIN\s+([-\d.]+)\s+([-\d.]+)', lef_text).groups()]
    assert all(abs(a-b) < 1e-6 for a, b in zip(origin, [-bbox[0], -bbox[1]])), 'LEF/GDS origin mismatch'
    assert all(abs(a-b) < 1e-6 for a, b in zip(parsed['size_um'],
                    [bbox[2]-bbox[0], bbox[3]-bbox[1]])), 'LEF/GDS bounds mismatch'
    assert all(sha(p) == h for p, h in before.items()), 'qualified layout changed during export'
    destination = generated/(TOP+'.lef')
    shutil.copyfile(work/destination.name, destination)
    report = dict(status='pass', gds_geometry_xor=xor, openroad=parsed,
                  gds_bbox_um=bbox, lef_origin_um=origin,
                  generator_allocation_estimate_um=physical['layout']['size_um'],
                  qualified_gds_sha256=sha(generated/(TOP+'.gds')), lef_sha256=sha(destination),
                  source_hashes={str(p): sha(p) for p in [Path(__file__).resolve(), evidence_path,
                      generated/(TOP+'.mag'), generated/(TOP+'.gds')]},
                  tool_images={name: tf.image_id(name) for name in (le.DIGITAL_IMAGE, tf.ANALOG_IMAGE)},
                  excluded=['full-chip placement, routing and pin-access closure'])
    if preview:
        (work/'preview.py').write_text(PREVIEW_SCRIPT)
        run(tf.ANALOG_IMAGE, 'QT_QPA_PLATFORM=offscreen klayout -b -r /work/preview.py', 'preview.log')
        png = work/'control-layout.png'
        data = png.read_bytes()
        assert data[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', data[16:24]) == (1920, 1200)
        shutil.copyfile(png, generated/(TOP+'.png'))
        report['preview'] = dict(sha256=sha(png), size_px=[1920, 1200],
                                note='Mask geometry overview; pin names and roles are in the LEF/OpenROAD report.')
    (generated/'lef-evidence.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(status='pass', pins=len(parsed['pins']),
                         size_um=parsed['size_um'], geometry_xor_layers=len(xor['different_layers']),
                         lef=str(destination)), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generated', type=Path, default=HERE/'generated')
    parser.add_argument('--work', type=Path, default=ROOT/'scratch/bringup-control-lef')
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    export(args.generated.resolve(), args.work.resolve(), args.preview)
