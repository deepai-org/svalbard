"""Place custom physical cells and expose retained-ring metal collisions.

Run in the pinned KLayout container. This is a failing assembly candidate until
rail integration and connectivity checks resolve every reported overlap.
"""
import hashlib
from collections import Counter
from itertools import combinations
import json
from pathlib import Path
import klayout.db as db

work=Path('/work')
report=json.loads((work/'assembly-report.json').read_text())
mapping=json.loads((work/'custom-map.json').read_text())
layout=db.Layout();layout.read(str(work/'provider-reference-ring.gds'))
retained=layout.create_cell('retained_provider_ring')
top=layout.create_cell('custom_assembly_candidate')
replaced={site for sites in mapping.values() for site in sites}
retained_binding=json.loads((work/'retained-binding.json').read_text())
output_sites={site:signal for signal,site in retained_binding['output_sites'].items()}
native=db.Layout();native.read('/pdk/gf180mcuD/libs.ref/gf180mcu_fd_io/gds/gf180mcu_fd_io.gds')
if native.dbu!=layout.dbu:raise ValueError('Native host library units differ')
output_cell=layout.create_cell('selected_host_output')
output_cell.copy_tree(native.cell(retained_binding['output_master']))
host_replacements=[]
restored_rails=[]
rail=layout.cell('5LM_METAL_RAIL')
if rail is None:raise ValueError('Native rail module missing')
landing_box=db.Box(*[round(v/layout.dbu) for v in (9,77.305,11,79.305)])
rail_top=db.Region(rail.begin_shapes_rec(layout.find_layer(81,0))).merged()
landing_components=[polygon for polygon in rail_top.each()
                    if not (db.Region(polygon)&db.Region(landing_box)).is_empty()]
if len(landing_components)!=1:raise ValueError('Ground landing does not identify one native top-metal component')
landing_component=db.Region(landing_components[0])
if not (db.Region(landing_box)-landing_component).is_empty():raise ValueError('Ground landing exceeds native top metal')
landing_labels=[]
for shape in rail.each_shape(layout.find_layer(81,10)):
    if shape.is_text() and landing_components[0].inside(db.Point(shape.text.x,shape.text.y)):
        landing_labels.append(shape.text.string)
if set(landing_labels)!={'DVSS'}:raise ValueError('Near-bond landing is not exclusively labeled DVSS')

def rail_transforms(cell,transform):
    if cell.cell_index()==rail.cell_index():return [transform]
    found=[]
    for inst in cell.each_inst():found+=rail_transforms(inst.cell,transform*inst.trans)
    return found
for item in json.loads((work/'placement-transforms.json').read_text()):
    cell=layout.cell(item['master'])
    transform=db.Trans(item['rotation'],item['mirror'],item['x'],item['y'])
    if item['name'] in replaced:
        native=rail_transforms(cell,db.Trans())
        if len(native)!=1 or native[0]!=db.Trans():
            raise ValueError('Stock cell rail transform needs explicit handling: '+item['name'])
        retained.insert(db.CellInstArray(rail.cell_index(),transform))
        restored_rails.append(item['name'])
    elif item['name'] in output_sites:
        retained.insert(db.CellInstArray(output_cell.cell_index(),transform))
        host_replacements.append(dict(site=item['name'],signal=output_sites[item['name']],
            original_master=item['master'],candidate_master=retained_binding['output_master'],settings=retained_binding['settings']))
    else:
        retained.insert(db.CellInstArray(cell.cell_index(),transform))
top.insert(db.CellInstArray(retained.cell_index(),db.Trans()))
orientations={'R0':(0,False),'R90':(1,False),'R180':(2,False),'R270':(3,False),
              'MX':(0,True),'MY':(2,True),'MXR90':(1,True),'MYR90':(3,True)}
placed={};entries={};ground_landings={}
def umbox(b):return [v*layout.dbu for v in (b.left,b.bottom,b.right,b.top)]
for family,sites in mapping.items():
    candidate=db.Layout();path=work/f'candidate_{family}.gds';candidate.read(str(path))
    if candidate.dbu!=layout.dbu:raise ValueError('Database unit conversion required')
    source=candidate.top_cell()
    layout_report=json.loads((work/f'candidate_{family}-layout.json').read_text())
    reservations=db.Region()
    for rectangle in layout_report['allocation_regions_um']:
        reservations.insert(db.Box(*[round(v/layout.dbu) for v in rectangle]))
    reservations.merge()
    outside=db.Region()
    for layer_index in candidate.layer_indexes():
        physical=db.Region(source.begin_shapes_rec(layer_index))
        outside+=physical-reservations
    if not outside.is_empty():raise ValueError('Candidate geometry exceeds declared nonrectangular allocation: '+family)
    reserved_area=reservations.area()*layout.dbu**2
    openings=[];it=source.begin_shapes_rec(candidate.find_layer(37,0))
    while not it.at_end():
        openings.append(it.shape().bbox().transformed(it.trans()));it.next()
    # Generator explicitly places P left and N right; graph/LVS checks remain
    # the electrical authority. This geometric test does not infer net names.
    openings.sort(key=lambda b:b.left)
    if len(openings)!=2:raise ValueError('Expected two custom openings')
    positive=report['sites'][sites[0]]
    negative=report['sites'][sites[1]]
    if positive['orientation']!=negative['orientation']:raise ValueError('Pair spans different orientations')
    rot,mirror=orientations[positive['orientation']]
    orientation=db.Trans(rot,mirror,0,0)
    origin=orientation*openings[0].center()
    target=positive['bond_center_um']
    transform=db.Trans(rot,mirror,round(target[0]/layout.dbu)-origin.x,round(target[1]/layout.dbu)-origin.y)
    for opening,site in zip(openings,sites):
        actual=opening.transformed(transform)
        expected=db.Box(*[round(v/layout.dbu) for v in report['sites'][site]['bond_opening_bbox_um']])
        if actual!=expected:raise ValueError('Absolute bond opening mismatch: '+site)
    cell=layout.create_cell('custom_'+family);cell.copy_tree(source)
    top.insert(db.CellInstArray(cell.cell_index(),transform))
    bbox=cell.bbox().transformed(transform)
    die=db.Box(*[round(v/layout.dbu) for v in report['die_area_um']])
    if bbox.left<die.left or bbox.bottom<die.bottom or bbox.right>die.right or bbox.top>die.top:raise ValueError('Custom cell outside die: '+family)
    entries[family]=dict(reference_sites=sites,bond_openings_match=True,bbox_um=umbox(bbox),
        allocated_region_area_um2=reserved_area,geometry_within_allocation=True,
        area_ceiling_um2=layout_report['area_ceiling_um2'],
        region_area_within_ceiling=reserved_area<=layout_report['area_ceiling_um2'],
        transform=dict(rotation=rot,mirror=mirror,x_um=transform.disp.x*layout.dbu,y_um=transform.disp.y*layout.dbu),
        gds_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        layout_report_sha256=hashlib.sha256((work/f'candidate_{family}-layout.json').read_bytes()).hexdigest(),retained_metal_overlaps={})
    placed[family]=(cell,transform)
    ground_landings[family]=db.Region()
    for rectangle in layout_report.get('near_bond_ground_landings_um',[]):
        ground_landings[family].insert(db.Box(*[round(v/layout.dbu) for v in rectangle]).transformed(transform))
    entries[family]['declared_ground_landing_overlaps']={}
    entries[family]['unexpected_retained_metal_overlaps']={}

# GF180 5LM drawing layers, as used by the installed Magic/GDS technology.
metals={'metal1':34,'metal2':36,'metal3':42,'metal4':46,'metal5':81}
mutual_overlaps=[]
for name,number in metals.items():
    index=layout.find_layer(number,0)
    fixed=db.Region(retained.begin_shapes_rec(index));fixed.merge()
    custom_regions={}
    for family,(cell,transform) in placed.items():
        moving=db.Region(cell.begin_shapes_rec(index)).transformed(transform)
        custom_regions[family]=moving
        overlap=moving & fixed
        if not overlap.is_empty():
            entries[family]['retained_metal_overlaps'][name]=dict(area_um2=overlap.area()*layout.dbu**2,
                region_count=overlap.count(),example_boxes_um=[umbox(p.bbox()) for p in list(overlap.each())[:5]])
            intended=(overlap & ground_landings[family]) if number in (42,46,81) else db.Region()
            unexpected=overlap-intended
            if not intended.is_empty():
                entries[family]['declared_ground_landing_overlaps'][name]=dict(area_um2=intended.area()*layout.dbu**2,
                    scope='Geometric overlap at declared DVSS landing only; not extracted rail connectivity or current-capacity signoff.')
            if not unexpected.is_empty():
                entries[family]['unexpected_retained_metal_overlaps'][name]=dict(area_um2=unexpected.area()*layout.dbu**2,
                    example_boxes_um=[umbox(p.bbox()) for p in list(unexpected.each())[:5]])
    for first,second in combinations(custom_regions,2):
        overlap=custom_regions[first] & custom_regions[second]
        if not overlap.is_empty():mutual_overlaps.append(dict(first=first,second=second,layer=name,area_um2=overlap.area()*layout.dbu**2))
options=db.SaveLayoutOptions();options.select_cell(top.cell_index());options.set_format_from_filename('candidate.oas')
layout.write(str(work/'custom-assembly-candidate.oas'),options)
roundtrip=db.Layout();roundtrip.read(str(work/'custom-assembly-candidate.oas'))
rt_top=roundtrip.top_cell();it=rt_top.begin_shapes_rec(roundtrip.find_layer(37,0));actual_openings=[]
while not it.at_end():
    b=it.shape().bbox().transformed(it.trans())
    actual_openings.append(tuple(round(v*roundtrip.dbu,6) for v in (b.left,b.bottom,b.right,b.top)));it.next()
expected_openings=[tuple(round(v,6) for v in site['bond_opening_bbox_um']) for site in report['sites'].values()]
if Counter(actual_openings)!=Counter(expected_openings):raise ValueError('Streamed assembly changes provider bond openings')
has_overlap=bool(mutual_overlaps) or any(e['unexpected_retained_metal_overlaps'] for e in entries.values())
audit=dict(status='placed_custom_candidate_with_unresolved_ring_metal_overlaps' if has_overlap else 'no_unexpected_metal_overlap_declared_ground_joins_unverified',
    native_ground_landing_top_metal_labels=landing_labels,
    roundtrip_all_bond_openings_match=True,bond_opening_count=len(actual_openings),
    custom_cells=entries,custom_to_custom_metal_overlaps=mutual_overlaps,replaced_stock_signal_cells=sorted(replaced),
    restored_native_rail_modules=sorted(restored_rails),host_cell_replacements=host_replacements,
    retained_provider_site_count=len(report['sites'])-len(replaced),
    retained_power_ground_sites=[s for s in report['sites'] if s.startswith(('vdd_','vss_','dvdd_','dvss_'))],
    limitations=['Same-layer overlap is a connectivity hazard, not a net-aware short verdict; intended ground joins also appear.',
        'Native rail modules are restored geometrically; substrate ties, lower-metal access, net-aware connectivity and current capacity still need verification. No integrated DRC/LVS, power-net hookup, package-return simulation or board qualification.',
        'Positive bond is the left opening in each generated candidate; electrical polarity remains a graph/LVS obligation.',
        'Macro containment does not establish routing clearance, density or separation from the future core.'],
    source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [Path(__file__),work/'assembly-report.json',work/'custom-map.json',work/'retained-binding.json',work/'provider-reference-ring.gds']},
    oas_sha256=hashlib.sha256((work/'custom-assembly-candidate.oas').read_bytes()).hexdigest())
# Export actual merged metal/opening polygons for a host-side raster preview.
# This avoids drawing merely the macro envelopes as if they were routing.
preview={}
for name,number in {**metals,'glass':37}.items():
    region=db.Region(top.begin_shapes_rec(layout.find_layer(number,0)));region.merge()
    preview[name]=[[[[p.x*layout.dbu,p.y*layout.dbu] for p in polygon.each_point_hull()],
                    [[[p.x*layout.dbu,p.y*layout.dbu] for p in polygon.each_point_hole(i)] for i in range(polygon.holes())]]
                   for polygon in region.each()]
(work/'assembly-polygons.json').write_text(json.dumps(preview,separators=(',',':'))+'\n')
(work/'placement-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
print('Placed custom cells; overlapping retained metal:',sum(bool(e['retained_metal_overlaps']) for e in entries.values()))
