"""Connect the physical primary macro to the TX replacement base.

Parameterized placement candidate. No protection rating or ring-fit claim.
"""
import argparse
import json
import re
import hashlib
from pathlib import Path
import shutil
import subprocess


def assemble(work):
    import klayout.db as k
    cfg=json.loads((work/'config.json').read_text());ox,oy=cfg['origin_um'];gx,gy=cfg['ground_anchor_um']
    l=k.Layout();l.read(str(work/'base.gds'));base=l.top_cell()
    root=l.create_cell('tx_with_primary');root.copy_tree(base)
    l.read(str(work/'network.gds'));network=l.cell('protection_network');network.flatten(False)
    for ix in l.layer_indexes():
        for shape in list(network.each_shape(ix)):
            if shape.is_text():shape.delete()
    root.insert(k.DCellInstArray(network.cell_index(),k.DTrans(float(ox),float(oy))))
    metals={1:34,2:36,3:42,4:46,5:81};vias={1:35,2:38,3:40,4:41};routes=[]
    def box(layer,x1,y1,x2,y2):root.shapes(l.layer(layer,0)).insert(k.DBox(x1,y1,x2,y2))
    def wire(level,a,b,width):
        assert a[0]==b[0] or a[1]==b[1]
        h=width/2;box(metals[level],min(a[0],b[0])-h,min(a[1],b[1])-h,max(a[0],b[0])+h,max(a[1],b[1])+h)
        routes.append(dict(layer=level,start_um=a,end_um=b,width_um=width))
    def stack(x,y,lo,hi):
        for level in range(lo,hi+1):box(metals[level],x-1,y-1,x+1,y+1)
        for level in range(lo,hi):
            for dx in (-.6,0.,.6):
                for dy in (-.6,0.,.6):box(vias[level],x+dx-.13,y+dy-.13,x+dx+.13,y+dy+.13)
    for leg,cx,y,outer,px,py in [('P',37.5,400.,ox+288.,ox+186.,oy+40.),('N',248.5,412.,ox+304.,ox+190.,oy+60.)]:
        stack(cx,y,2,4);wire(4,(cx,y),(outer,y),8.)
        stack(outer,y,4,5);wire(5,(outer,y),(outer,py),8.)
        stack(outer,py,4,5);wire(4,(outer,py),(px,py),8.);stack(px,py,3,4)
    ground=ox+320.
    wire(4,(ox+138.,oy+4.),(ground,oy+4.),4.);stack(ground,oy+4.,4,5)
    wire(5,(ground,oy+4.),(ground,gy),8.);stack(ground,gy,4,5)
    wire(4,(ground,gy),(gx,gy),4.);stack(gx,gy,4,5)
    root.shapes(l.layer(42,10)).insert(k.DText('ESD_RAIL',k.DTrans(float(ox+130.),float(oy+4.))))
    if cfg.get('atb_port_um'):
        # Stress-safe network: expose the high-value protection-rail ATB tap.
        ax,ay=cfg['atb_port_um']
        root.shapes(l.layer(42,10)).insert(k.DText('ATB_ESD_RAIL',k.DTrans(float(ox+ax),float(oy+ay))))
    opts=k.SaveLayoutOptions();opts.select_cell(root.cell_index());l.write(str(work/'combined.gds'),opts)
    (work/'routes.json').write_text(json.dumps(routes,indent=2)+'\n')
    metadata=json.loads((work/'base-layout.json').read_text())
    regions=metadata['allocation_regions_um'][:]
    if cfg.get('network_regions_um'):
        # Non-rectangular macro (network plus stress shunt): use its declared boxes.
        regions += [[x0+ox,y0+oy,x1+ox,y1+oy] for x0,y0,x1,y1 in cfg['network_regions_um']]
    else:
        b=network.dbbox();regions.append([b.left+ox,b.bottom+oy,b.right+ox,b.top+oy])
    for route in routes:
        a,b=route['start_um'],route['end_um'];h=route['width_um']/2
        regions.append([min(a[0],b[0])-h,min(a[1],b[1])-h,max(a[0],b[0])+h,max(a[1],b[1])+h])
    union=k.Region()
    for coords in regions:union.insert(k.DBox(*coords).to_itype(l.dbu))
    union.merge()
    physical_box=root.dbbox()
    for key in ('device_count','net_count','candidate_size_um','area_um2'):
        if key in metadata:metadata['base_'+key]=metadata.pop(key)
    metadata.pop('protection_device_centers_y_um',None)
    metadata['physical_bbox_um']=[physical_box.left,physical_box.bottom,physical_box.right,physical_box.top]
    metadata['candidate_size_um']=[max(0.,physical_box.right),max(0.,physical_box.top)]
    metadata['area_um2']=union.area()*l.dbu**2
    metadata['area_basis']='Allocated nonrectangular union, not material area or bounding rectangle.'
    metadata.update(flat_cell='tx_with_primary',allocation_regions_um=regions,
        allocation_union_um2=union.area()*l.dbu**2,
        fits_assigned_area=union.area()*l.dbu**2<=metadata['area_ceiling_um2'],
        requires_attached_primary_protection=False,connected_primary_candidate=True)
    (work/'placement-layout.json').write_text(json.dumps(metadata,indent=2)+'\n')



def export_model(work, network, pdk):
    from protection_device_audit import check
    raw=work/'combined_flat.spice';text=raw.read_text();lines=text.splitlines()
    manifest=json.loads((network/'network-layout.json').read_text())
    correction=manifest['array_well_capacitance_removed_ff'];changed=0
    for i,line in enumerate(lines):
        fields=line.split()
        if fields and fields[0].startswith('C') and set(fields[1:3])=={'VSS','ESD_RAIL'}:
            value=float(fields[3][:-1])*{'f':1.,'p':1000.}[fields[3][-1]]
            if value<=correction:raise ValueError('Insufficient well-area capacitance')
            lines[i]=' '.join(fields[:3])+f' {value-correction:.12g}f';changed+=1
    if changed!=1:raise ValueError('Ambiguous extracted protection-rail capacitor')
    well=next(line for line in (network/'network-with-well.spice').read_text().splitlines() if line.startswith('DWELL_ARRAY '))
    well=well.replace(' RAIL ',' ESD_RAIL ')
    end=next(i for i,line in enumerate(lines) if line.startswith('.ends'));lines.insert(end,well)
    joined=re.sub(r'\n\+\s*',' ',text)
    ports=next(line.split()[2:] for line in joined.splitlines() if line.startswith('.subckt'))
    public=[port for port in ports if port!='ESD_RAIL']
    wrapper='.subckt tx_protected_pad '+' '.join(public)+'\nXPHYSICAL '+' '.join(ports)+' combined_flat\n.ends tx_protected_pad\n'
    model=work/'physical.spice'
    model.write_text(wrapper+'\n'.join(lines)+f'\n.lib {pdk}/sm141064.ngspice diode_typical\n.lib {pdk}/sm141064.ngspice mimcap_typical\n')
    result=check(work/'combined_flat.ext',model,work/'model-audit.json',raw)
    if not result['device_graph_matches']:raise ValueError('Combined model differs from physical extraction')
    return model


def generate(work,base,network,origin,pdk=None):
    from layout import IMAGE,magic
    work.mkdir(parents=True,exist_ok=False)
    meta=json.loads((base/'layout-report.json').read_text())
    if not meta.get('requires_attached_primary_protection'):raise ValueError('Use the replacement base')
    family=meta['family']
    if family not in ('wired_transmit','reference_clock','wired_receive_usb'):raise ValueError('Unsupported primary-protection family')
    base_gds=base/(meta['flat_cell']+'.gds')
    base_schematic=base/('pad_'+family+'.spice')
    ground_anchor=[meta['net_track_x_um']['VSS'],meta['port_heights_um']['VSS']]
    for source,name in ((base_gds,'base.gds'),(base/'layout-report.json','base-layout.json'),(network/'network.gds','network.gds'),(Path(__file__),'wired_protection_layout.py')):shutil.copyfile(source,work/name)
    network_meta=json.loads((network/'network-layout.json').read_text())
    atb=network_meta.get('ports',{}).get('ATB_RAIL')
    (work/'config.json').write_text(json.dumps(dict(origin_um=origin,ground_anchor_um=ground_anchor,atb_port_um=atb,network_regions_um=network_meta.get('allocation_regions_um')))+'\n')
    subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3','--mount',f'type=bind,src={work},dst=/work',IMAGE,'/work/wired_protection_layout.py','--inside','--output-dir','/work'],check=True)
    (work/'extract.tcl').write_text('crashbackups stop\ngds read combined.gds\nload tx_with_primary\nselect top cell\nflatten combined_flat\nload combined_flat\nselect top cell\nexpand\ndrc check\ndrc catchup\nputs "COMBINED_DRC [drc list count total]"\nputs [drc listall why]\nextract all\next2spice lvs\next2spice cthresh 0\next2spice\nsave\nquit -noprompt\n')
    result=magic(work,'extract.tcl')
    if not re.search(r'COMBINED_DRC 0\b',result.stdout):raise ValueError('Combined TX DRC failed')
    from run_first_pass import lvs
    from protection_device_audit import check
    base_text=(base_schematic).read_text()
    definition=next(line.split() for line in base_text.splitlines() if line.startswith('.subckt'))
    base_cell=definition[1];ports=definition[2:]
    extra=' ATB_ESD_RAIL' if atb else ''
    reference=base_text+(network/'network_flat.spice').read_text()+'\n.subckt expected '+' '.join(ports)+' ESD_RAIL'+extra+'\nXBASE '+' '.join(ports)+' '+base_cell+'\nXPRIMARY VSS ESD_RAIL PAD_P PAD_N'+extra+' network_flat\n.ends expected\n'
    strip=lambda text:'\n'.join(line for line in text.splitlines() if not line.startswith('C'))+'\n'
    (work/'reference.spice').write_text(strip(reference))
    (work/'actual.spice').write_text(strip((work/'combined_flat.spice').read_text()))
    if not lvs(work,'actual.spice','combined_flat','reference.spice','expected','combined-lvs.txt'):
        raise ValueError('Connected TX device graph failed LVS')
    independent=check(work/'combined_flat.ext',work/'combined_flat.spice',work/'independent-device-audit.json')
    if not independent['device_graph_matches']:raise ValueError('Independent physical device audit failed')
    placement=json.loads((work/'placement-layout.json').read_text())
    placement['device_count']=independent['physical_devices']
    staging=work/'placement-layout.updated.json'
    staging.write_text(json.dumps(placement,indent=2)+'\n')
    staging.replace(work/'placement-layout.json')
    report=dict(status='connected_primary_layout_verified_not_canonical',family=family,drc_count=0,
        device_count=independent['physical_devices'],device_lvs_match=True,independent_device_graph_match=True,
        limitations=['ESD_RAIL is an extraction port to hide inside the simulation wrapper, not a new bond pin.',
                     'Nonlinear well correction, extracted loading screens, provider placement and area accounting pending.',
                     'No ESD rating, core-survival or current-capacity claim.'],
        source_sha256={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in
            (Path(__file__),base_gds,base_schematic,network/'network.gds',network/'network_flat.spice')})
    if pdk is not None:
        model=export_model(work,network,pdk)
        report['simulation_model_sha256']=hashlib.sha256(model.read_bytes()).hexdigest()
        report['nonlinear_well_replacement_checked']=True
    (work/'layout-screen.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--inside',action='store_true')
    p.add_argument('--base-dir',type=Path);p.add_argument('--network-dir',type=Path);p.add_argument('--origin-um',type=float,nargs=2,default=[160.,700.])
    p.add_argument('--pdk-model-dir',type=Path)
    a=p.parse_args()
    if a.inside:assemble(a.output_dir)
    else:generate(a.output_dir.resolve(),a.base_dir.resolve(),a.network_dir.resolve(),a.origin_um,a.pdk_model_dir.resolve() if a.pdk_model_dir else None)
