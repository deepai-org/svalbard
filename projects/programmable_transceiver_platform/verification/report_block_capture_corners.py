import hashlib,json,pathlib,re
root=pathlib.Path(__file__).resolve().parents[3];p=root/'projects/programmable_transceiver_platform'
out=root/'scratch/transceiver-block-capture-corners'
prior=json.loads((p/'evidence/block-capture-mapping.json').read_text())
for name,digest in prior['sha256'].items():
 if name.startswith('scratch/'):
  assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
libraries=json.loads((out/'libraries.json').read_text());cases={}
def slacks(s):return [float(x) for x in re.findall(r'([-\d.]+)\s+slack',s)]
for corner in libraries:
 setup=(out/(corner+'-setup.log')).read_text();hold=(out/(corner+'-hold.log')).read_text()
 assert 'Error:' not in setup+hold and 'not found' not in setup+hold
 h=hold.split('HOLD_BEGIN read_domain\n')[1].split('HOLD_END')[0]
 assert len(set(re.findall(r'Endpoint: (\S+)',h)))==84
 hm=min(slacks(h));sens={}
 for u in ('0.5','5.0'):
  value=slacks(hold.split('SENSITIVITY_BEGIN '+u+'\n')[1].split('SENSITIVITY_END')[0])[0]
  assert abs(value-(hm-float(u)))<0.0002
  sens[u]=value
 assert sens['5.0']<0
 paths={}
 for label in ('wr_clk','rd_clk'):
  section=setup.split('CAPTURE_BEGIN '+label+'\n')[1].split('CAPTURE_END')[0]
  paths[label]=min(slacks(section))
 cases[corner]={'capture_slack_ns':paths,'minimum_read_domain_hold_ns':hm,'hold_uncertainty_sensitivity_ns':sens}
assert abs(cases['tt_025C_3v30']['minimum_read_domain_hold_ns']-1.1485)<0.0001
files=[p/'verification'/f for f in ('block_capture_corners.py','run_block_capture_corners.sh','report_block_capture_corners.py','block_capture_timing.tcl','block_capture_hold.tcl')]+list(out.glob('*.log'))
r={'pass':62,'corners':cases,'library_sha256':libraries,'scope':'Fixed nominal mapped fixture. Available mixed PVT stress screens, not process-only or proof of bounding the intended narrow envelope. Ideal clocks, no wire RC or local variation; capture paths only.','sha256':{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
(p/'evidence/block-capture-corners.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(cases,indent=2))
