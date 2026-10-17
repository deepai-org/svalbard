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
    report={};unplaced=[]
    for name,macro in area['macros'].items():
        if macro['instance_count']!=1 or 'placement' not in allocations[name]:
            unplaced.append(name);continue
        policy=allocations[name]['placement']
        other=db.Layout();other.read(str(project/macro['gds']))
        cell=layout.create_cell('attached_tx_'+name);cell.copy_tree(other.top_cell())
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
        report[name]=dict(bbox_um=[box.left,box.bottom,box.right,box.top],
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
        svg.append(f'<text x="{cx}" y="{cy}" text-anchor="middle" dominant-baseline="middle" transform="rotate({angle} {cx} {cy})" font-size="65">{label}</text>')
    svg.append('</svg>')
    output.with_name('attached-core-placement.svg').write_text('\n'.join(svg))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--assembly',type=Path)
    args=parser.parse_args();run(args.project.resolve(),args.output.resolve())
    if args.assembly:place(args.project.resolve(),args.assembly.resolve(),args.output.resolve())
