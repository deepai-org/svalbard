"""Extract local pad-to-native-rail metal connectivity with KLayout.

Includes actual custom GDS and both restored native rail modules. This is a
metal/via connectivity check, not transistor LVS, resistance or ESD signoff.
Run in the pinned GF180 container. Fault injection changes only the in-memory
fixture and must never be published as candidate geometry.
"""
import argparse
import hashlib
import os
import json
from pathlib import Path
import re
import klayout.db as db


def audit(generated, native_path, map_path, fault='none'):
    mapping=map_path.read_text()
    metals=[34,36,42,46,81];vias=[35,38,40,41]
    for prefix,numbers in [('Metal',metals),('Via',vias)]:
        for i,number in enumerate(numbers,1):
            if not re.search(rf'^{prefix}{i}\s+\S+\s+{number}\s+0\s*$',mapping,re.M):
                raise ValueError('Installed layer map changed')
    results={};sources=[Path(__file__),native_path,map_path]
    for family in ('wired-transmit','wired-receive-usb','reference-clock','rf-receive','rf-transmit'):
        path=generated/(family+'.gds');meta=generated/(family+'-layout.json')
        sources.extend([path,meta]);report=json.loads(meta.read_text())
        layout=db.Layout();layout.read(str(native_path));rail=layout.cell('5LM_METAL_RAIL')
        candidate=db.Layout();candidate.read(str(path));source=candidate.top_cell()
        if candidate.dbu!=layout.dbu:raise ValueError('Layout units differ')
        unit=layout.dbu
        port_points={}
        for level,number in enumerate(metals):
            index=candidate.find_layer(number,10)
            if index is None:continue
            for shape in source.each_shape(index):
                if not shape.is_text():continue
                name=shape.text.string
                if name in port_points:raise ValueError('Ambiguous custom port label: '+name)
                port_points[name]=(level,db.Point(shape.text.x,shape.text.y))
        if not {'VSS','PAD_P','PAD_N'}<=port_points.keys():raise ValueError('Missing custom port labels')
        pair=layout.create_cell('pad_with_native_rails')
        custom=layout.create_cell('custom_candidate');custom.copy_tree(source)
        pair.insert(db.CellInstArray(custom.cell_index(),db.Trans()))
        supply_points=[]
        for offset in (0,round(report['bond_pitch_um']/unit)):
            pair.insert(db.CellInstArray(rail.cell_index(),db.Trans(offset,0)))
            for s in rail.each_shape(layout.find_layer(81,10)):
                if s.is_text() and s.text.string in ('VDD','DVDD'):
                    supply_points.append((s.text.string,db.Point(s.text.x+offset,s.text.y)))
        pair.flatten(True)
        def box(values):return db.Box(*(round(v/unit) for v in values))
        if fault=='open_ground':
            index=layout.find_layer(38,0);shapes=db.Region(pair.begin_shapes_rec(index))
            for rectangle in report['near_bond_ground_landings_um']:shapes-=db.Region(box(rectangle))
            pair.shapes(index).clear();pair.shapes(index).insert(shapes)
        elif fault=='short_protection' and 'ESD_RAIL' in port_points:
            level,a=port_points['ESD_RAIL'];other,b=port_points['VSS']
            if level!=other:raise ValueError('Fault bridge requires same-layer rail labels')
            bridge=db.Box(min(a.x,b.x),min(a.y,b.y),max(a.x,b.x),max(a.y,b.y)).enlarged(round(.5/unit))
            pair.shapes(layout.find_layer(metals[level],0)).insert(bridge)
        elif fault=='short_supply':
            pair.shapes(layout.find_layer(81,0)).insert(box([9,77.305,11,122]))
        # VIA4 inside CAPM contacts the MIM top plate, not Metal4 below
        # its dielectric. Treating it as an ordinary via shorts every MIM.
        cap_index=layout.layer(75,0)
        cap=db.Region(pair.begin_shapes_rec(cap_index))
        via4=db.Region(pair.begin_shapes_rec(layout.find_layer(41,0)))
        normal_index=layout.layer(900,0);capvia_index=layout.layer(901,0)
        pair.shapes(normal_index).insert(via4-cap)
        pair.shapes(capvia_index).insert(via4&cap)
        netlist=db.LayoutToNetlist(pair.begin_shapes_rec(layout.find_layer(34,0)))
        m=[netlist.make_layer(layout.find_layer(n,0),'M'+str(i+1)) for i,n in enumerate(metals)]
        v=[netlist.make_layer(normal_index if i==3 else layout.find_layer(n,0),'V'+str(i+1)) for i,n in enumerate(vias)]
        cap_plate=netlist.make_layer(cap_index,'CAPM')
        cap_contact=netlist.make_layer(capvia_index,'CAPM_CONTACT')
        netlist.connect(cap_plate);netlist.connect(cap_plate,cap_contact);netlist.connect(cap_contact,m[4])
        for layer in m:netlist.connect(layer)
        for i,layer in enumerate(v):netlist.connect(m[i],layer);netlist.connect(layer,m[i+1])
        netlist.extract_netlist()
        def cluster(layer,point):
            net=netlist.probe_net(layer,point)
            return None if net is None else net.cluster_id
        def port_cluster(name):
            level,point=port_points[name]
            return cluster(m[level],point)
        ground=port_cluster('VSS')
        if ground is None:raise ValueError('VSS label is not on extracted metal')
        landings=[]
        for rectangle in report['near_bond_ground_landings_um']:
            center=box(rectangle).center()
            ids=[cluster(m[i],center) for i in (1,2,3,4)]
            landings.append(dict(center_um=[center.x*unit,center.y*unit],
                metal2_through_metal5_cluster_ids=ids,connected_to_custom_vss=all(n==ground for n in ids)))
        conflicts=[dict(label=name,point_um=[point.x*unit,point.y*unit])
                   for name,point in supply_points if cluster(m[4],point)==ground]
        pads={name:port_cluster(name) for name in ('PAD_P','PAD_N')}
        separate=all(n is not None and n!=ground for n in pads.values()) and len(set(pads.values()))==2
        protection=None
        if 'ESD_RAIL' in port_points:
            rail_id=port_cluster('ESD_RAIL')
            forbidden={ground,*pads.values(),*[cluster(m[4],point) for _,point in supply_points]}
            protection=dict(cluster_id=rail_id,isolated_from_ground_signals_and_supplies=rail_id is not None and rail_id not in forbidden)
        passed=(protection is None or protection['isolated_from_ground_signals_and_supplies']) and bool(landings) and all(x['connected_to_custom_vss'] for x in landings) and not conflicts and separate
        results[family]=dict(pass_metal_connectivity=passed,custom_vss_cluster_id=ground,
            protection_rail=protection,ground_landings=landings,supply_rail_conflicts=conflicts,pad_cluster_ids=pads,
            pads_separate_from_ground_and_each_other=separate)
    return dict(status='local_metal_connectivity_pass' if all(v['pass_metal_connectivity'] for v in results.values()) else 'local_metal_connectivity_fail',
        fault_injection=fault,families=results,
        limitations=['Local custom pair plus two native rail modules only; whole-ring/global supply hookup is outside this check.',
            'Only metal and via connectivity is extracted; no diffusion/device conduction, distributed resistance, current capacity or ESD qualification.',
            'No implicit connection by matching net names; every tested connection follows touching metal/via geometry.'],
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})


def audit_steering(generated, map_path, fault='none'):
    """Extract routed metal without using text labels to join disconnected shapes."""
    if fault not in ('none','open_route','short_routes'):raise ValueError('Unsupported steering fault')
    project=generated.parents[2]
    route_path=generated/'attached-core-steering-routing.json'
    area_path=generated/'attached-core-area.json'
    route=json.loads(route_path.read_text());area=json.loads(area_path.read_text())
    oas=generated/'attached-core-steering-routed.oas'
    if hashlib.sha256(oas.read_bytes()).hexdigest()!=route['routed_oas_sha256']:
        raise ValueError('Routed assembly differs from its report')
    metals=[34,36,42,46,81];vias=[35,38,40,41]
    mapping=map_path.read_text()
    for prefix,numbers in [('Metal',metals),('Via',vias)]:
        for i,number in enumerate(numbers,1):
            if not re.search(rf'^{prefix}{i}\s+\S+\s+{number}\s+0\s*$',mapping,re.M):
                raise ValueError('Installed layer map changed')
    layout=db.Layout();layout.read(str(oas));top=layout.top_cell();unit=layout.dbu
    pad_audit_path=next(project/name for name in route['source_sha256'] if name.endswith('/placement-audit.json'))
    pad_box=json.loads(pad_audit_path.read_text())['custom_cells']['wired_transmit']['bbox_um']
    boxes={name:v['bbox_um'] for name,v in area['placement']['macros'].items()}
    boxes['pad']=pad_box
    ports=[];it=top.begin_shapes_rec(layout.find_layer(81,10))
    while not it.at_end():
        shape=it.shape()
        if shape.is_text():
            displacement=shape.text.trans.disp
            point=it.trans()*db.Point(displacement.x,displacement.y)
            for name,box in boxes.items():
                if box[0]<=point.x*unit<=box[2] and box[1]<=point.y*unit<=box[3]:
                    ports.append((name,shape.text.string,point))
        it.next()
    # A separate flat drawing-only layout prevents accidental text-name joining.
    drawing=db.Layout();drawing.dbu=unit;cell=drawing.create_cell('routed_metal')
    # Keep every macro in full, its output routes and the adjacent native pad
    # geometry. This is explicitly a local interconnect audit, not ring LVS.
    bounds=list(boxes.values())
    crop=db.Region(db.Box(round((min(b[0] for b in bounds)-10)/unit),
        round((min(b[1] for b in bounds)-10)/unit),
        round((max(b[2] for b in bounds)+10)/unit),
        round((max(b[3] for b in bounds)+10)/unit)))
    for number in metals+vias+[75]:
        index=layout.find_layer(number,0)
        if index is not None:cell.shapes(drawing.layer(number,0)).insert(db.Region(top.begin_shapes_rec(index))&crop)
    def point(xy):return db.Point(*(round(v/unit) for v in xy))
    if fault=='open_route':
        p=point(route['routes']['MAIN_P']['route_points_um'][-1]);index=drawing.layer(41,0)
        shapes=db.Region(cell.begin_shapes_rec(index))-db.Region(db.Box(p,p).enlarged(round(.16/unit)))
        cell.shapes(index).clear();cell.shapes(index).insert(shapes)
    elif fault=='short_routes':
        a=point(route['routes']['MAIN_P']['route_points_um'][-2]);b=point(route['routes']['MAIN_N']['route_points_um'][-2])
        cell.shapes(drawing.layer(81,0)).insert(db.Box(a,b).enlarged(round(.3/unit)))
    cap=db.Region(cell.begin_shapes_rec(drawing.layer(75,0)))
    via4=db.Region(cell.begin_shapes_rec(drawing.layer(41,0)))
    ordinary=drawing.layer(900,0);capvia=drawing.layer(901,0)
    cell.shapes(ordinary).insert(via4-cap);cell.shapes(capvia).insert(via4&cap)
    extraction=db.LayoutToNetlist(cell.begin_shapes_rec(drawing.layer(34,0)))
    m=[extraction.make_layer(drawing.layer(n,0),'M'+str(i+1)) for i,n in enumerate(metals)]
    v=[extraction.make_layer(ordinary if i==3 else drawing.layer(n,0),'V'+str(i+1)) for i,n in enumerate(vias)]
    plate=extraction.make_layer(drawing.layer(75,0),'CAPM')
    contact=extraction.make_layer(capvia,'CAPM_CONTACT')
    extraction.connect(plate);extraction.connect(plate,contact);extraction.connect(contact,m[4])
    for layer in m:extraction.connect(layer)
    for i,layer in enumerate(v):extraction.connect(m[i],layer);extraction.connect(layer,m[i+1])
    extraction.extract_netlist()
    def cluster(p):
        net=extraction.probe_net(m[4],p)
        return None if net is None else net.cluster_id
    forbidden=[]
    for instance,name,p in ports:
        intended=(instance=='pad' and name in route['routes']) or (instance.startswith('steering_driver_') and name=='OUT')
        if not intended:forbidden.append((instance,name,cluster(p)))
    results={}
    for name,r in route['routes'].items():
        start=cluster(point(r['route_points_um'][0]));end=cluster(point(r['route_points_um'][-1]))
        conflicts=[instance+'.'+port for instance,port,net in forbidden if net is not None and net in (start,end)]
        results[name]=dict(source_cluster=start,destination_cluster=end,
            connected=start is not None and start==end,forbidden_port_connections=conflicts)
    ids=[v['source_cluster'] for v in results.values()]
    separate=None not in ids and len(set(ids))==len(ids)
    passed=separate and all(v['connected'] and not v['forbidden_port_connections'] for v in results.values())
    return dict(status='steering_metal_connectivity_pass' if passed else 'steering_metal_connectivity_fail',
        fault_injection=fault,routes=results,output_nets_separate=separate,
        non_output_ports_checked=len(forbidden),
        scope='Drawing-only metal/via extraction of the complete TX macro cluster and adjacent native pad geometry. Text identifies probe locations only; equal names never join nets. MIM top-plate contacts are separated from ordinary via4.',
        limitations=['Not transistor LVS, spacing DRC, parasitic timing or current-capacity qualification.',
                    'Other macro connections remain unrouted; passing these six outputs is not assembly completion.',
                    'Connectivity outside the TX cluster crop is not extracted. Whole-ring connectivity remains unverified.'],
        pdk_layer_map_sha256=hashlib.sha256(map_path.read_bytes()).hexdigest(),
        source_sha256={os.path.relpath(p,project):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                       (Path(__file__),oas,route_path,area_path,pad_audit_path)})


def steering_campaign(generated, map_path):
    report=audit_steering(generated,map_path)
    faults={name:audit_steering(generated,map_path,name) for name in ('open_route','short_routes')}
    report['fault_detection']=faults
    report['faults_detected']=all(r['status']=='steering_metal_connectivity_fail' for r in faults.values())
    if not report['faults_detected']:report['status']='steering_fault_detection_failed'
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--generated',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pdk',type=Path,default=Path('/pdk/gf180mcuD'))
    p.add_argument('--steering',action='store_true')
    p.add_argument('--fault',choices=('none','open_ground','short_supply','short_protection'),default='none')
    a=p.parse_args()
    if a.steering:
        if a.fault!='none':raise ValueError('Steering campaign owns its fault cases')
        r=steering_campaign(a.generated,a.pdk/'libs.tech/klayout/tech/gf180mcu.map')
    else:r=audit(a.generated,a.pdk/'libs.ref/gf180mcu_fd_io/gds/gf180mcu_fd_io.gds',a.pdk/'libs.tech/klayout/tech/gf180mcu.map',a.fault)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(r['status'] if a.steering else {k:v['pass_metal_connectivity'] for k,v in r['families'].items()}))
    raise SystemExit(0 if r['status'] in ('local_metal_connectivity_pass','steering_metal_connectivity_pass') else 1)
