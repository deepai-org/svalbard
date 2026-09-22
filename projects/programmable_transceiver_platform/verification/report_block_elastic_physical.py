import hashlib,json,pathlib,re
root=pathlib.Path(__file__).resolve().parents[3];p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-block-elastic-physical'
prior=json.loads((p/'evidence/block-elastic-mapping.json').read_text())
for name,digest in prior['sha256'].items():
 if name.startswith('scratch/'):
  assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
log=(out/'physical.log').read_text()
assert 'Error' not in log and 'Total number of Sinks: 881.' in log
assert 'Total number of Clock Roots: 2.' in log
counts=json.loads((out/'placement-counts.json').read_text());assert counts['unplaced']==0
cases={}
for corner in ('tt_025C_3v30','ff_n40C_3v60','ss_125C_3v00'):
 text=(out/(corner+'.log')).read_text()
 assert 'Error:' not in text and 'not found' not in text and 'clock network delay (propagated)' in text
 paths={}
 for kind in ('max','min'):
  section=text.split('CAPACITY_BEGIN '+kind+'\n')[1].split('CAPACITY_END')[0]
  assert len(set(re.findall(r'Endpoint: (\S+)',section)))==168
  paths[kind]=min(float(x) for x in re.findall(r'([-\d.]+)\s+slack',section))
 assert not text.split('ELECTRICAL_BEGIN')[1].split('ELECTRICAL_END')[0].strip()
 cases[corner]=paths
files=[p/'verification'/f for f in ('block_elastic_physical.tcl','block_elastic_physical_timing.py','run_block_elastic_physical.sh','report_block_elastic_physical.py')]+[out/f for f in ('digital.odb','digital.def','placed.odb','physical.log','placement-counts.json')]+list(out.glob('*C*.log'))
r={'pass':67,'pre_cts_placement':counts,'clock_roots':2,'clock_sinks':881,'tree_buffers':59,'capacity_path_slack_ns':cases,'hold_uncertainty_ns':0.5,'scope':'Capacity flag to 168 receiving data bits only. Propagated CTS, placement-estimated RC, mixed PVT stress corners. No routed timing, whole-buffer/interface qualification, CDC/reset signoff or CTS equivalence.','sha256':{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
(p/'evidence/block-elastic-physical.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(cases,indent=2))
