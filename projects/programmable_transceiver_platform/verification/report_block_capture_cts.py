import hashlib,json,pathlib,re
root=pathlib.Path(__file__).resolve().parents[3];p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-block-capture-cts'
prior=json.loads((p/'evidence/block-capture-placement.json').read_text())
name='scratch/transceiver-block-capture-placement/digital.odb'
assert hashlib.sha256((root/name).read_bytes()).hexdigest()==prior['sha256'][name]
log=(out/'cts.log').read_text();assert 'Error' not in log
assert 'Total number of Clock Roots: 2.' in log and 'Total number of Sinks: 791.' in log
cases={}
def minimum(s):return min(float(x) for x in re.findall(r'([-\d.]+)\s+slack',s))
for corner in ('tt_025C_3v30','ff_n40C_3v60','ss_125C_3v00'):
 h=(out/(corner+'-hold.log')).read_text();s=(out/(corner+'-setup.log')).read_text()
 assert 'Error:' not in h+s and 'not found' not in h+s
 assert 'clock network delay (propagated)' in h
 paths={}
 for label in ('pointer','feedback','ready','read_domain'):
  section=h.split('HOLD_BEGIN '+label+'\n')[1].split('HOLD_END')[0]
  assert len(set(re.findall(r'Endpoint: (\S+)',section)))==84
  paths[label]=minimum(section)
 sens=minimum(h.split('SENSITIVITY_BEGIN 0.5\n')[1].split('SENSITIVITY_END')[0])
 assert abs(sens-paths['read_domain']+0.5)<0.0002
 assert not s.split('ELECTRICAL_BEGIN')[1].split('ELECTRICAL_END')[0].strip()
 cases[corner]={'capture_setup_min_ns':minimum(s),'hold_paths_ns':paths,'hold_with_0p5ns_uncertainty':sens}
assert cases['ff_n40C_3v60']['hold_with_0p5ns_uncertainty']<0
files=[p/'verification'/f for f in ('block_capture_cts.tcl','block_capture_cts_timing.py','run_block_capture_cts.sh','report_block_capture_cts.py')]+[out/f for f in ('digital.odb','digital.def','cts.log')]+list(out.glob('*-*.log'))
r={'pass':64,'status':'hold sensitivity failure retained','clock_roots':2,'clock_sinks':791,'clock_tree_buffers':54,'corners':cases,'scope':'Propagated CTS cells with placement-estimated RC. Zero-minimum ready arrival, illustrative 0.5ns uncertainty. No routed timing, functional CTS equivalence, reset/CDC or full-chip signoff.','sha256':{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
(p/'evidence/block-capture-cts.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(cases,indent=2))
