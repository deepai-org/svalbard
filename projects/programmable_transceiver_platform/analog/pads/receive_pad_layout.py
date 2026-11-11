"""Build a connected RX pad/discharge layout and verify its device graph.

Routes are guarded against changes in the current pad access coordinates.
Core allocation and provider placement are recorded separately from DRC/LVS.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


def assemble(w):
    import klayout.db as k
    l=k.Layout();l.read(str(w/'pad.gds'));pad=l.top_cell();root=l.create_cell('rx_pad_with_discharge');root.copy_tree(pad);l.read(str(w/'discharge.gds'));macro=l.cell('receiver_core_discharge');macro.flatten(False)
    # Child port labels are not top-level pad ports. Repeated primitive labels
    # must not create implicit net aliases when this companion macro is flattened.
    for ix in l.layer_indexes():
     for shape in list(macro.each_shape(ix)):
      if shape.is_text():shape.delete()
    root.insert(k.DCellInstArray(macro.cell_index(),k.DTrans(160.,450.)))
    reservations=[]
    metals={1:34,2:36,3:42,4:46,5:81};vias={1:35,2:38,3:40,4:41}
    def rect(layer,x1,y1,x2,y2):
     box=[min(x1,x2),min(y1,y2),max(x1,x2),max(y1,y2)]
     reservations.append(box);root.shapes(l.layer(layer,0)).insert(k.DBox(*box))
    def wire(layer,a,b,width=1.):
     assert a[0]==b[0] or a[1]==b[1];h=width/2;rect(metals[layer],min(a[0],b[0])-h,min(a[1],b[1])-h,max(a[0],b[0])+h,max(a[1],b[1])+h)
    def stack(x,y,lo,hi):
     for m in range(lo,hi+1):rect(metals[m],x-.22,y-.22,x+.22,y+.22)
     for v in range(lo,hi):rect(vias[v],x-.13,y-.13,x+.13,y+.13)
    for leg,x,y,outer in [('P',98.,440.5,151.),('N',97.,439.8,155.)]:
     stack(x,y,3,5);wire(3,(x,y),(outer,y),width=.3);stack(outer,y,3,5)
     if leg=='P':
      target=(163.45,455.765);wire(5,(outer,y),(outer,target[1]));stack(outer,target[1],4,5);wire(4,(outer,target[1]),target);stack(*target,1,4)
     else:
      target=(177.45,455.765);wire(5,(outer,y),(outer,453.));stack(outer,453.,4,5);wire(4,(outer,453.),(target[0],453.));stack(target[0],453.,4,5);wire(5,(target[0],453.),target);stack(*target,1,5)
    va=json.loads((w/'vss-access.json').read_text()) if (w/'vss-access.json').exists() else dict(x=131.22,y=1512.)
    vx,vy=va['x'],va['y']
    wire(2,(168.55,452.),(168.55,447.));wire(2,(168.55,447.),(190.,447.));stack(190.,447.,2,5);wire(5,(190.,447.),(190.,vy));stack(190.,vy,4,5);wire(4,(190.,vy),(vx,vy));stack(vx,vy,4,5)
    # Check actual metal connectivity before any label-based extraction.
    root.flatten(False);tr=k.LayoutToNetlist(k.RecursiveShapeIterator(l,root,[]));layers={n:tr.make_layer(l.layer(n,0),'L'+str(n)) for n in list(metals.values())+list(vias.values())}
    for layer in layers.values():tr.connect(layer)
    for v in range(1,5):tr.connect(layers[metals[v]],layers[vias[v]]);tr.connect(layers[vias[v]],layers[metals[v+1]])
    tr.extract_netlist()
    def net(level,x,y):
     n=tr.probe_net(layers[metals[level]],k.DPoint(x,y));return None if n is None else n.cluster_id
    pairs={'P':(net(5,98,437.75),net(1,163.45,455.765)),'N':(net(5,97,437.75),net(1,177.45,455.765)),'VSS':(net(5,vx,vy-.25),net(2,168.55,452))}
    (w/'metal-check.json').write_text(json.dumps(pairs,indent=2)+'\n');assert all(a is not None and a==b for a,b in pairs.values()),pairs;assert len({a for a,b in pairs.values()})==3,pairs
    opt=k.SaveLayoutOptions();opt.select_cell(root.cell_index());l.write(str(w/'combined.gds'),opt)
    
    metadata=json.loads((w/'base-layout.json').read_text())
    box=macro.dbbox();reservations.append([box.left+160.,box.bottom+450.,box.right+160.,box.top+450.])
    regions=metadata['allocation_regions_um']+reservations
    base_union=k.Region()
    for coordinates in metadata['allocation_regions_um']:base_union.insert(k.DBox(*coordinates).to_itype(l.dbu))
    base_union.merge()
    union=k.Region()
    for coordinates in regions:union.insert(k.DBox(*coordinates).to_itype(l.dbu))
    union.merge()
    (w/'geometry.json').write_text(json.dumps(dict(allocation_regions_um=regions,base_allocation_union_um2=base_union.area()*l.dbu*l.dbu,allocation_union_um2=union.area()*l.dbu*l.dbu),indent=2)+'\n')


def generate(work, pad_dir, core_dir):
    from layout import IMAGE, magic
    from extract_audit import converted_graph, extracted_graph, export_extracted
    work.mkdir(parents=True, exist_ok=False)
    metadata=json.loads((pad_dir/'wired-receive-usb-layout.json').read_text())
    expected_access={'RX_P':(98.,438.),'RX_N':(97.,438.),'VSS':(None,None)}
    for name,(x,y) in expected_access.items():
        if (x is not None and metadata['net_track_x_um'][name]!=x) or (y is not None and metadata['port_heights_um'][name]!=y):
            raise ValueError('Re-route receiver integration for changed access: '+name)
    # PD28: the VSS landing follows the array top (1512 for the canonical cell; taller for the 6 V USB variant).
    (work/'vss-access.json').write_text(json.dumps(dict(x=metadata['net_track_x_um']['VSS'],y=metadata['port_heights_um']['VSS']))+'\n')
    for source,target in [(pad_dir/'wired-receive-usb.gds','pad.gds'),
                          (pad_dir/'wired-receive-usb-layout.json','base-layout.json'),
                          (core_dir/'receiver-core.gds','discharge.gds')]:
        shutil.copyfile(source,work/target)
    shutil.copyfile(Path(__file__),work/'receive_pad_layout.py')
    subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3',
        '--mount',f'type=bind,src={work},dst=/work',IMAGE,'/work/receive_pad_layout.py',
        '--inside','--output-dir','/work'],check=True)
    script='crashbackups stop\ngds read combined.gds\nload rx_pad_with_discharge\nselect top cell\nexpand\ndrc check\ndrc catchup\nputs "COMBINED_DRC [drc list count total]"\nputs [drc listall why]\nextract all\next2spice lvs\next2spice cthresh 0\next2spice\nsave\nquit -noprompt\n'
    (work/'extract.tcl').write_text(script)
    result=magic(work,'extract.tcl')
    if not re.search(r'COMBINED_DRC 0\b',result.stdout):raise ValueError('Combined RX DRC failed')
    pad_model=pad_dir/'wired-receive-usb-extracted-c.spice'
    # Magic may express resistor dimensions in millimetres. Normalize only
    # dimension fields for the independent graph reader, which expects microns.
    scales={'':1e6,'m':1e3,'u':1.,'n':1e-3,'p':1e-6}
    def micron_dimension(match):
        value=float(match[2])*scales[match[3].lower()]
        return f'{match[1]}={value:.12g}u'
    core_reference=work/'core-reference.spice'
    core_reference.write_text(re.sub(
        r'\b(r_width|r_length)=([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([munp]?)(?=\s|$)',
        micron_dimension,(core_dir/'physical.spice').read_text(),flags=re.IGNORECASE))
    expected=converted_graph(pad_model)+converted_graph(core_reference)
    extracted=extracted_graph(work/'rx_pad_with_discharge.ext')
    if expected!=extracted:raise ValueError('Combined device graph differs from pad plus discharge macro')
    export_extracted(work/'rx_pad_with_discharge.ext',work/'physical.spice')
    if converted_graph(work/'physical.spice')!=extracted:raise ValueError('Independent exporter changed device graph')
    geometry=json.loads((work/'geometry.json').read_text())
    allocation=account_allocation(geometry)
    (work/'allocation-screen.json').write_text(json.dumps(allocation,indent=2)+'\n')
    metadata.update(flat_cell='rx_pad_with_discharge',device_count=sum(extracted.values()),
        allocation_regions_um=geometry['allocation_regions_um'],
        integrated_receiver_discharge=True,allocation_accounting=allocation)
    (work/'layout-report.json').write_text(json.dumps(metadata,indent=2)+'\n')
    sources=[Path(__file__),pad_model,pad_dir/'wired-receive-usb-layout.json',
             pad_dir/'wired-receive-usb.gds',core_dir/'receiver-core.gds',core_dir/'physical.spice',
             Path(__file__).with_name('extract_audit.py'),Path(__file__).with_name('layout.py')]
    report=dict(status='connected_RX_layout_device_graph_verified_not_canonical',drc_count=0,
        device_count=sum(extracted.values()),independent_device_graph_matches=True,
        independent_export_matches=True,allocation_union_um2=geometry['allocation_union_um2'],
        metal_connectivity=json.loads((work/'metal-check.json').read_text()),
        limitations=['Provider placement and area attribution require separate assembly check.',
                     'Capacitance included; distributed route resistance, core stress and ESD qualification absent.'],
        source_sha256={str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for f in sources},
        artifact_sha256={name:hashlib.sha256((work/name).read_bytes()).hexdigest()
                         for name in ('combined.gds','physical.spice','layout-report.json')})
    (work/'layout-screen.json').write_text(json.dumps(report,indent=2)+'\n')


def account_allocation(geometry):
    """Charge existing pad geometry once and incremental discharge/routes to rxlevel."""
    from design import PROJECT
    source=PROJECT/'spec/analog-architecture.json'
    blocks=json.loads(source.read_text())['blocks']
    base=geometry['base_allocation_union_um2']
    total=geometry['allocation_union_um2']
    increment=total-base
    budgets={name:blocks[name]['resource_allocation']['area_ceiling_um2']
             for name in ('wirepad','rxlevel')}
    if increment<0 or base>budgets['wirepad'] or increment>budgets['rxlevel']:
        raise ValueError('Integrated RX allocation exceeds existing block budgets')
    return dict(status='discharge_increment_fits_existing_rxlevel_allowance',
        wirepad=dict(charged_um2=base,budget_um2=budgets['wirepad']),
        rxlevel=dict(discharge_and_routes_um2=increment,budget_um2=budgets['rxlevel'],
                     remaining_before_other_core_work_um2=budgets['rxlevel']-increment),
        combined_reserved_um2=total,
        scope='Incremental geometric union only. Other receiver circuitry, routing clearance and whole-core fit remain unproven.',
        source_sha256={str(source):hashlib.sha256(source.read_bytes()).hexdigest()})


def verify_provider_placement(work, integration, assembly):
    """Check generated geometry in an existing provider assembly, without hand reservations."""
    from layout import IMAGE
    work.mkdir(parents=True, exist_ok=False)
    inputs=list(assembly.glob('candidate_*'))+[assembly/name for name in
        ('assembly-report.json','custom-map.json','retained-binding.json',
         'provider-reference-ring.gds','placement-transforms.json')]
    for source in inputs:
        if source.is_file():shutil.copyfile(source,work/source.name)
    for source,target in ((integration/'combined.gds','candidate_wired_receive_usb.gds'),
                          (integration/'layout-report.json','candidate_wired_receive_usb-layout.json'),
                          (Path(__file__).with_name('placement_audit.py'),'placement_audit.py')):
        shutil.copyfile(source,work/target)
    subprocess.run(['docker','run','--rm','--network','none','--entrypoint','python3',
        '--mount',f'type=bind,src={work},dst=/work',IMAGE,'/work/placement_audit.py'],check=True)
    report=json.loads((work/'placement-audit.json').read_text())
    if (not report['roundtrip_all_bond_openings_match'] or
        report['custom_to_custom_metal_overlaps'] or
        any(v['unexpected_retained_metal_overlaps'] for v in report['custom_cells'].values())):
        raise ValueError('Integrated RX provider placement failed')
    report['integration_input_sha256']={name:hashlib.sha256((integration/name).read_bytes()).hexdigest()
        for name in ('combined.gds','layout-report.json')}
    # Container output may be root-owned; replace it atomically in our directory.
    temporary=work/'placement-audit.with-inputs.json'
    temporary.write_text(json.dumps(report,indent=2)+'\n')
    temporary.replace(work/'placement-audit.json')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--inside',action='store_true')
    parser.add_argument('--pad-dir',type=Path)
    parser.add_argument('--core-dir',type=Path)
    parser.add_argument('--assembly-dir',type=Path,help='Also verify placement against this existing provider assembly')
    args=parser.parse_args()
    if args.inside:assemble(args.output_dir)
    else:
        if args.pad_dir is None or args.core_dir is None:parser.error('--pad-dir and --core-dir are required')
        generate(args.output_dir.resolve(),args.pad_dir.resolve(),args.core_dir.resolve())
        if args.assembly_dir:
            verify_provider_placement(args.output_dir.resolve()/'placement',args.output_dir.resolve(),args.assembly_dir.resolve())
