"""Run inside the pinned container: stream the placed reference IO library ring."""
import hashlib
import json
from pathlib import Path
import re
import math
import klayout.db as db

root=Path('/pdk/gf180mcuD/libs.ref/gf180mcu_fd_io')
work=Path('/work')
layout=db.Layout();gds=root/'gds/gf180mcu_fd_io.gds';layout.read(str(gds))
top=layout.create_cell('provider_reference_ring')
report=json.loads((work/'assembly-report.json').read_text())
orientations={'R0':(0,False),'R90':(1,False),'R180':(2,False),'R270':(3,False),
              'MX':(0,True),'MY':(2,True),'MXR90':(1,True),'MYR90':(3,True)}
layer=layout.find_layer(37,0)
lef_hashes={}
transforms=[]
for line in (work/'sites.tsv').read_text().splitlines():
    name,master,orientation,*box=line.split('\t')
    x0,y0,x1,y1=[int(v)/2000 for v in box]
    lef=root/'lef'/f'{master}.lef';text=lef.read_text()
    lef_hashes[master]=hashlib.sha256(lef.read_bytes()).hexdigest()
    width,height=map(float,re.search(r'SIZE\s+([\d.]+)\s+BY\s+([\d.]+)',text).groups())
    cell=layout.cell(master)
    if cell is None:raise ValueError('Missing library GDS cell '+master)
    rot,mirror=orientations[orientation]
    orientation_only=db.Trans(rot,mirror,0,0)
    box_native=db.Box(0,0,round(width/layout.dbu),round(height/layout.dbu))
    rotated=box_native.transformed(orientation_only)
    trans=db.Trans(rot,mirror,round(x0/layout.dbu)-rotated.left,round(y0/layout.dbu)-rotated.bottom)
    actual=box_native.transformed(trans)
    expected=db.Box(round(x0/layout.dbu),round(y0/layout.dbu),round(x1/layout.dbu),round(y1/layout.dbu))
    if actual!=expected:raise ValueError('Orientation/LEF bbox mismatch '+name)
    top.insert(db.CellInstArray(cell.cell_index(),trans))
    transforms.append(dict(name=name,master=master,rotation=rot,mirror=mirror,x=trans.disp.x,y=trans.disp.y))
    if name in report['sites']:
        openings=[]
        it=cell.begin_shapes_rec(layer)
        while not it.at_end():
            bbox=it.shape().bbox().transformed(it.trans()).transformed(trans)
            openings.append([v*layout.dbu for v in [bbox.left,bbox.bottom,bbox.right,bbox.top]])
            it.next()
        if len(openings)!=1:raise ValueError(f'Expected one bond opening for {name}, got {len(openings)}')
        report['sites'][name]['bond_opening_bbox_um']=openings[0]
        b=openings[0];report['sites'][name]['bond_center_um']=[(b[0]+b[2])/2,(b[1]+b[3])/2]
(work/'placement-transforms.json').write_text(json.dumps(transforms)+'\n')
options=db.SaveLayoutOptions();options.select_cell(top.cell_index());layout.write(str(work/'provider-reference-ring.gds'),options)
report['geometry_sources']=dict(library_gds_sha256=hashlib.sha256(gds.read_bytes()).hexdigest(),
    lef_sha256=lef_hashes,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    gds_sha256=hashlib.sha256((work/'provider-reference-ring.gds').read_bytes()).hexdigest())
report['limitations']=[s for s in report['limitations'] if not s.startswith('Bond opening coordinates require')]
report['limitations'].append('Reference ring retains stock signal protection; it must not be used as the custom electrical implementation.')
report['candidate_geometry']={}
for path in work.glob('candidate_*.gds'):
    candidate=db.Layout();candidate.read(str(path));cell=candidate.top_cell()
    it=cell.begin_shapes_rec(candidate.find_layer(37,0));centers=[]
    while not it.at_end():
        box=it.shape().bbox().transformed(it.trans());centers.append([box.center().x*candidate.dbu,box.center().y*candidate.dbu]);it.next()
    if len(centers)!=2:raise ValueError('Expected two custom candidate bond openings: '+path.name)
    family=path.stem.removeprefix('candidate_')
    report['candidate_geometry'][family]=dict(bond_centers_um=centers,bond_pitch_um=math.dist(*centers),
        gds_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
(work/'assembly-report.json').write_text(json.dumps(report,indent=2)+'\n')
