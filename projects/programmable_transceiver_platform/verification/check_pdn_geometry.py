"""Same-layer opposite-rail intersection check, including via enclosures/cuts.
This does not implement foundry spacing/enclosure or cell-obstruction DRC.
"""
import hashlib,json,sys
from pathlib import Path
from collections import Counter,defaultdict
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform';out=Path(sys.argv[2]) if len(sys.argv)>2 else root/'scratch/transceiver-pdn-geometry'
database=Path(sys.argv[3]) if len(sys.argv)>3 else root/'scratch/transceiver-pdn/digital-pdn.odb'
characterization=Path(sys.argv[4]) if len(sys.argv)>4 else p/'evidence/digital-pdn-screen.json'
report_path=Path(sys.argv[5]) if len(sys.argv)>5 else p/'evidence/pdn-geometry-screen.json'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
base=json.loads(characterization.read_text())
assert sha(database)==base['artifact_sha256']['digital-pdn.odb']
assert 'PDN_GEOMETRY_DUMP_COMPLETE' in (out/'dump.log').read_text()
rects=[]
for line in (out/'rectangles.tsv').read_text().splitlines():
 net,layer,x0,y0,x1,y1,kind=line.split('\t');r=(net,layer,int(x0),int(y0),int(x1),int(y1),kind)
 assert r[2]<r[4] and r[3]<r[5] and net in ('VDD_CORE','VSS_CORE');rects.append(r)
def check(items):
 bins=defaultdict(list);step=128000 # 64 um at the retained 2000 DBU/um
 def tiles(r):
  for x in range(r[2]//step,r[4]//step+1):
   for y in range(r[3]//step,r[5]//step+1):yield (r[1],x,y)
 for i,r in enumerate(items):
  if r[0]=='VDD_CORE':
   for tile in tiles(r):bins[tile].append(i)
 for r in items:
  if r[0]!='VSS_CORE':continue
  seen=set()
  for tile in tiles(r):
   for i in bins.get(tile,[]):
    if i in seen:continue
    seen.add(i);a=items[i]
    if max(a[2],r[2])<=min(a[4],r[4]) and max(a[3],r[3])<=min(a[5],r[5]):raise AssertionError(('opposite-rail contact',a,r))
check(rects)
# Exercise both interior overlap and exact edge contact in the same checker.
for edge in [False,True]:
 a=next(r for r in rects if r[0]=='VDD_CORE' and r[1]=='Metal4')
 b=('VSS_CORE',a[1],a[4] if edge else a[2],a[3],a[4]+1 if edge else a[4],a[5],a[6])
 try:check([a,b])
 except AssertionError:pass
 else:raise AssertionError('short mutation escaped')
counts=Counter((r[0],r[1],r[6]) for r in rects)
assert {r[1] for r in rects}=={'Metal1','Metal2','Metal3','Metal4','Metal5','Via1','Via2','Via3','Via4'}
r={'scope':'Exact closed-rectangle intersections between opposite rails on each PDN layer, including expanded native via geometry; not complete DRC',
 'rectangles_checked':len(rects),'opposite_rail_contacts':0,'negative_controls':['interior overlap rejected','edge contact rejected'],
 'counts':[{'net':n,'layer':l,'kind':k,'rectangles':v} for (n,l,k),v in sorted(counts.items())],
 'input_database_sha256':base['artifact_sha256']['digital-pdn.odb'],
 'artifact_sha256':{f:sha(out/f) for f in ['rectangles.tsv','dump.log']},
 'source_sha256':{f:sha(p/'verification'/f) for f in ['pdn_geometry_dump.tcl','check_pdn_geometry.py','run_pdn_geometry.sh']},
 'limitations':['Checks generated special-wire PDN shapes only, not all cell geometry, signal wires or pads.','No minimum spacing, enclosure, cut-array or density rules checked; complete DRC/LVS still required.','No via resistance/current, IR/EM, dynamic supply noise or package-feed qualification.','Well/substrate contacts and full-chip domain isolation remain unverified.']}
report_path.write_text(json.dumps(r,indent=2)+'\n')
print('PDN_GEOMETRY_PASS rectangles=',len(rects))
