"""Audit a pinned provider COB board against the selected bond-site assignment.

Board net assignments and projected geometry are evidence, not a released-run
bond map, RF package model or manufacturing signoff.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from design import PROJECT


def sexpr(text):
    root=[];stack=[root]
    for token in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text):
        if token=='(':
            row=[];stack[-1].append(row);stack.append(row)
        elif token==')':
            if len(stack)==1:raise ValueError('Unbalanced PCB syntax')
            stack.pop()
        else:stack[-1].append(json.loads(token) if token.startswith('"') else token)
    if len(stack)!=1 or len(root)!=1:raise ValueError('Incomplete PCB syntax')
    return root[0]


def children(node,key):
    return [v for v in node if isinstance(v,list) and v and v[0]==key]


def inspect_layout(assembly, mask):
    """Run with KLayout's Python module; retain real polygon subtraction."""
    import klayout.db as k
    layout=k.Layout();layout.read(str(assembly));top=layout.top_cell();box=top.dbbox()
    result=dict(dbu_um=layout.dbu,top_cells=[c.name for c in layout.top_cells()],
        bbox_um=[box.left,box.bottom,box.right,box.top],
        guard_ring_marker_polygons=k.Region(top.begin_shapes_rec(layout.layer(167,5))).count(),
        identifiers=[c.name for c in layout.each_cell() if any(n in c.name for n in ('qrcode','project_id','shuttle_id','marker'))])
    golden=k.Layout();golden.read(str(mask));regions=[]
    if layout.dbu!=golden.dbu:raise ValueError('Different layout database units')
    for label,view in [('current',layout),('golden',golden)]:
        region=k.Region(view.top_cell().begin_shapes_rec(view.layer(37,0))).merged();regions.append(region)
        result[label+'_openings_um']=sorted([[v*view.dbu for v in
            (p.bbox().left,p.bbox().bottom,p.bbox().right,p.bbox().top)] for p in region.each()])
    result['missing_required_opening_area_um2']=(regions[1]-regions[0]).area()*layout.dbu**2
    result['source_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (assembly,mask)}
    return result


def audit(board, output, layout_inventory=None):
    contract=PROJECT/'spec/contract.json';placement=PROJECT/'analog/pads/generated/assembly-report.json'
    policy=json.loads(contract.read_text())['assembly_policy'];geometry=json.loads(placement.read_text())
    footprints=children(sexpr(board.read_text()),'footprint')
    bond=next(f for f in footprints if 'default_padring' in f[1])
    connector=next(f for f in footprints if '70P-' in f[1])
    if children(bond,'at')[0][-1]!='180':raise ValueError('Re-audit changed board orientation')
    pads={int(p[1]):p for p in children(bond,'pad') if p[1].isdigit() and 1<=int(p[1])<=74}
    if set(pads)!=set(range(1,75)):raise ValueError('Expected all 74 die bond sites')
    breakout={}
    for p in children(connector,'pad'):
        if p[1].isdigit() and 1<=int(p[1])<=70:
            breakout.setdefault(children(p,'net')[0][-1],[]).append(int(p[1]))
    if len(set(sum(breakout.values(),[])))!=70:raise ValueError('Incomplete connector inventory')
    # Physical counterclockwise order, beginning at the southwest pad. Template
    # arrays run left-to-right / bottom-to-top on ALL sides; north/west reverse.
    order=[]
    for side in ('south','east','north','west'):
        sites=policy['provider_site_inventory']['ordered_sites_by_side'][side]
        axis=0 if side in ('south','north') else 1
        physical=sorted(sites,key=lambda n:geometry['sites'][n]['bond_center_um'][axis],reverse=side in ('north','west'))
        order.extend((side,n) for n in physical)
    signals={v:k for k,v in policy['candidate_signal_sites'].items()};rows=[]
    for i,(side,site) in enumerate(order,1):
        p=pads[i];net=children(p,'net')[0][-1]
        xy=list(map(float,children(p,'at')[0][1:3]));target=[-xy[0],xy[1]]
        # Centered die; 180 degree footprint rotation plus PCB-down/GDS-up Y.
        source=[(geometry['sites'][site]['bond_center_um'][j]-geometry['die_area_um'][j+2]/2)/1000 for j in (0,1)]
        delta=[target[j]-source[j] for j in (0,1)]
        normal=abs(delta[1 if side in ('south','north') else 0]);tangent=abs(delta[0 if side in ('south','north') else 1])
        ground='vss_pads' in site;power='vdd_pads' in site
        if ground and net!='GND':raise ValueError('Ground mismatch: '+site)
        if power and not net.startswith(('VDD_','PWR_AUX')):raise ValueError('Power mismatch: '+site)
        if not ground and not power and net!='/'+f'pad_{i-1}':raise ValueError('Signal mismatch: '+site)
        if not breakout.get(net):raise ValueError('Bond net has no connector access')
        rows.append(dict(bond_number_1based=i,provider_site=site,signal=signals.get(site),side=side,
                         board_net=net,connector_pins=sorted(breakout[net]),die_centered_mm=source,
                         pcb_landing_centered_mm=target,projected_center_length_mm=math.hypot(*delta),
                         projected_angle_deg=math.degrees(math.atan2(tangent,normal))))
    report=dict(status='pinned_run2_board_net_mapping_and_center_projection_not_production_approval',
        board_revision='5cb466897372ac6c9df03142287858c1c8b1c9a7',board_path='run-2/1x1-cob/1x1-mezzanine.kicad_pcb',
        provider_template_revision='33e4b5ecc9faac82787fa7cb205f08377e27b912',
        checked_on='2026-10-18',bond_sites=len(rows),connector_contacts=70,
        all_provider_power_ground_assignments_match=True,all_functional_signals_reach_connector=len(signals)==sum(r['signal'] is not None for r in rows),
        all_ground_sites_share_board_net=True,
        projected_center_length_range_mm=[min(r['projected_center_length_mm'] for r in rows),max(r['projected_center_length_mm'] for r in rows)],
        maximum_projected_angle_deg=max(r['projected_angle_deg'] for r in rows),sites=rows,
        limitations=['Run 2 repository design is a pinned candidate, not confirmation of the board delivered for a future run.',
        'Center-to-center straight segments assume centered die placement. Real landing choice within 1mm pads, die thickness and wire-loop height are not supplied by this audit.',
        'Published run-1 wire rules are <3mm length, <=45deg angle, minimum max(1mm,2*die thickness), no crossings and no solder mask in bonding area. Their application to the chosen run and actual loops must be established.',
        'Net labels are not a copper connectivity extraction, impedance model, power-current rating or crosstalk qualification.',
        'Separate PCB VDD/AUX labels do not prove separate die supplies: native ring rails may join them. Grounds explicitly share the board return.'],
        sources={'board':'https://github.com/wafer-space/chip-on-board-wire-bonded-pcbs/blob/5cb466897372ac6c9df03142287858c1c8b1c9a7/run-2/1x1-cob/1x1-mezzanine.kicad_pcb',
                 'template':'https://github.com/wafer-space/gf180mcu-project-template/blob/33e4b5ecc9faac82787fa7cb205f08377e27b912/README.md',
                 'wire_rules':'https://github.com/wafer-space/chip-on-board-wire-bonded-pcbs/blob/5cb466897372ac6c9df03142287858c1c8b1c9a7/run-1/wirebonding/README.md'},
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),board,contract,placement)})
    if layout_inventory is not None:
        layout=json.loads(layout_inventory.read_text())
        gold=[b for b in layout['golden_openings_um'] if b[2]-b[0]<100 and b[3]-b[1]<100]
        current=layout['current_openings_um'];offsets=[]
        if len(gold)!=74 or len(current)!=74:raise ValueError('Re-audit changed mask inventory')
        for b in current:
            match=min(gold,key=lambda g:sum((g[i]-b[i])**2 for i in range(4)))
            if b!=match:offsets.append(dict(current_bbox_um=b,required_bbox_um=match,
                                           lower_left_delta_um=[match[i]-b[i] for i in (0,1)]))
        report['inspected_layout_sources']=layout.get('source_sha256',{})
        report['submission_geometry']={
            'status':'not_submission_ready',
            'layout_dbu_um':layout['dbu_um'],'top_cells':layout['top_cells'],
            'bbox_um':layout['bbox_um'],'expected_bbox_um':[0,0,3932,5122],
            'guard_ring_marker_polygons':layout['guard_ring_marker_polygons'],
            'present_identifier_cells':layout['identifiers'],
            'required_identifier_cells':['gf180mcu_ws_ip__'+n for n in ('qrcode_id','shuttle_id','project_id','marker')],
            'misaligned_bond_opening_count':len(offsets),'misaligned_openings':offsets,
            'missing_required_opening_area_um2':layout['missing_required_opening_area_um2'],
            'provider_precheck_revision':'8d58ff75fb9e2169a37876696eb470a42c6c9701',
            'official_check_observations':{'size':(layout_inventory.parent/'size-check.log').read_text().strip(),
                                           'pad_mask':(layout_inventory.parent/'mask-check.log').read_text().strip()},
            'scope':'Actual partial routed assembly inspected; two upstream geometry scripts run. Not full precheck, DRC/LVS or package qualification.'}
        for path in (layout_inventory,layout_inventory.parent/'size-check.log',layout_inventory.parent/'mask-check.log'):
            report['source_sha256'][str(path.resolve())]=hashlib.sha256(path.read_bytes()).hexdigest()
    output.write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--layout-inventory',type=Path)
    a=p.parse_args();r=audit(a.board.resolve(),a.output.resolve(),a.layout_inventory);print(json.dumps({k:v for k,v in r.items() if k not in ('sites','source_sha256','sources')},indent=2))
