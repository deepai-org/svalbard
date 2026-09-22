import pathlib,json,re,hashlib
root=pathlib.Path(__file__).resolve().parents[3];p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-block-rx-commit-physical'
prior=json.loads((p/'evidence/block-rx-commit-mapping.json').read_text());name='scratch/transceiver-block-rx-commit-mapping/mapped.v'
assert hashlib.sha256((root/name).read_bytes()).hexdigest()==prior['sha256'][name]
log=(out/'physical.log').read_text();assert 'Error' not in log and 'Total number of Sinks: 330.' in log
counts=json.loads((out/'placement-counts.json').read_text());assert counts['unplaced']==0
cases={}
for corner in ('tt_025C_3v30','ff_n40C_3v60','ss_n40C_3v00','ss_125C_3v00'):
 s=(out/(corner+'.log')).read_text();assert 'Error:' not in s and 'not found' not in s and 'clock network delay (propagated)' in s
 paths={}
 for mode in (0,1):
  for kind in ('max','min'):
   section=s.split(f'PATH_BEGIN {mode} {kind}\n')[1].split('PATH_END')[0];found=[]
   for path in section.split('Startpoint:')[1:]:
    found.append({'slack_ns':float(re.search(r'([-\d.]+)\s+slack',path)[1]),'startpoint':path.splitlines()[0].strip(),'endpoint':re.search(r'Endpoint: (.*)',path)[1]})
   paths[f'{mode}:{kind}']=min(found,key=lambda x:x['slack_ns'])
 assert not s.split('ELECTRICAL_BEGIN')[1].split('ELECTRICAL_END')[0].strip()
 cases[corner]=paths
assert cases['ss_n40C_3v00']['1:max']['slack_ns']<0 and cases['tt_025C_3v30']['1:min']['slack_ns']<0
files=[p/'verification'/f for f in ('block_rx_commit_physical.tcl','block_rx_commit_physical.py','run_block_rx_commit_physical.sh','report_block_rx_commit_physical.py','block_rx_commit_timing.tcl')]+[out/f for f in ('digital.odb','digital.def','placed.odb','physical.log','placement-counts.json')]+list(out.glob('*C*.log'))
r={'pass':87,'status':'slow-corner setup and provisional interface hold fail','pre_cts_placement':counts,'clock_roots':1,'clock_sinks':330,'clock_tree_buffers':31,'hold_uncertainty_ns':0.5,'corners':cases,'scope':'Propagated CTS with placement-estimated RC. No routed timing, verified source launch contract, CTS equivalence, full geometry/DRC or physical signoff.','sha256':{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
(p/'evidence/block-rx-commit-physical.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({c:{k:v['slack_ns'] for k,v in d.items()} for c,d in cases.items()},indent=2))
