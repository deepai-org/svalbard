import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
r=json.loads((root/'scratch/transceiver-gray-prefix-mapping/buffered/timing-screen.json').read_text())
assert r['area_screen']['source_sha256']['rtl/pt_fifo.sv']==sha(p/'evidence/experiments/fifo-prefix-candidate.sv')
base=json.loads((p/'evidence/fifo-flags-screen.json').read_text())
assert sha(p/'rtl/pt_fifo.sv')==base['area_screen']['source_sha256']['rtl/pt_fifo.sv']
r['conversion_proof']=json.loads((root/'scratch/transceiver-gray-prefix-proof/proof.json').read_text())
logs=['transceiver-gray-prefix-proof.log','transceiver-gray-prefix-baseline.log','transceiver-gray-prefix-restored.log']
a,b,c=[(root/'scratch'/f).read_text() for f in logs]
assert 'GRAY_PREFIX_PROOF_PASS widths=3 negative_controls=3' in a
assert 'BASELINE_PASS' in b
assert 'SYNC_FIFO_FLAGS_PASS' in c and 'FIFO_FLAGS_NEGATIVE_CONTROL_PASS' in c
r['verification_log_sha256']={f:sha(root/'scratch'/f) for f in logs}
r['report_source_sha256']=sha(p/'verification/report_gray_prefix.py')
r['decision']='Reject candidate after worse high-speed timing; pass-41 FIFO RTL restored byte-identically. Balanced Boolean depth did not establish a mapped timing benefit.'
r['comparison_reference']='fifo-flags-screen.json'
r['restored_fifo_sha256']=sha(p/'rtl/pt_fifo.sv')
(p/'evidence/rejected-gray-prefix-screen.json').write_text(json.dumps(r,indent=2)+'\n')
