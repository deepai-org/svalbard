"""Parametric physical rail bleed; extracted resistance, not an ideal 10 Mohm."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import re
import numpy as np
from layout import magic,rectangles,IMAGE
from screen import control,run_spice


def generate(work,pdk,*,fingers=40,length_um=250.,width_um=1.):
    if not 2<=fingers<=100 or width_um<1 or length_um<1:raise ValueError('Invalid bleed geometry')
    work.mkdir(parents=True,exist_ok=False)
    (work/'generate.tcl').write_text(f'''crashbackups stop
load workspace
units internal
set cell [magic::gencell_makecell gf180mcu::ppolyf_u_1k_6p0 w {width_um} l {length_um} nx {fingers} snake 1 guard 1 full_metal 1 res_spacing 0.7]
load $cell
save bleed
quit -noprompt
''');magic(work,'generate.tcl')
    geometry=rectangles(work/'bleed.mag');contacts=sorted(geometry['polycontact'])
    if len(contacts)!=2:raise ValueError('Expected two snake terminal contacts')
    center=lambda r:((r[0]+r[2])/2,(r[1]+r[3])/2)
    terminals={'RAIL':center(contacts[0]),'VSS':center(contacts[1])}
    body_layer=next(k for k in ('psubdiffcont','mvpsubdiffcont','nsubdiffcont') if k in geometry)
    terminals['BODY']=center(max(geometry[body_layer],key=lambda r:r[2]))
    script=['crashbackups stop','load bleed','units microns']
    for i,(name,(x,y)) in enumerate(terminals.items(),1):
        script.extend([f'box values {x-.05} {y-.05} {x+.05} {y+.05}',f'label {name} center metal1',f'port make {i}'])
    script+=['save','select top cell','expand','drc check','drc catchup','puts "BLEED_DRC [drc list count total]"','puts [drc listall why]','extract all','ext2spice lvs','ext2spice cthresh 0','ext2spice','gds write bleed.gds','quit -noprompt']
    (work/'extract.tcl').write_text('\n'.join(script)+'\n');result=magic(work,'extract.tcl')
    match=re.search(r'BLEED_DRC (\d+)',result.stdout)
    if not match or int(match[1]):raise ValueError('Bleed DRC failed')
    before_devices=[line.split()[1:] for line in (work/'bleed.spice').read_text().splitlines() if line.startswith('X')]
    # The installed snake GDS exporter omits HRES despite emitting RESDEF.
    # Materialize its documented HRES rule: connected resistor poly grown .4um.
    repair="""import klayout.db as k
l=k.Layout();l.read('/work/bleed.gds');c=l.cell('bleed')
poly=k.Region(c.begin_shapes_rec(l.layer(30,0))).merged()
marker=k.Region(c.begin_shapes_rec(l.layer(62,0)))
expected=poly.sized(400)
if not marker.is_empty() and not (marker^expected).is_empty():raise ValueError('Unexpected HRES marker')
if marker.is_empty():c.shapes(l.layer(62,0)).insert(expected)
# The same missing bloat-all affects the MV poly's DUALGATE enclosure.
c.shapes(l.layer(55,0)).insert(expected)
l.write('/work/bleed.gds')
"""
    subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3','--mount',f'type=bind,src={work},dst=/work',IMAGE,'-c',repair],check=True,timeout=30)
    # Verify the actual GDS, not just the pre-export Magic representation.
    (work/'roundtrip.tcl').write_text('crashbackups stop\ngds read bleed.gds\nload bleed\nselect top cell\ndrc check\ndrc catchup\nputs "ROUNDTRIP_DRC [drc list count total]"\nputs [drc listall why]\nextract all\next2spice lvs\next2spice cthresh 0\next2spice\nquit -noprompt\n')
    # Avoid reading over the pre-export cell; preserve it outside Magic's search.
    (work/'bleed.mag').rename(work/'bleed-source.mag.saved')
    result=magic(work,'roundtrip.tcl')
    match=re.search(r'ROUNDTRIP_DRC (\d+)',result.stdout)
    if not match or int(match[1]):raise ValueError('Exported bleed DRC failed')
    (work/'bleed-source.mag.saved').rename(work/'bleed.mag')
    physical=(work/'bleed.spice').read_text()
    devices=[line.split() for line in physical.splitlines() if line.startswith('X')]
    if [d[1:] for d in devices]!=before_devices:
        raise ValueError('GDS roundtrip changed resistor dimensions or connectivity')
    if len(devices)!=1 or devices[0][1:5]!=['VSS','RAIL','BODY','ppolyf_u_1k_6p0']:
        raise ValueError('GDS roundtrip changed resistor model or terminal identity')
    if '.subckt bleed RAIL VSS BODY' not in physical:raise ValueError('Bleed port order changed')
    (work/'.spiceinit').write_text('set ngbehavior=hs\n')
    deck=(f'Physical bleed DC loading\n.include {pdk}/design.ngspice\n.lib {pdk}/sm141064.ngspice res_typical\n.temp 27\n'+physical+'\nXBLEED RAIL 0 0 bleed\nVRAIL RAIL 0 3.3\n'+control(work,'dc','dc VRAIL 0 3.3 .1','v(RAIL) i(VRAIL)'))
    previous=Path.cwd()
    try:
        os.chdir(work)
        rows=np.atleast_2d(run_spice(work,'dc',deck))
    finally:os.chdir(previous)
    current=-float(rows[-1,-1]);resistance=float(rows[-1,0])/current
    if not np.isfinite(resistance) or current<=0:raise ValueError('Invalid extracted bleed current')
    subprocess.run([sys.executable,str(Path(__file__).with_name('render.py').resolve()),str(work/'bleed.mag'),'--output',str(work/'bleed.png'),'--title','Physical isolated-rail bleed','--primitive'],check=True,timeout=30)
    all_rects=[r for layer,values in geometry.items() if layer!='checkpaint' for r in values];bbox=[min(r[0] for r in all_rects),min(r[1] for r in all_rects),max(r[2] for r in all_rects),max(r[3] for r in all_rects)]
    report=dict(status='standalone_bleed_DRC_and_extracted_DC_not_integrated',drc_count=0,gds_roundtrip_checked=True,hres_export_rule='Connected poly grown 0.4um on HRES 62/0 and DUALGATE 55/0; materialized because installed snake export omitted these poly enclosures.',parameters=dict(model='ppolyf_u_1k_6p0',fingers=fingers,length_um=length_um,width_um=width_um,res_spacing_um=.7),terminals_um=terminals,bbox_um=bbox,area_envelope_um2=(bbox[2]-bbox[0])*(bbox[3]-bbox[1]),dc_3p3v=dict(current_a=current,resistance_ohm=resistance),extracted_spice_sha256=hashlib.sha256(physical.encode()).hexdigest(),limitations=['BODY must be tied to return during integration.','Nominal model only; no process/temperature or transient stress qualification.','Standalone geometry is not yet included in the protection network.'],source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(__file__).with_name('layout.py'),pdk/'sm141064.ngspice')})
    (work/'bleed-layout.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--pdk-model-dir',type=Path,required=True);p.add_argument('--fingers',type=int,default=40);p.add_argument('--length-um',type=float,default=250.)
    a=p.parse_args();generate(a.output_dir.resolve(),a.pdk_model_dir.resolve(),fingers=a.fingers,length_um=a.length_um)
