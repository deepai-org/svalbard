"""Independent single-height standard-cell geometry checks for this experiment."""
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
out=Path(sys.argv[1]);project=Path(__file__).resolve().parents[1]
deftext=(out/'digital.def').read_text()
dbu=int(re.search(r'UNITS DISTANCE MICRONS (\d+)',deftext)[1])
rows={}
for x,y,orient,n,pitch in re.findall(r'^ROW \S+ \S+ (\d+) (\d+) (\S+) DO (\d+) BY 1 STEP (\d+) 0 ;',deftext,re.M):
    rows[int(y)]=(int(x),int(n),int(pitch),orient)
ys=sorted(rows);height=ys[1]-ys[0]
assert rows and all(b-a==height for a,b in zip(ys,ys[1:])), 'unexpected row geometry'
cells=[]
for line in (out/'cells.tsv').read_text().splitlines():
    name,x0,y0,x1,y1,orient=line.split('\t')
    cells.append((name,int(x0),int(y0),int(x1),int(y1),orient))
def validate(items):
    occupied={}
    assert len({c[0] for c in items})==len(items),'duplicate instance'
    for name,x0,y0,x1,y1,orient in items:
        assert y0 in rows and y1-y0==height,'row or height'
        start,n,pitch,row_orient=rows[y0]
        assert start<=x0<x1<=start+n*pitch,'row boundary'
        assert (x0-start)%pitch==0 and (x1-x0)%pitch==0,'site alignment'
        allowed={'N':{'R0','MY'},'FS':{'MX','R180'}}[row_orient]
        assert orient in allowed,'row orientation'
        occupied.setdefault(y0,[]).append((x0,x1,name))
    for row in occupied.values():
        row.sort()
        assert all(a[1]<=b[0] for a,b in zip(row,row[1:])),'cell overlap'
validate(cells)
# Deliberately malformed layouts must be rejected by the same checker.
mutations=[]
bad=list(cells);c=list(bad[0]);c[1]+=1;c[3]+=1;bad[0]=tuple(c);mutations.append(bad)
bad=list(cells);c=list(bad[0]);delta=rows[c[2]][0]-rows[c[2]][2]-c[1];c[1]+=delta;c[3]+=delta;bad[0]=tuple(c);mutations.append(bad)
a=0;b=next(i for i,c in enumerate(cells) if i!=a and c[2]==cells[a][2])
bad=list(cells);c=list(bad[b]);delta=cells[a][1]-c[1];c[1]+=delta;c[3]+=delta;bad[b]=tuple(c);mutations.append(bad)
for bad in mutations:
    try:validate(bad)
    except AssertionError:pass
    else:raise AssertionError('negative geometry control passed')
counts=json.loads((out/'placement-counts.json').read_text())
assert counts['unplaced']==0 and counts['instances']==len(cells)
area=sum((c[3]-c[1])*(c[4]-c[2]) for c in cells)/dbu**2
assert abs(area-counts['cell_area_um2'])<0.01
row_area=sum(n*pitch*height for _,n,pitch,_ in rows.values())/dbu**2
characterization=Path(sys.argv[2]) if len(sys.argv)>2 else project/'evidence/delay-sized-screen.json'
record=json.loads(characterization.read_text())
if 'area_screen' in record:
    sized=record['area_screen']
else:
    assert record['equivalence']['proof_status']=='pass','unproven repaired candidate'
    sized={'mapped_netlist_sha256':record['artifact_sha256']['repaired.v'],
           'physical_cell_count':record['after']['cells'],'cell_area_um2':record['after']['cell_area_um2']}

assert hashlib.sha256((out/'input.v').read_bytes()).hexdigest()==sized['mapped_netlist_sha256']
assert len(cells)==sized['physical_cell_count'] and abs(area-sized['cell_area_um2'])<0.01
r={'scope':'Digital-region placement of sized netlist; not routed/full-chip/timing signoff',
   'characterization_sha256':hashlib.sha256(characterization.read_bytes()).hexdigest(),
   'instances':len(cells),'unplaced':0,'cell_area_um2':area,'row_area_um2':row_area,'row_utilization':area/row_area,
   'checks':['OpenROAD check_placement','independent row/boundary/site/orientation/overlap checks','three deliberately invalid geometry controls rejected','cell count/area matches characterized sizing netlist'],
   'pdk_sha256':(out/'pdk.sha256').read_text().splitlines(),
   'artifact_sha256':{f:hashlib.sha256((out/f).read_bytes()).hexdigest() for f in ['input.v','digital.def','digital.odb','cells.tsv','placement.log']},
   'source_sha256':{f:hashlib.sha256((project/'verification'/f).read_bytes()).hexdigest() for f in ['placement_screen.tcl','run_placement_screen.sh','check_placement_screen.py']},
   'limitations':['Abstract digital-region boundaries/pins; no analog macros or full-chip padframe.',
      'No PDN/taps/decaps/fillers, clock tree, reset repair, routing or extracted parasitics.',
      'No physical timing repair or post-placement timing claim; previous setup/recovery failures remain.',
      'No routability/congestion or final area/power/DRC/LVS qualification.']}
(out/'placement-screen.json').write_text(json.dumps(r,indent=2)+'\n')
print(f'PLACEMENT_SCREEN_PASS cells={len(cells)} row_utilization={area/row_area:.4%}')
