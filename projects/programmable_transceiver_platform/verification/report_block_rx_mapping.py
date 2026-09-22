import pathlib,json,re,hashlib
root=pathlib.Path(__file__).resolve().parents[3];p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-block-rx-mapping'
s=(out/'timing.log').read_text();assert 'Error:' not in s and 'not found' not in s
stat=json.loads((out/'stat.json').read_text())['design'];cases={}
for mode in (0,1):
 paths={}
 for delay in ('max','min'):
  section=s.split(f'PATH_BEGIN {mode} {delay}\n')[1].split('PATH_END')[0]
  found=[]
  for path in section.split('Startpoint:')[1:]:
   found.append({'slack_ns':float(re.search(r'([-\d.]+)\s+slack',path)[1]),'startpoint':path.splitlines()[0].strip(),'endpoint':re.search(r'Endpoint: (.*)',path)[1]})
  paths[delay]=min(found,key=lambda x:x['slack_ns'])
 assert paths['max']['slack_ns'] < -8
 cases[mode]=paths
assert not s.split('ELECTRICAL_BEGIN')[1].split('ELECTRICAL_END')[0].strip()
assert 'unconstrained endpoints' not in s
files=[p/'rtl'/f for f in ('pt_block_rx.sv','pt_block_header.sv','pt_block_route.sv','pt_lane_compact.sv','pt_schedule.vh')]+[p/'verification'/f for f in ('block_rx_timing.tcl','run_block_rx_mapping.sh','report_block_rx_mapping.py')]+[out/f for f in ('mapped.v','mapped.json','stat.json','timing.log','library.sha256')]
r={'pass':75,'status':'setup fails both modes','cell_area_um2':stat['area'],'flip_flops':sum(n for k,n in stat['num_cells_by_type'].items() if '__dff' in k),'paths':cases,'period_ns':25.6,'input_max_delay_ns':4,'output_max_delay_ns':4,'scope':'Nominal TT25C3.3V unplaced ideal clocks/no wire RC. No mapped equivalence, queues or physical signoff.','sha256':{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
(p/'evidence/block-rx-mapping.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='sha256'},indent=2))
