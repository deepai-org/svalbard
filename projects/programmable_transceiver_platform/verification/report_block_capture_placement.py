import hashlib,json,pathlib,re
root=pathlib.Path(__file__).resolve().parents[3];p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-block-capture-placement'
prior=json.loads((p/'evidence/block-capture-mapping.json').read_text())
for name,digest in prior['sha256'].items():
 if name.startswith('scratch/'):
  assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
counts=json.loads((out/'placement-counts.json').read_text())
assert counts['instances']==2251 and counts['unplaced']==0
boxes=[]
for line in (out/'cells.tsv').read_text().splitlines():
 name,x,y,xx,yy,orient=line.split();boxes.append((name,int(x),int(y),int(xx),int(yy)))
def geometry(boxes):
 active=[]
 for b in sorted(boxes,key=lambda b:b[1]):
  _,x,y,xx,yy=b
  assert 20000<=x<xx<=1020000 and 20000<=y<yy<=820000,'bounds'
  active=[a for a in active if a[3]>x]
  assert all(yy<=a[2] or y>=a[4] for a in active),'overlap'
  active.append(b)
geometry(boxes)
assert len(boxes)==2251 and len(set(b[0] for b in boxes))==2251
try:geometry(boxes+[boxes[0]])
except AssertionError as e:assert str(e)=='overlap'
else:raise AssertionError('overlap control escaped')
corners={}
for corner in ('tt_025C_3v30','ff_n40C_3v60','ss_125C_3v00'):
 setup=(out/(corner+'-setup.log')).read_text();hold=(out/(corner+'-hold.log')).read_text()
 assert 'Error:' not in setup+hold and 'not found' not in setup+hold
 assert not setup.split('ELECTRICAL_BEGIN')[1].split('ELECTRICAL_END')[0].strip()
 def minimum(text):return min(float(x) for x in re.findall(r'([-\d.]+)\s+slack',text))
 h=hold.split('HOLD_BEGIN read_domain\n')[1].split('HOLD_END')[0]
 assert len(set(re.findall(r'Endpoint: (\S+)',h)))==84
 corners[corner]={'capture_min_setup_slack_ns':minimum(setup),'read_domain_hold_ns':minimum(h),'hold_with_0p5ns_uncertainty':minimum(hold.split('SENSITIVITY_BEGIN 0.5\n')[1].split('SENSITIVITY_END')[0])}
files=[p/'verification'/f for f in ('block_capture_place.tcl','block_capture_placed_timing.py','run_block_capture_placement.sh','report_block_capture_placement.py')]+[out/f for f in ('digital.odb','digital.def','cells.tsv','placement.log')]+list(out.glob('*-*.log'))
r={'pass':63,'placement':counts,'independent_bounds_nonoverlap':'pass','overlap_negative_control':'pass','corners':corners,'scope':'Placement-based Metal3 RC, ideal clocks. No CTS, routing, PDN, full DRC, Gray skew, hold closure or CDC signoff.','sha256':{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
(p/'evidence/block-capture-placement.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(corners,indent=2))
