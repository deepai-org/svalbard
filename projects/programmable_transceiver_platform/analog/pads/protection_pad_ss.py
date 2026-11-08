"""Attach the extracted protection network to provider-compatible RF bond pads.

First-pass geometry; explicitly report area and discharge-path limitations.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def assemble(work):
    import klayout.db as k
    cfg=json.loads((work/'config.json').read_text());origin=cfg['active_origin_um'];pitch=cfg['bond_pitch_um']
    native=Path('/pdk/gf180mcuD/libs.ref/gf180mcu_fd_io/gds/gf180mcu_fd_io.gds')
    source=k.Layout();source.read(str(native))
    layout=k.Layout();layout.dbu=source.dbu
    # Import only the bond tree: loading the whole library would merge original
    # MOS-capacitor leaves back into the intentionally modified clamp cells.
    bond=layout.create_cell('Bondpad_5LM');bond.copy_tree(source.cell('Bondpad_5LM'))
    layout.read(str(work/'network.gds'));network=layout.cell('protection_network')
    # Only top-level labels define the local extraction interface.
    for cell in layout.each_cell():
        for ix in layout.layer_indexes():
            for shape in list(cell.each_shape(ix)):
                if shape.is_text():shape.delete()
    root=layout.create_cell('rf_protected_pad_pair')
    root.insert(k.DCellInstArray(network.cell_index(),k.DTrans(0.,origin)))
    single=cfg.get('single_leg',False)
    for dx in ((0.,) if single else (0.,pitch)):root.insert(k.DCellInstArray(bond.cell_index(),k.DTrans(dx+5.5,0.)))
    def rect(layer,x1,y1,x2,y2):
        root.shapes(layout.layer(layer,0)).insert(k.DBox(x1,y1,x2,y2).to_itype(layout.dbu))
    def wire(layer,a,b,width):
        assert a[0]==b[0] or a[1]==b[1]
        h=width/2;rect(layer,min(a[0],b[0])-h,min(a[1],b[1])-h,max(a[0],b[0])+h,max(a[1],b[1])+h)
    def stack(x,y,low,high):
        metals={1:34,2:36,3:42,4:46,5:81};vias={1:35,2:38,3:40,4:41}
        for level in range(low,high+1):rect(metals[level],x-.25,y-.25,x+.25,y+.25)
        for level in range(low,high):
            h=.13 if level==1 else .14
            rect(vias[level],x-h,y-h,x+h,y+h)
    routes=[]
    for route in [r for r in cfg['signal_routes'] if not single or r['leg']=='P']:
        leg=route['leg'];cx=route['bond_center_x_um'];escape_y=origin+route['escape_offset_um']
        trunk_x=route['outer_trunk_x_um'];landing_x=route['landing_x_um'];landing_y=origin+route['landing_offset_um']
        segments=[dict(layer=2,start_um=[cx,62.],end_um=[cx,escape_y],width_um=cfg['escape_width_um'],role='bond corridor'),
                  dict(layer=4,start_um=[cx,escape_y],end_um=[trunk_x,escape_y],width_um=route['transverse_width_um'],role='first transverse'),
                  dict(layer=5,start_um=[trunk_x,escape_y],end_um=[trunk_x,landing_y],width_um=route['vertical_width_um'],role='outer vertical'),
                  dict(layer=4,start_um=[trunk_x,landing_y],end_um=[landing_x,landing_y],width_um=route['transverse_width_um'],role='protection transverse')]
        for segment in segments:
            wire({2:36,4:46,5:81}[segment['layer']],segment['start_um'],segment['end_um'],segment['width_um'])
        # Multiple cuts at the bond corridor transition; protection macro still
        # has narrow internal paths that require a separate current audit.
        for dx in (-.6,0.,.6):
            for dy in (-.6,0.,.6):stack(cx+dx,escape_y+dy,2,4)
        for layer in (36,42,46):rect(layer,cx-1.,escape_y-1.,cx+1.,escape_y+1.)
        stack(trunk_x,escape_y,4,5);stack(trunk_x,landing_y,4,5)
        stack(landing_x,landing_y,3,4)
        routes.append(dict(leg=leg,bond_center_x_um=cx,corridor_end_y_um=escape_y,outer_trunk_x_um=trunk_x,protection_landing_um=[landing_x,landing_y],segments=segments))
    ground_routes=[];ground_y=origin+cfg['return_routing']['transverse_offset_um']
    for leg,dx in ([('P',0.)] if single else [('P',0.),('N',pitch)]):
        ground_routes += [dict(a='GND_'+leg,b='TOP_'+leg,layer=2,start_um=[dx+10.,78.305],end_um=[dx+10.,ground_y],width_um=cfg['return_routing']['corridor_width_um']),
                          dict(a='TOP_'+leg,b='JOIN',layer=4,start_um=[dx+10.,ground_y],end_um=[138.,ground_y],width_um=cfg['return_routing']['transverse_width_um'])]
        for xoff in (-.6,0.,.6):
            for yoff in (-.6,0.,.6):stack(dx+10.+xoff,78.305+yoff,2,5)
        for layer in (36,42,46,81):rect(layer,dx+9.,77.305,dx+11.,79.305)
        stack(dx+10.,ground_y,2,4)
    ground_routes.append(dict(a='JOIN',b='PAD_RETURN',layer=5,start_um=[138.,ground_y],end_um=[138.,origin+4.],width_um=cfg['return_routing']['vertical_width_um']))
    for segment in ground_routes:
        wire({2:36,4:46,5:81}[segment['layer']],segment['start_um'],segment['end_um'],segment['width_um'])
    stack(138.,ground_y,4,5);stack(138.,origin+4.,4,5)
    # The existing macro's VSS stack joins the latter route at (138, origin+4).
    if single:
        # ESD_TEST: the second leg (PADN) is terminated to VSS on metal3 below
        # the macro (PADN stub x 189..191 -> VSS stub x 137..139).
        wire(42,(190.,origin+4.),(190.,origin-6.),2.);wire(42,(190.,origin-6.),(138.,origin-6.),2.);wire(42,(138.,origin-6.),(138.,origin+4.),2.)
    for name,x in [('VSS',138.),('ESD_RAIL',130.),('PAD_P',186.)]+([] if single else [('PAD_N',190.)]):
        root.shapes(layout.layer(42,10)).insert(k.DText(name,k.DTrans(x,origin+4.)))
    if cfg.get('atb_port_um'):
        ax,ay=cfg['atb_port_um'];root.shapes(layout.layer(42,10)).insert(k.DText('ATB_ESD_RAIL',k.DTrans(ax,origin+ay)))
    for cell in layout.each_cell():
        if cell.cell_index()!=root.cell_index():cell.name='svrfpad__'+cell.name
    opts=k.SaveLayoutOptions();opts.add_cell(root.cell_index());layout.write(str(work/'pad.gds'),opts)
    # Reserve the complete native bond stack, not just its glass opening.
    bond_top=bond.dbbox().top
    netboxes=[k.DBox(x0,y0+origin,x1,y1+origin) for x0,y0,x1,y1 in cfg['network_regions_um']] if cfg.get('network_regions_um') else [k.DBox(-.055,origin,274.5,origin+288.)]
    regions=netboxes+[k.DBox(0,0,75,bond_top)]+([] if single else [k.DBox(pitch,0,pitch+75,bond_top)])+[k.DBox(0,origin-34,pitch+75,origin)]
    for dx in ((0.,) if single else (0.,pitch)):
        regions += [k.DBox(dx+9.,76.,dx+11.,origin),k.DBox(dx+37.5-cfg['escape_width_um']/2,62.,dx+37.5+cfg['escape_width_um']/2,origin)]
    for route in routes+[dict(segments=ground_routes)]:
        for segment in route['segments']:
            a,b=segment['start_um'],segment['end_um'];h=segment['width_um']/2
            regions.append(k.DBox(min(a[0],b[0])-h,min(a[1],b[1])-h,max(a[0],b[0])+h,max(a[1],b[1])+h))
    union=k.Region()
    for box in regions:union.insert(box.to_itype(layout.dbu))
    report=dict(bbox_um=str(root.dbbox()),routes=routes,ground_routes=ground_routes,allocation_regions_um=[[b.left,b.bottom,b.right,b.top] for b in regions],allocation_union_um2=union.merged().area()*layout.dbu**2,native_bond_source_sha256=hashlib.sha256(native.read_bytes()).hexdigest())
    (work/'geometry.json').write_text(json.dumps(report,indent=2)+'\n')


def generate(work,generated,wide_signals=False,escape_width_um=None,network=None,single_leg=False):
    from layout import magic,IMAGE
    from run_first_pass import lvs
    work.mkdir(parents=True,exist_ok=False)
    meta=json.loads((generated/'rf-receive-layout.json').read_text())
    tx=json.loads((generated/'rf-transmit-layout.json').read_text())
    keys=('active_origin_um','bond_pitch_um','escape_width_um','area_ceiling_um2')
    cfg={key:meta[key] for key in keys}
    if any(tx[key]!=value for key,value in cfg.items()):raise ValueError('RF family placement requirements differ')
    if escape_width_um is not None:
        if not 4. <= escape_width_um <= 24.:
            raise ValueError('Escape width must remain within the 4..24um bond corridor')
        cfg['escape_width_um']=escape_width_um
    cfg['return_routing']=dict(corridor_width_um=8.,transverse_width_um=8.,vertical_width_um=4.,transverse_offset_um=-40.)
    cfg['signal_routes']=[
        dict(leg='P',bond_center_x_um=37.5,escape_offset_um=-24.,outer_trunk_x_um=280.,landing_x_um=186.,landing_offset_um=40.,transverse_width_um=cfg['escape_width_um'],vertical_width_um=2.),
        dict(leg='N',bond_center_x_um=37.5+cfg['bond_pitch_um'],escape_offset_um=-8.,outer_trunk_x_um=284.,landing_x_um=190.,landing_offset_um=60.,transverse_width_um=cfg['escape_width_um']/3.,vertical_width_um=2.)]
    if wide_signals:
        # Keep both outer trunks clear of each other and the bleed macro.
        for route,x in zip(cfg['signal_routes'],(288.,304.)):
            route.update(outer_trunk_x_um=x,transverse_width_um=12.,vertical_width_um=12.)
    network=generated/'protection-network' if network is None else network
    manifest=json.loads((network/'network-layout.json').read_text())
    cfg['atb_port_um']=manifest.get('ports',{}).get('ATB_RAIL')
    cfg['network_regions_um']=manifest.get('allocation_regions_um')
    cfg['single_leg']=single_leg
    (work/'config.json').write_text(json.dumps(cfg))
    if manifest['drc_count'] or not manifest['device_graph_lvs_match'] or not manifest['physical_bleed_included']:raise ValueError('Protection network not checked')
    for source,digest in ({} if cfg['atb_port_um'] else manifest['source_sha256']).items():
        if hashlib.sha256(Path(source).read_bytes()).hexdigest()!=digest:raise ValueError('Stale network input: '+source)
    shutil.copy2(network/'network.gds',work/'network.gds');shutil.copy2(Path(__file__),work/'protection_pad.py')
    subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3','--mount',f'type=bind,src={work},dst=/work',IMAGE,'/work/protection_pad.py','--inside','--output-dir','/work'],check=True,timeout=60)
    (work/'extract.tcl').write_text('''crashbackups stop
gds read pad.gds
load rf_protected_pad_pair
select top cell
flatten pad_flat
load pad_flat
save
select top cell
expand
drc check
drc catchup
puts "PAD_DRC [drc list count total]"
puts [drc listall why]
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice
quit -noprompt
''')
    result=magic(work,'extract.tcl');match=re.search(r'PAD_DRC (\d+)',result.stdout)
    if not match or int(match[1]):raise ValueError('Pad DRC failed: inspect extraction log')
    raw=(work/'pad_flat.spice').read_text()
    ports=next(line.split()[2:] for line in raw.splitlines() if line.startswith('.subckt'))
    atb=' ATB_ESD_RAIL' if cfg['atb_port_um'] else ''
    legs={'PAD_P'} if single_leg else {'PAD_P','PAD_N'}
    if set(ports)!=legs|{'VSS','ESD_RAIL'}|set(atb.split()):raise ValueError('Unexpected extracted ports: '+str(ports))
    reference=(network/'network_flat.spice').read_text()+'.subckt pad_reference '+' '.join(sorted(legs))+' VSS ESD_RAIL'+atb+'\nXP VSS ESD_RAIL PAD_P '+('VSS' if single_leg else 'PAD_N')+atb+' network_flat\n.ends pad_reference\n'
    strip=lambda text:'\n'.join(line for line in text.splitlines() if not line.startswith('C'))+'\n'
    (work/'pad-lvs.spice').write_text(strip(raw));(work/'reference.spice').write_text(strip(reference))
    if not lvs(work,'pad-lvs.spice','pad_flat','reference.spice','pad_reference','pad-lvs.txt'):raise ValueError('Pad device-graph LVS failed')
    # Correct precisely the same array well area as in the connected network.
    correction=manifest['array_well_capacitance_removed_ff'];lines=raw.splitlines();corrected=False
    for i,line in enumerate(lines):
        t=line.split()
        if t and t[0].startswith('C') and set(t[1:3])=={'VSS','ESD_RAIL'}:
            value=float(t[3][:-1])*{'f':1.,'p':1000.}[t[3][-1]]
            if value<=correction:raise ValueError('Well correction exceeds extracted capacitance')
            lines[i]=' '.join(t[:3])+f' {value-correction:.9g}f';corrected=True
    if not corrected:raise ValueError('Missing well capacitance')
    well=next(line for line in (network/'network-with-well.spice').read_text().splitlines() if line.startswith('DWELL_ARRAY'))
    well=well.replace(' RAIL ',' ESD_RAIL ')
    physical='\n'.join(lines).replace('.ends',well+'\n.ends')+'\n'
    # ESD_RAIL is internal, not an extra bond or functional-supply connection.
    wrapper='.subckt rf_protected_pad '+' '.join(sorted(legs))+' VSS'+atb+'\nXPHYSICAL '+' '.join(ports)+' pad_flat\n.ends rf_protected_pad\n'
    (work/'pad-extracted.spice').write_text(wrapper+physical)
    from protection_device_audit import check as independent_device_check
    independent=independent_device_check(work/'pad_flat.ext',work/'pad-extracted.spice',
        work/'independent-device-audit.json',work/'pad_flat.spice')
    if not independent['device_graph_matches']:
        raise ValueError('RF protection extraction differs from simulated device graph')
    subprocess.run([sys.executable,str(Path(__file__).with_name('render.py').resolve()),str(work/'pad_flat.mag'),'--output',str(work/'pad.png'),'--title','RF pair with connected protection','--primitive'],check=True,timeout=600)
    geometry=json.loads((work/'geometry.json').read_text())
    report=dict(status='RF_pad_candidate_DRC_and_device_LVS_pass_area_not_closed',drc_count=0,device_graph_lvs_match=True,configuration=cfg,network_routing=manifest['geometry'],geometry=geometry,fits_assigned_area=geometry['allocation_union_um2']<=cfg['area_ceiling_um2'],extracted_spice_sha256=hashlib.sha256((wrapper+physical).encode()).hexdigest(),limitations=['Area overrun is explicit; not adopted in the provider ring.','Native rail module is not included in this standalone view.','Signal and return resistance, current capacity and ESD stress remain unqualified; protection taps are behind the long bond corridors.'],source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('protection_device_audit.py'),Path(__file__).with_name('extract_audit.py'),network/'network.gds',network/'network-layout.json',network/'network-with-well.spice',generated/'rf-receive-layout.json',generated/'rf-transmit-layout.json']})
    (work/'pad-layout.json').write_text(json.dumps(report,indent=2)+'\n')


def screen_pad(work,pdk):
    from analog_screen import screen
    from protection_candidate import completion_flags
    physical=work/'pad-extracted.spice';manifest=json.loads((work/'pad-layout.json').read_text())
    if hashlib.sha256(physical.read_bytes()).hexdigest()!=manifest['extracted_spice_sha256']:raise ValueError('Changed physical pad extraction')
    for path,digest in manifest['source_sha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise ValueError('Stale pad source: '+path)
    model=work/'pad-screen.spice'
    model.write_text(physical.read_text()+f'\n.lib {pdk}/sm141064.ngspice diode_typical\n.lib {pdk}/sm141064.ngspice mimcap_typical\n')
    (work/'.spiceinit').write_text('set ngbehavior=hs\n')
    previous=Path.cwd();results={}
    try:
        os.chdir(work)
        for family in ('rf_receive','rf_transmit'):
            results[family]=screen(work/family,pdk,model,family)
    finally:os.chdir(previous)
    flags=completion_flags(results)
    simulator=Path(shutil.which('ngspice')).resolve()
    report=dict(status='full_RF_pad_extraction_lifecycle_screen_not_ESD_qualification',all_screens_complete=len(flags)==6 and all(flags.values()),transient_completion_checks=flags,results=results,area_fits=manifest['fits_assigned_area'],limitations=manifest['limitations'],source_sha256={str(path.resolve()):hashlib.sha256(path.read_bytes()).hexdigest() for path in (physical,work/'pad-layout.json',Path(__file__),Path(__file__).with_name('analog_screen.py'),Path(__file__).with_name('protection_candidate.py'),simulator)})
    (work/'pad-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['all_screens_complete']:raise ValueError('Incomplete pad lifecycle screen')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--inside',action='store_true');p.add_argument('--generated',type=Path,default=Path(__file__).with_name('generated'));p.add_argument('--pdk-model-dir',type=Path)
    p.add_argument('--wide-signals',action='store_true',help='Evaluate 12um transverse and outer signal trunks')
    p.add_argument('--escape-width-um',type=float,help='Explicit signal bond-corridor width, 4..24um')
    a=p.parse_args()
    if a.inside:assemble(a.output_dir.resolve())
    else:
        generate(a.output_dir.resolve(),a.generated.resolve(),wide_signals=a.wide_signals,escape_width_um=a.escape_width_um)
        if a.pdk_model_dir:screen_pad(a.output_dir.resolve(),a.pdk_model_dir.resolve())
