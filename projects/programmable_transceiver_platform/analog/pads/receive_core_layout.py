"""Connected two-leg receiver discharge macro; core placement remains open."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


def assemble(work):
    import klayout.db as k
    metadata = json.loads((work/'primitive-layout.json').read_text())
    layout = k.Layout(); layout.read(str(work/'primitive.gds'))
    primitive = layout.cell('bleed')
    if primitive is None:
        raise ValueError('Missing resistor primitive')
    cell = layout.create_cell('receiver_core_discharge')
    # Two identical orientations; keep the high impedance terminals separate.
    positions = {'P': 6., 'N': 20.}
    for leg, offset in positions.items():
        cell.insert(k.DCellInstArray(primitive.cell_index(), k.DTrans(offset, 46.)))
    def rectangle(layer, x1, y1, x2, y2):
        cell.shapes(layout.layer(layer, 0)).insert(k.DBox(min(x1,x2),min(y1,y2),max(x1,x2),max(y1,y2)))
    def wire(layer, a, b, width=1.):
        assert a[0] == b[0] or a[1] == b[1]
        h=width/2;rectangle(layer,min(a[0],b[0])-h,min(a[1],b[1])-h,max(a[0],b[0])+h,max(a[1],b[1])+h)
    def via(x,y):
        for layer in (34,36):rectangle(layer,x-.5,y-.5,x+.5,y+.5)
        rectangle(35,x-.13,y-.13,x+.13,y+.13)
    def label(name,x,y,layer):
        cell.shapes(layout.layer(layer,10)).insert(k.DText(name,k.DTrans(x,y)))
    for leg,dx in positions.items():
        terminals={name:(point[0]+dx,point[1]+46.) for name,point in metadata['terminals_um'].items()}
        label('RX_'+leg,*terminals['RAIL'],34)
        for name in ('VSS','BODY'):
            x,y=terminals[name];via(x,y)
            # M2 return traces can cross resistor poly without contacting it.
            wire(36,(x,y),(x,2.))
    ground_x=[metadata['terminals_um'][name][0]+dx for dx in positions.values() for name in ('VSS','BODY')]
    wire(36,(min(ground_x),2.),(max(ground_x),2.))
    label('VSS',min(ground_x),2.,36)
    # Stream only this macro and dependencies.
    options=k.SaveLayoutOptions();options.select_cell(cell.cell_index())
    layout.write(str(work/'receiver-core.gds'),options)
    box=cell.dbbox()
    (work/'geometry.json').write_text(json.dumps(dict(bbox_um=[box.left,box.bottom,box.right,box.top],
        area_envelope_um2=box.width()*box.height(),primitive_offsets_um=positions),indent=2)+'\n')


def generate(work,primitive):
    from layout import IMAGE,magic
    work.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(primitive/'bleed.gds',work/'primitive.gds')
    shutil.copyfile(primitive/'bleed-layout.json',work/'primitive-layout.json')
    shutil.copyfile(Path(__file__),work/'receive_core_layout.py')
    subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3','--mount',f'type=bind,src={work},dst=/work',IMAGE,'/work/receive_core_layout.py','--inside','--output-dir','/work'],check=True)
    script='''crashbackups stop
gds read receiver-core.gds
load receiver_core_discharge
select top cell
flatten receiver_core_flat
load receiver_core_flat
select top cell
expand
drc check
drc catchup
puts "CORE_DRC [drc list count total]"
puts [drc listall why]
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice
save
quit -noprompt
'''
    (work/'extract.tcl').write_text(script)
    result=magic(work,'extract.tcl')
    count=re.search(r'CORE_DRC (\d+)',result.stdout)
    if not count or int(count[1]):raise ValueError('Connected receiver macro DRC failed')
    raw=(work/'receiver_core_flat.spice').read_text()
    devices=[line.split() for line in raw.splitlines() if line.startswith('X')]
    if len(devices)!=2:raise ValueError('Expected two discharge resistors')
    expected_device=next(line.split() for line in (primitive/'bleed.spice').read_text().splitlines() if line.startswith('X'))
    for leg in ('P','N'):
        matches=[d for d in devices if d[4]=='ppolyf_u_1k_6p0' and set(d[1:3])=={'RX_'+leg,'VSS'} and d[3]=='VSS']
        if len(matches)!=1:raise ValueError('Receiver discharge/body connectivity mismatch: '+leg)
        if matches[0][4:]!=expected_device[4:]:raise ValueError('Resistor model or dimensions changed: '+leg)
    report=dict(status='connected_receiver_discharge_macro_not_placed_in_core',drc_count=0,
        extracted_resistor_body_connectivity_checked=True,geometry=json.loads((work/'geometry.json').read_text()),
        physical_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        source_sha256={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in (Path(__file__),primitive/'bleed.gds',primitive/'bleed-layout.json',primitive/'bleed.spice')})
    (work/'layout.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--primitive',type=Path)
    parser.add_argument('--inside',action='store_true')
    args=parser.parse_args()
    if args.inside:assemble(args.output_dir)
    else:
        if args.primitive is None:parser.error('--primitive is required')
        generate(args.output_dir.resolve(),args.primitive.resolve())
