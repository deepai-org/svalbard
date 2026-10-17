"""Measure attached TX macro footprints against shared block allocations.

Run in the existing layout-tool container (klayout required). This is a lower
bound on placement demand, not placement/routing or whole-chip fit signoff.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import klayout.db as db


def run(project, output):
    spec_path=project/'spec/schematic-implementation.json'
    arch_path=project/'spec/analog-architecture.json'
    spec=json.loads(spec_path.read_text())['io_pad_first_pass']
    architecture=json.loads(arch_path.read_text())
    sources=[spec_path,arch_path,Path(__file__)]
    macros={}
    for name,allocation in spec['tx_attached_macro_allocations'].items():
        model=project/spec['tx_integration_fixture']['models'][name]
        layout_path=model.parent/'layout.json'
        layout_report=json.loads(layout_path.read_text())
        files=list(model.parent.glob('*.gds'))
        if len(files)!=1:
            raise ValueError('Expected one selected GDS for '+name)
        gds=files[0]
        digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        if layout_report.get('physical_sha256')!=digest(model) or layout_report.get('gds_sha256')!=digest(gds):
            raise ValueError('Selected macro model/layout hash mismatch: '+name)
        layout=db.Layout();layout.read(str(gds))
        cells=layout.top_cells()
        if len(cells)!=1:raise ValueError('Ambiguous macro top cell: '+name)
        bounds=cells[0].dbbox()
        block=allocation['block']
        budget=architecture['blocks'][block]['resource_allocation']['area_ceiling_um2']
        reservation=allocation['reservation_um2']
        count=allocation.get('instance_count',1)
        if type(count) is not int or count<1:raise ValueError('Invalid macro instance count')
        macros[name]=dict(block=block,model=str(model.relative_to(project)),
            gds=str(gds.relative_to(project)),
            bbox_um=[bounds.left,bounds.bottom,bounds.right,bounds.top],
            minimum_rectangular_footprint_um2=bounds.area()*count,instance_count=count,reservation_um2=reservation,
            fits_reservation=bounds.area()*count<=reservation,owner_block_budget_um2=budget)
        sources.extend([model,gds,layout_path])
    owners={}
    for block in sorted({m['block'] for m in macros.values()}):
        group=[m for m in macros.values() if m['block']==block]
        reserved=sum(m['reservation_um2'] for m in group)
        budget=group[0]['owner_block_budget_um2']
        owners[block]=dict(reserved_um2=reserved,budget_um2=budget,
            unreserved_um2=budget-reserved,reservations_fit=reserved<=budget)
    report=dict(status='attached_macro_area_accounting_not_placement_signoff',macros=macros,owners=owners,
        all_reservations_fit=all(m['fits_reservation'] for m in macros.values()) and all(o['reservations_fit'] for o in owners.values()),
        limitations=['Bounding rectangles exclude additional routing, guard separation, bias passives and missing control/monitor circuits.',
                     'Unreserved owner area must also fund its other circuitry; it is not free die reserve.',
                     'No placement or connectivity to the assembled pad ring is established.'],
        source_sha256={str(p.relative_to(project)) if p.is_relative_to(project) else str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(all_reservations_fit=report['all_reservations_fit'],macros=macros,owners=owners),indent=2))


def place(project, assembly, output):
    """Place verified macro instances; do not imply any electrical hookup."""
    area=json.loads(output.read_text())
    if not area['all_reservations_fit']:raise ValueError('Unfunded attached macro')
    spec_path=project/'spec/schematic-implementation.json'
    allocations=json.loads(spec_path.read_text())['io_pad_first_pass']['tx_attached_macro_allocations']
    placement_path=assembly/'placement-audit.json'
    pad_report=json.loads(placement_path.read_text())
    provider_path=assembly/'assembly-report.json'
    provider=json.loads(provider_path.read_text())
    die=db.DBox(*provider['die_area_um'])
    core=db.DBox(*provider['core_area_um'])
    original=assembly/'custom-assembly-candidate.oas'
    if hashlib.sha256(original.read_bytes()).hexdigest()!=pad_report['oas_sha256']:
        raise ValueError('Pad assembly differs from its audit')
    layout=db.Layout();layout.read(str(original));top=layout.top_cell()
    glass_index=layout.find_layer(37,0)
    original_openings=db.Region(top.begin_shapes_rec(glass_index)).merged()
    obstacles=[(name,db.DBox(*item['bbox_um'])) for name,item in pad_report['custom_cells'].items()]
    report={};unplaced=[];jobs=[];masters={}
    for family,macro in area['macros'].items():
        allocation=allocations[family]
        policies=allocation.get('placements')
        if policies is None and 'placement' in allocation:policies=[allocation['placement']]
        if policies is None:unplaced.append(family);continue
        if len(policies)!=macro['instance_count']:raise ValueError('Placement count differs from reserved instances: '+family)
        for index,policy in enumerate(policies):
            suffix=policy.get('name',str(index))
            name=family if macro['instance_count']==1 else family+'_'+suffix
            if any(job[0]==name for job in jobs):raise ValueError('Duplicate instance name: '+name)
            jobs.append((name,family,macro,policy))
    for name,family,macro,policy in jobs:
        if family not in masters:
            other=db.Layout();other.read(str(project/macro['gds']))
            cell=layout.create_cell('attached_tx_'+family);cell.copy_tree(other.top_cell())
            masters[family]=cell
        cell=masters[family]
        rotation=db.DCplxTrans(1,policy['rotation_degrees'],False,0,0)
        rotated=rotation*cell.dbbox()
        x,y=policy['lower_left_um']
        transform=db.DCplxTrans(1,policy['rotation_degrees'],False,x-rotated.left,y-rotated.bottom)
        box=transform*cell.dbbox()
        # Whole rectangular envelopes reserve room even where routing is sparse.
        if box.left<core.left or box.bottom<core.bottom or box.right>core.right or box.top>core.top:raise ValueError('Macro outside provider core')
        clearance=policy['minimum_clearance_um']
        padded=db.DBox(box.left-clearance,box.bottom-clearance,box.right+clearance,box.top+clearance)
        conflicts=[label for label,b in obstacles if padded.overlaps(b)]
        if conflicts:raise ValueError(name+' placement conflicts with '+str(conflicts))
        # Check actual same-layer metal against the complete retained native ring
        # and already inserted cells, rather than only the five custom envelopes.
        for layer in (34,36,42,46,81):
            index=layout.find_layer(layer,0)
            if index is None:continue
            existing=db.Region(top.begin_shapes_rec(index))
            local=db.Region(cell.begin_shapes_rec(index))
            moved=local.transformed(db.ICplxTrans(transform.mag,transform.angle,transform.is_mirror(),
                round(transform.disp.x/layout.dbu),round(transform.disp.y/layout.dbu)))
            if not (existing & moved).is_empty():raise ValueError(name+' metal collision on '+str(layer))
        top.insert(db.DCellInstArray(cell.cell_index(),transform))
        obstacles.append((name,box))
        report[name]=dict(macro_family=family,instance_name=policy.get('name',family),bbox_um=[box.left,box.bottom,box.right,box.top],
            rotation_degrees=policy['rotation_degrees'],minimum_clearance_um=clearance,
            electrical_connection_status='unrouted_no_supply_or_signal_hookup')
    oas=output.with_name('attached-core-assembly.oas')
    options=db.SaveLayoutOptions();options.select_cell(top.cell_index());options.set_format_from_filename(str(oas))
    layout.write(str(oas),options)
    check=db.Layout();check.read(str(oas))
    if check.top_cell().child_instances()!=top.child_instances():raise ValueError('Assembly roundtrip changed instances')
    exported_openings=db.Region(check.top_cell().begin_shapes_rec(check.find_layer(37,0))).merged()
    if not (original_openings ^ exported_openings).is_empty():raise ValueError('Bond openings changed')
    area['placement']=dict(status='geometry_only_unrouted',macros=report,unplaced_macros=unplaced,
        exported_bond_opening_polygons_match_original=True,
        same_layer_metal_collision_check_pass=True,
        oas_sha256=hashlib.sha256(oas.read_bytes()).hexdigest(),
        limitations=['Not full-chip floorplan: other core blocks still need placement.',
                     'No signal/supply routing, integrated DRC/LVS or routed electrical rerun.'])
    area['source_sha256'].update({os.path.relpath(p,project):hashlib.sha256(p.read_bytes()).hexdigest() for p in (original,placement_path,provider_path)})
    output.write_text(json.dumps(area,indent=2)+'\n')
    # Explicit envelope preview; rectangles are not presented as routed metal.
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="786" height="1024" viewBox="-180 -180 {die.width()+360} {die.height()+360}">',
         '<rect x="-180" y="-180" width="100%" height="100%" fill="white"/>',
         f'<rect x="0" y="0" width="{die.width()}" height="{die.height()}" fill="#fafafa" stroke="#334155" stroke-width="8"/>',
         '<text x="100" y="-60" font-size="65">Pad + TX macro placement — UNROUTED</text>']
    for label,b in obstacles:
        color='#bae6fd' if label in report else '#e2e8f0'
        svg.append(f'<rect x="{b.left}" y="{die.top-b.top}" width="{b.width()}" height="{b.height()}" fill="{color}" stroke="#334155" stroke-width="5"/>')
        cx=(b.left+b.right)/2;cy=die.top-(b.top+b.bottom)/2
        angle=-90 if b.height()>b.width() else 0
        display=label.removeprefix('steering_driver_')
        svg.append(f'<text x="{cx}" y="{cy}" text-anchor="middle" dominant-baseline="middle" transform="rotate({angle} {cx} {cy})" font-size="{min(65, max(b.width(),b.height())/(max(1,len(display))*.62))}">{display}</text>')
    svg.append('</svg>')
    output.with_name('attached-core-placement.svg').write_text('\n'.join(svg))


def route_steering(project, output, assembly):
    """Connect six steering outputs; leave other macro hookups explicitly open."""
    area=json.loads(output.read_text())
    spec_path=project/'spec/schematic-implementation.json'
    cfg=json.loads(spec_path.read_text())['io_pad_first_pass']['steering_output_routing']
    source=output.with_name('attached-core-assembly.oas')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=area['placement']['oas_sha256']:
        raise ValueError('Placed assembly changed')
    layout=db.Layout();layout.read(str(source));top=layout.top_cell();unit=layout.dbu
    pad_audit=assembly/'placement-audit.json'
    provider_path=assembly/'assembly-report.json'
    die_top=json.loads(provider_path.read_text())['die_area_um'][3]
    pad_box=json.loads(pad_audit.read_text())['custom_cells']['wired_transmit']['bbox_um']
    def port(name,box):
        found=[];it=top.begin_shapes_rec(layout.find_layer(81,10))
        while not it.at_end():
            shape=it.shape()
            if shape.is_text() and shape.text.string==name:
                displacement=shape.text.trans.disp
                point=it.trans()*db.Point(displacement.x,displacement.y)
                if box[0]<=point.x*unit<=box[2] and box[1]<=point.y*unit<=box[3]:found.append(point)
            it.next()
        if len(found)!=1:raise ValueError('Ambiguous placed port '+name)
        return found[0]
    layers={4:layout.find_layer(46,0),5:layout.find_layer(81,0)}
    original={m:db.Region(top.begin_shapes_rec(i)).merged() for m,i in layers.items()}
    def metal_at(point):
        found=[poly for poly in original[5].each() if poly.inside(point)]
        if len(found)!=1:raise ValueError('Port lacks unique M5 metal')
        region=db.Region();region.insert(found[0]);return region
    def rectangle(a,b,width):
        h=round(width/(2*unit));r=db.Region()
        r.insert(db.Box(min(a.x,b.x)-h,min(a.y,b.y)-h,max(a.x,b.x)+h,max(a.y,b.y)+h));return r
    def point(x,y):return db.Point(round(x/unit),round(y/unit))
    planned=[];report={}
    for index,name in enumerate(('MAIN_P','MAIN_N','POST_P','POST_N','TMDS_P','TMDS_N')):
        box=area['placement']['macros']['steering_driver_'+name]['bbox_um']
        start=port('OUT',box);end=port(name,pad_box)
        escape_y=box[3]+cfg['escape_above_macro_um'][index%2]
        channel=cfg['first_channel_x_um']+index*cfg['channel_pitch_um']
        points=[start,point(start.x*unit,escape_y),point(channel,escape_y),point(channel,end.y*unit),end]
        if index%2 and cfg['match_pair_lengths']:
            direct=sum((abs(a.x-b.x)+abs(a.y-b.y))*unit for a,b in zip(points,points[1:]))
            extra=(report[name[:-1]+'P']['manhattan_length_um']-direct)/2
            if extra<0:raise ValueError('Pair matching requires an unsupported route reversal')
            left=start.x*unit-extra;upper=escape_y+cfg['meander_step_um']
            if upper>=end.y*unit:raise ValueError('No vertical room for pair matching')
            points=[start,point(start.x*unit,escape_y),point(left,escape_y),
                    point(left,upper),point(channel,upper),point(channel,end.y*unit),end]
        regions={4:db.Region(),5:db.Region()};vias=db.Region();length=0.
        for i,(a,b) in enumerate(zip(points,points[1:])):
            metal=5 if i%2==0 else 4
            width=cfg['landing_width_um'] if i==len(points)-2 else cfg['channel_width_um']
            regions[metal]+=rectangle(a,b,width)
            length+=(abs(a.x-b.x)+abs(a.y-b.y))*unit
        for q in points[1:-1]:
            vias+=rectangle(q,q,.28)
            regions[4]+=rectangle(q,q,.4);regions[5]+=rectangle(q,q,.44)
        vias+=rectangle(end,end,.28)
        regions[4]+=rectangle(end,end,.4);regions[5]+=rectangle(end,end,.44)
        allowed=metal_at(start)+metal_at(end)
        for metal in (4,5):
            overlap=regions[metal]&original[metal]
            if metal==5:overlap-=allowed
            if not overlap.is_empty():raise ValueError(name+' intersects unrelated existing M'+str(metal)+' '+str(overlap.bbox()))
            for other,other_regions,_ in planned:
                if not (regions[metal]&other_regions[metal]).is_empty():raise ValueError(name+' shorts '+other)
        planned.append((name,regions,vias))
        report[name]=dict(source_macro='steering_driver_'+name,source_port='OUT',destination_port=name,
            route_points_um=[[q.x*unit,q.y*unit] for q in points],manhattan_length_um=length,
            via4_count=len(points)-1,
            pair_length_skew_um=length-report[name[:-1]+'P']['manhattan_length_um'] if index%2 else None,
            electrical_status='geometry_connected_requires_extraction_and_timing')
    for name,regions,vias in planned:
        for m,r in regions.items():top.shapes(layers[m]).insert(r)
        top.shapes(layout.layer(41,0)).insert(vias)
    target=output.with_name('attached-core-steering-routed.oas');layout.write(str(target))
    check=db.Layout();check.read(str(target));exported=check.top_cell()
    for metal in (4,5):
        expected=original[metal].dup()
        for _,regions,_ in planned:expected+=regions[metal]
        actual=db.Region(exported.begin_shapes_rec(check.find_layer(46 if metal==4 else 81,0)))
        if not (expected^actual).is_empty():raise ValueError('Export changed routed metal')
    openings=db.Region(top.begin_shapes_rec(layout.find_layer(37,0)))
    exported_openings=db.Region(exported.begin_shapes_rec(check.find_layer(37,0)))
    if not (openings^exported_openings).is_empty():raise ValueError('Export changed bond openings')
    result=dict(status='six_steering_output_routes_only',routes=report,
        unchanged_other_macro_connections='Unrouted buffer, interlock, supplies, bias and upstream data/control remain incomplete.',
        same_layer_unintended_intersections=False,
        exported_route_metal_matches=True,exported_bond_openings_preserved=True,
        limitations=['Intersection checks are not spacing DRC or extracted LVS.',
                    'Equal drawn pair lengths do not establish matched RC or timing; vias and bends differ.',
                    'Routing resistance/capacitance and supply-return timing are not yet included in the connected simulation.',
                    'Nominal geometry only; no current-density or reliability qualification.'],
        source_sha256={os.path.relpath(p,project):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,spec_path,pad_audit,provider_path,Path(__file__))},
        routed_oas_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    output.with_name('attached-core-steering-routing.json').write_text(json.dumps(result,indent=2)+'\n')
    svg=output.with_name('attached-core-placement.svg').read_text().replace('Pad + TX macro placement — UNROUTED','TX steering output routes — other hookups incomplete')
    drawing=[]
    for index,(name,r) in enumerate(report.items()):
        points=' '.join(f'{x},{die_top-y}' for x,y in r['route_points_um'])
        drawing.append(f'<polyline points="{points}" fill="none" stroke="{["#dc2626","#2563eb","#16a34a","#9333ea","#ea580c","#0891b2"][index]}" stroke-width="4"/>')
    output.with_name('attached-core-steering-routing.svg').write_text(svg.replace('</svg>','\n'.join(drawing)+'</svg>'))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--assembly',type=Path)
    parser.add_argument('--route-steering',action='store_true')
    args=parser.parse_args();run(args.project.resolve(),args.output.resolve())
    if args.assembly:place(args.project.resolve(),args.assembly.resolve(),args.output.resolve())

    if args.route_steering:
        if not args.assembly:raise ValueError('Routing requires a freshly verified assembly')
        route_steering(args.project.resolve(),args.output.resolve(),args.assembly.resolve())
