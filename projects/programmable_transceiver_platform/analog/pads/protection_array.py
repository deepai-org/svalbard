"""Connected differential steering arrays; no inferred ESD current rating."""
from decimal import Decimal
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


def assemble(work):
    import klayout.db as k
    cfg=json.loads((work/'config.json').read_text())
    layout=k.Layout()
    for model in cfg['primitives']:
        layout.read(str(work/(model+'.gds')))
    # Instance labels must not alias otherwise independent terminal nets.
    for cell in layout.each_cell():
        for ix in layout.layer_indexes():
            for shape in list(cell.each_shape(ix)):
                if shape.is_text():shape.delete()
    root=layout.create_cell('steering_array')
    def rect(layer,x1,y1,x2,y2):
        root.shapes(layout.layer(layer,0)).insert(k.DBox(x1,y1,x2,y2).to_itype(layout.dbu))
    def wire(layer,a,b,width):
        assert a[0]==b[0] or a[1]==b[1]
        h=width/2;rect(layer,min(a[0],b[0])-h,min(a[1],b[1])-h,max(a[0],b[0])+h,max(a[1],b[1])+h)
    def via(x,y,lower):
        layers={1:(34,35,36),2:(36,38,42)}
        a,v,b=layers[lower]
        for layer in (a,b):rect(layer,x-.24,y-.24,x+.24,y+.24)
        h=.13  # GDS cut: every via is exactly 0.26 um (KLayout V*.1)
        rect(v,x-h,y-h,x+h,y+h)
    buses={'VSS':-12.,'RAIL':-20.,'PADP':36.,'PADN':40.}
    placements=[]
    # PD21 (HBM item a): optional extra up-diode rows (pad -> RAIL), one per leg above the canonical
    # four rows (y 160 + 40*leg), same fingers and bus taps. extra_up_rows=0 reproduces the canonical array.
    extra=cfg.get('extra_up_rows',0)
    rows=[(leg,pad,upper,model,leg*80+upper*40) for leg,pad in enumerate(('PADP','PADN')) for upper,model in enumerate(cfg['primitives'])]
    up_model=[m for m in cfg['primitives'] if m=='diode_pd2nw_06v0'][0]
    rows+=[(leg,pad,1,up_model,160+40*(2*r+leg)) for r in range(extra) for leg,pad in enumerate(('PADP','PADN'))]
    for leg,pad,upper,model,y in rows:
        if True:
            mappings={'A':pad,'K':'RAIL','SUB':'VSS'} if upper else {'A':'VSS','K':pad}
            offsets={'A':0.,'K':8.,'SUB':-8.} if upper else {'A':-8.,'K':0.}
            for finger in range(cfg['fingers']):
                x=finger*8.
                cell=layout.cell(model)
                root.insert(k.DCellInstArray(cell.cell_index(),k.DTrans(x,y)))
                placements.append(dict(model=model,pad=pad,origin_um=[x,y]))
                for terminal,net in mappings.items():
                    tx=x+cfg['primitives'][model]['terminals_um'][terminal][0];ty=y+offsets[terminal]
                    # Check the actual M1 landing before adding any metal.
                    m1=k.Region(cell.begin_shapes_rec(layout.layer(34,0)))
                    landing=k.Region(k.DBox(tx-x-.10,ty-y-.10,tx-x+.10,ty-y+.10).to_itype(layout.dbu))
                    if not (landing-m1).is_empty():raise ValueError('Terminal via misses primitive M1: '+terminal)
                    via(tx,ty,1);wire(36,(tx,ty),(buses[net],ty),.48);via(buses[net],ty,2)
    top=136.+80.*extra
    for net,x in buses.items():
        wire(42,(x,-16.),(x,top),2.)
        root.shapes(layout.layer(42,10)).insert(k.DText(net,k.DTrans(x,-16.)))
    opts=k.SaveLayoutOptions();opts.add_cell(root.cell_index());layout.write(str(work/'array.gds'),opts)
    wells=k.Region(root.begin_shapes_rec(layout.layer(21,0))).merged()
    well_geometry=dict(area_um2=wells.area()*layout.dbu**2,perimeter_um=wells.perimeter()*layout.dbu,count=wells.count())
    (work/'geometry.json').write_text(json.dumps(dict(bbox_um=str(root.dbbox()),placements=placements,buses_um=buses,wells=well_geometry),indent=2)+'\n')


def generate(work,primitives,fingers,extra_up_rows=0):
    from layout import magic,IMAGE
    if not 1<=fingers<=4:raise ValueError('Current bus envelope supports one to four fingers')
    work.mkdir(parents=True,exist_ok=False)
    data=json.loads((primitives/'protection-primitives.json').read_text())
    cfg=dict(primitives=data['primitives'],fingers=fingers)
    if extra_up_rows:cfg['extra_up_rows']=extra_up_rows
    (work/'config.json').write_text(json.dumps(cfg))
    for model in cfg['primitives']:shutil.copy2(primitives/(model+'.gds'),work/(model+'.gds'))
    shutil.copy2(Path(__file__),work/'protection_array.py')
    subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3','--mount',f'type=bind,src={work},dst=/work',IMAGE,'/work/protection_array.py','--inside','--output-dir','/work'],check=True,timeout=60)
    script='''crashbackups stop
gds read array.gds
load steering_array
select top cell
flatten array_flat
load array_flat
save
select top cell
expand
drc check
drc catchup
puts "ARRAY_DRC [drc list count total]"
puts [drc listall why]
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice
quit -noprompt
'''
    (work/'extract.tcl').write_text(script);result=magic(work,'extract.tcl')
    match=re.search(r'ARRAY_DRC (\d+)',result.stdout)
    if not match or int(match[1]):raise ValueError('Array DRC failed; inspect extract.tcl.log')
    physical=(work/'array_flat.spice').read_text()
    devices=[line.split() for line in physical.splitlines() if line.startswith('D')]
    expected={('VSS',pad,'diode_nd2ps_06v0'):fingers for pad in ('PADP','PADN')}
    expected.update({(pad,'RAIL','diode_pd2nw_06v0'):fingers*(1+extra_up_rows) for pad in ('PADP','PADN')})
    actual={}
    for d in devices:
        key=tuple(d[1:4]);actual[key]=actual.get(key,0)+1
        params=dict(t.split('=') for t in d[4:])
        assert abs(float(params['area'].removesuffix('p'))-data['junction_width_um']*data['finger_width_um'])<1e-6
    if actual!=expected:raise ValueError(f'Array connectivity mismatch: {actual}')
    # Replace only the linear well-area term, preserving routed coupling.
    geometry=json.loads((work/'geometry.json').read_text())
    well=geometry['wells'];unit=data['primitives']['diode_pd2nw_06v0']
    if well['count']!=2*fingers*(1+extra_up_rows) or abs(well['area_um2']-2*fingers*(1+extra_up_rows)*unit['nwell_area_um2'])>1e-5:
        raise ValueError('Unexpected merged or missing wells')
    tech=subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3',IMAGE,'-c','from pathlib import Path; print(Path("/pdk/gf180mcuD/libs.tech/magic/gf180mcuD.tech").read_text(),end="")'],capture_output=True,text=True,check=True,timeout=30).stdout
    if hashlib.sha256(tech.encode()).hexdigest()!=data['extraction_technology_sha256']:
        raise ValueError('Primitive/array extraction technology mismatch')
    changed,count=re.subn(r'(?m)^defaultareacap\s+nwell\s+well\s+120\s*$','defaultareacap nwell well 0',tech)
    if count!=3:raise ValueError('Unexpected well extraction coefficients')
    (work/'no-well-area.tech').write_text(changed)
    (work/'array-linear-well.spice').write_text(physical)
    (work/'nonlinear.tcl').write_text('crashbackups stop\ntech load /work/no-well-area.tech\nload array_flat\nextract all\next2spice lvs\next2spice cthresh 0\next2spice\nquit -noprompt\n')
    magic(work,'nonlinear.tcl')
    residual=(work/'array_flat.spice').read_text()
    def well_cap(text):
        total=0.;rounding=0.
        for line in text.splitlines():
            t=line.split()
            if t and t[0].startswith('C') and set(t[1:3])=={'RAIL','VSS'}:
                scale={'f':1.,'p':1000.}[t[3][-1]]
                printed=Decimal(t[3][:-1])
                total+=float(printed)*scale
                rounding+=.5*10**printed.as_tuple().exponent*scale
        return total,rounding
    before,before_rounding=well_cap(physical)
    after,after_rounding=well_cap(residual)
    removed=before-after
    rounding_bound=before_rounding+after_rounding
    if abs(removed-well['area_um2']*.120)>rounding_bound+1e-9:raise ValueError('Well capacitance correction exceeds printed-value rounding bound')
    corrected=residual.replace('.ends',f"DWELL VSS RAIL diode_nw2ps_06v0 area={well['area_um2']}p pj={well['perimeter_um']}u\n.ends")
    (work/'array-with-well.spice').write_text(corrected)
    subprocess.run([sys.executable,str(Path(__file__).with_name('render.py').resolve()),str(work/'array_flat.mag'),'--output',str(work/'array.png'),'--title','Differential steering array','--primitive'],check=True,timeout=30)
    report=dict(status='connected_array_DRC_and_diode_graph_pass_not_ESD_qualification',drc_count=0,fingers_per_diode=fingers,extra_up_rows=extra_up_rows,diode_count=len(devices),geometry=geometry,removed_linear_well_capacitance_ff=removed,well_capacitance_rounding_bound_ff=rounding_bound,extracted_spice_sha256=hashlib.sha256(corrected.encode()).hexdigest(),limitations=['Not connected to pads or clamp yet.','Single terminal vias are not discharge-current qualified.','Nonlinear well junction reconstructed from isolated physical wells; linear well-area term removed, other extracted coupling retained.'],source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),primitives/'protection-primitives.json',*[primitives/(m+'.gds') for m in cfg['primitives']]]})
    (work/'array-layout.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--inside',action='store_true');p.add_argument('--primitives',type=Path,default=Path(__file__).with_name('generated')/'protection-primitives');p.add_argument('--fingers',type=int,default=4);p.add_argument('--extra-up-rows',type=int,default=0)
    a=p.parse_args()
    if a.inside:assemble(a.output_dir.resolve())
    else:generate(a.output_dir.resolve(),a.primitives.resolve(),a.fingers,a.extra_up_rows)
