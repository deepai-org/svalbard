import hashlib,json,pathlib,re
root=pathlib.Path(__file__).resolve().parents[3]
p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-block-capture-hold'
log=(out/'hold.log').read_text()
assert 'Error:' not in log and 'Warning:' not in log
prior=json.loads((p/'evidence/block-capture-mapping.json').read_text())
for name,digest in prior['sha256'].items():
 if name.startswith('scratch/'):
  assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest, name
results={}
for label in ('pointer','feedback','ready','read_domain'):
 s=log.split('HOLD_BEGIN '+label+'\n')[1].split('HOLD_END')[0]
 endpoints=re.findall(r'Endpoint: (\S+)',s)
 slacks=[float(x) for x in re.findall(r'([-\d.]+)\s+slack',s)]
 assert len(endpoints)==len(set(endpoints))==len(slacks)==84
 results[label]={'endpoints':84,'minimum_slack_ns':min(slacks)}
base=results['read_domain']['minimum_slack_ns']
sensitivity={}
for label in ('0.5','5.0'):
 s=log.split('SENSITIVITY_BEGIN '+label+'\n')[1].split('SENSITIVITY_END')[0]
 slack=float(re.search(r'([-\d.]+)\s+slack',s)[1])
 assert abs(slack-(base-float(label)))<0.0002
 sensitivity[label]=slack
assert sensitivity['0.5']>0 and sensitivity['5.0']<0
files=[p/'verification'/f for f in ('block_capture_hold.tcl','run_block_capture_hold.sh','report_block_capture_hold.py')]+[out/'hold.log',root/'scratch/transceiver-block-capture-mapping/mapped.v']
r={'pass':61,'paths':results,'hold_uncertainty_sensitivity_ns':sensitivity,'minimum_ready_input_delay_ns':0,'scope':'TT 25C 3.3V ideal-clock zero-wire-RC capture hold only; no fast corner, CTS, routed hold, asynchronous storage-path hold or reset signoff.','sha256':{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
(p/'evidence/block-capture-hold.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({k:v for k,v in r.items() if k!='sha256'},indent=2))
