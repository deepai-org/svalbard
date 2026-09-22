import pathlib,json,re,hashlib
root=pathlib.Path(__file__).resolve().parents[3];p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-block-rx-commit-corners'
prior=json.loads((p/'evidence/block-rx-commit-mapping.json').read_text());name='scratch/transceiver-block-rx-commit-mapping/mapped.v'
assert hashlib.sha256((root/name).read_bytes()).hexdigest()==prior['sha256'][name]
libraries=json.loads((out/'libraries.json').read_text());cases={}
for corner in libraries:
 s=(out/(corner+'.log')).read_text();assert 'Error:' not in s and 'not found' not in s
 paths={}
 for mode in (0,1):
  for kind in ('max','min'):
   section=s.split(f'PATH_BEGIN {mode} {kind}\n')[1].split('PATH_END')[0]
   found=[]
   for path in section.split('Startpoint:')[1:]:
    found.append({'slack_ns':float(re.search(r'([-\d.]+)\s+slack',path)[1]),'startpoint':path.splitlines()[0].strip(),'endpoint':re.search(r'Endpoint: (.*)',path)[1]})
   paths[f'{mode}:{kind}']=min(found,key=lambda x:x['slack_ns'])
 assert not s.split('ELECTRICAL_BEGIN')[1].split('ELECTRICAL_END')[0].strip()
 cases[corner]=paths
assert cases['tt_025C_3v30']['1:max']['slack_ns']==prior['paths']['1']['max']['slack_ns']
assert cases['ss_125C_3v00']['1:max']['slack_ns']<0
files=[p/'verification'/f for f in ('block_rx_commit_corners.py','run_block_rx_commit_corners.sh','report_block_rx_commit_corners.py','block_rx_commit_timing.tcl')]+list(out.glob('*.log'))
r={'pass':86,'status':'available slow mixed-PVT setup screens fail','corners':cases,'library_sha256':libraries,'scope':'Fixed nominal mapped netlist, ideal clocks/no wire RC. Mixed PVT stress screens do not define or bound the user-approved narrow operating window.','sha256':{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
(p/'evidence/block-rx-commit-corners.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({c:{k:v['slack_ns'] for k,v in d.items()} for c,d in cases.items()},indent=2))
