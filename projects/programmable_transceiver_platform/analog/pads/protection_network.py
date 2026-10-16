"""Physically join the steering array to its isolated rail clamp.

This is an integration macro, not a qualified ESD cell. Pad attachment and
current capacity remain explicit acceptance gaps.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROUTING = dict(rail_width_um=8., return_width_um=12., port_via_cuts_per_axis=3, port_via_pitch_um=.6)


def assemble(work):
    import klayout.db as k
    layout=k.Layout();layout.read(str(work/'clamp.gds'));layout.read(str(work/'array.gds'));layout.read(str(work/'bleed.gds'))
    clamp=layout.cell('pad_isolated_rail_clamp_layout');array=layout.cell('steering_array')
    cfg=json.loads((work/'clamp-layout.json').read_text())
    # Remove labels only; all physical device and interconnect geometry remains.
    for cell in layout.each_cell():
        for ix in layout.layer_indexes():
            for shape in list(cell.each_shape(ix)):
                if shape.is_text():shape.delete()
    root=layout.create_cell('protection_network')
    root.insert(k.DCellInstArray(clamp.cell_index(),k.DTrans()))
    root.insert(k.DCellInstArray(array.cell_index(),k.DTrans(150.,20.)))
    root.insert(k.DCellInstArray(layout.cell('bleed').cell_index(),k.DTrans(235.,144.)))
    def rect(layer,x1,y1,x2,y2):
        root.shapes(layout.layer(layer,0)).insert(k.DBox(x1,y1,x2,y2).to_itype(layout.dbu))
    def wire(layer,a,b,width):
        assert a[0]==b[0] or a[1]==b[1]
        h=width/2;rect(layer,min(a[0],b[0])-h,min(a[1],b[1])-h,max(a[0],b[0])+h,max(a[1],b[1])+h)
    def stack(x,y,hi,cuts=1):
        pitch=ROUTING['port_via_pitch_um'];half=(cuts-1)*pitch/2+.25
        for layer in ([42,46,81] if hi==5 else [42,46]):rect(layer,x-half,y-half,x+half,y+half)
        for via in ([40,41] if hi==5 else [40]):
            for i in range(cuts):
                for j in range(cuts):
                    cx=x+(i-(cuts-1)/2)*pitch;cy=y+(j-(cuts-1)/2)*pitch
                    rect(via,cx-.14,cy-.14,cx+.14,cy+.14)
    # Separate layers carry rail and return; no signal switching devices added.
    ra=cfg['gate_landings_um']['rail'];gr=cfg['ground_landing_um']
    wire(81,ra,(130.,ra[1]),ROUTING['rail_width_um']);wire(81,(130.,ra[1]),(130.,4.),ROUTING['rail_width_um']);stack(130.,4.,5,ROUTING['port_via_cuts_per_axis'])
    wire(46,gr,(138.,gr[1]),ROUTING['return_width_um']);wire(46,(138.,gr[1]),(138.,4.),ROUTING['return_width_um']);stack(138.,4.,4,ROUTING['port_via_cuts_per_axis'])
    bleed=json.loads((work/'bleed-layout.json').read_text())
    bp={name:(235.+point[0],144.+point[1]) for name,point in bleed['terminals_um'].items()}
    def low_stack(point,hi):
        x,y=point
        metals={1:34,2:36,3:42,4:46};vias={1:35,2:38,3:40}
        for level in range(1,hi+1):rect(metals[level],x-.25,y-.25,x+.25,y+.25)
        for level in range(1,hi):
            h=.13 if level==1 else .14
            rect(vias[level],x-h,y-h,x+h,y+h)
    low_stack(bp['RAIL'],2)
    # M2 rail route lands on existing M3 rail; M4 carries the return below it.
    rail_landing=(130.,bp['RAIL'][1]);x,y=rail_landing
    rect(36,x-.25,y-.25,x+.25,y+.25);rect(38,x-.14,y-.14,x+.14,y+.14)
    wire(36,rail_landing,bp['RAIL'],.5)
    low_stack(bp['VSS'],4)
    wire(46,(138.,4.),(bp['VSS'][0],4.),1.)
    wire(46,(bp['VSS'][0],4.),bp['VSS'],1.)
    low_stack(bp['BODY'],3)
    wire(42,bp['BODY'],(274.,bp['BODY'][1]),1.)
    wire(42,(274.,bp['BODY'][1]),(274.,4.),1.)
    stack(274.,4.,4);wire(46,(bp['VSS'][0],4.),(274.,4.),1.)
    ports={'VSS':(138.,4.),'RAIL':(130.,4.),'PADP':(186.,4.),'PADN':(190.,4.)}
    for name,point in ports.items():root.shapes(layout.layer(42,10)).insert(k.DText(name,k.DTrans(*point)))
    opts=k.SaveLayoutOptions();opts.add_cell(root.cell_index());layout.write(str(work/'network.gds'),opts)
    (work/'geometry.json').write_text(json.dumps(dict(bbox_um=str(root.dbbox()),array_origin_um=[150.,20.],ports_um=ports,routing_parameters=ROUTING,rail_route_length_um=130.-ra[0]+ra[1]-4.,return_route_length_um=138.-gr[0]+gr[1]-4.),indent=2)+'\n')


def generate(work,generated):
    from layout import magic,IMAGE
    from run_first_pass import lvs
    work.mkdir(parents=True,exist_ok=False)
    clamp=generated/'protection-clamp';array=generated/'protection-array';bleed=generated/'protection-bleed'
    for folder,files in [(clamp,['clamp.gds','clamp-layout.json','clamp-reference.spice']),
                         (array,['array.gds','array-layout.json','array_flat.spice']),
                         (bleed,['bleed.gds','bleed-layout.json','bleed.spice'])]:
        for name in files:shutil.copy2(folder/name,work/name)
    for path in [clamp/'clamp-layout.json',array/'array-layout.json',bleed/'bleed-layout.json']:
        report=json.loads(path.read_text())
        if report['drc_count']:raise ValueError('Input macro DRC failure')
        for source,digest in report['source_sha256'].items():
            if hashlib.sha256(Path(source).read_bytes()).hexdigest()!=digest:raise ValueError('Stale input: '+source)
    shutil.copy2(Path(__file__),work/'protection_network.py')
    subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3','--mount',f'type=bind,src={work},dst=/work',IMAGE,'/work/protection_network.py','--inside','--output-dir','/work'],check=True,timeout=60)
    (work/'extract.tcl').write_text('''crashbackups stop
gds read network.gds
load protection_network
select top cell
flatten network_flat
load network_flat
save
select top cell
expand
drc check
drc catchup
puts "NETWORK_DRC [drc list count total]"
puts [drc listall why]
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice
quit -noprompt
''')
    result=magic(work,'extract.tcl');match=re.search(r'NETWORK_DRC (\d+)',result.stdout)
    if not match or int(match[1]):raise ValueError('Network DRC failed: inspect extraction log')
    physical=(work/'network_flat.spice').read_text()
    reference=(work/'clamp-reference.spice').read_text()+(work/'array_flat.spice').read_text()+(work/'bleed.spice').read_text()+'''
.subckt protection_reference VSS RAIL PADP PADN
XA VSS RAIL PADP PADN array_flat
XC VSS RAIL RCLOCAL clamp_reference
XB RAIL VSS VSS bleed
.ends protection_reference
'''
    strip=lambda text:'\n'.join(line for line in text.splitlines() if not line.startswith('C'))+'\n'
    (work/'reference.spice').write_text(strip(reference));(work/'network-lvs.spice').write_text(strip(physical))
    if not lvs(work,'network-lvs.spice','network_flat','reference.spice','protection_reference','network-lvs.txt'):
        raise ValueError('Connected protection network LVS mismatch')
    # No new well overlap is allowed by placement. Remove only array well-area
    # capacitance, leaving the native clamp extraction exactly as before.
    wells=json.loads((work/'array-layout.json').read_text())['geometry']['wells']
    correction_ff=wells['area_um2']*.120
    lines=physical.splitlines();corrected=False
    for i,line in enumerate(lines):
        t=line.split()
        if t and t[0].startswith('C') and set(t[1:3])=={'RAIL','VSS'}:
            value=float(t[3][:-1])*{'f':1.,'p':1000.}[t[3][-1]]
            if value<=correction_ff:raise ValueError('Insufficient extracted well capacitance')
            lines[i]=' '.join(t[:3])+f' {value-correction_ff:.9g}f';corrected=True
    if not corrected:raise ValueError('Missing rail/substrate extraction')
    physical='\n'.join(lines)+'\n'
    physical=physical.replace('.ends',f"DWELL_ARRAY VSS RAIL diode_nw2ps_06v0 area={wells['area_um2']}p pj={wells['perimeter_um']}u\n.ends")
    (work/'network-with-well.spice').write_text(physical)
    subprocess.run([sys.executable,str(Path(__file__).with_name('render.py').resolve()),str(work/'network_flat.mag'),'--output',str(work/'network.png'),'--title','Connected protection array and rail clamp','--primitive'],check=True,timeout=30)
    sources=[Path(__file__),clamp/'clamp.gds',clamp/'clamp-layout.json',array/'array.gds',array/'array-layout.json',bleed/'bleed.gds',bleed/'bleed-layout.json']
    report=dict(status='connected_protection_network_DRC_and_device_LVS_pass_not_ESD_qualification',drc_count=0,device_graph_lvs_match=True,physical_bleed_included=True,bleed_dc=json.loads((work/'bleed-layout.json').read_text())['dc_3p3v'],geometry=json.loads((work/'geometry.json').read_text()),array_well_capacitance_removed_ff=correction_ff,extracted_spice_sha256=hashlib.sha256(physical.encode()).hexdigest(),limitations=['Pad attachment is not implemented in this macro; bleed geometry and its extracted model are included.','Rail and return interconnect use single vias; discharge-current capacity unqualified.','Ordinary DRC and device LVS do not prove ESD survival.'],source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (work/'network-layout.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--inside',action='store_true');p.add_argument('--generated',type=Path,default=Path(__file__).with_name('generated'))
    a=p.parse_args()
    if a.inside:assemble(a.output_dir.resolve())
    else:generate(a.output_dir.resolve(),a.generated.resolve())
