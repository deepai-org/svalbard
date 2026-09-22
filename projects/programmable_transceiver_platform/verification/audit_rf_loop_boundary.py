#!/usr/bin/env python3
"""Record verified fixture differences before migrating autonomous timing."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';old=R/'scratch/transceiver-closed-loop-follower-prepared/closed.spice';new=R/'scratch/transceiver-bb-connected-bypass/zero.spice';cell=P/'analog/rf_rx_candidate_split.spice'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads(old.with_name('manifest.json').read_text());assert sha(old)==m['prepared_deck_sha256']
r=json.loads(new.with_name('result.json').read_text());c=next(c for c in r['cases'] if c['name']=='zero');assert c['returncode']==0 and not c['timed_out'] and sha(new)==c['artifacts_sha256']['.spice']
a=old.read_text();b=new.read_text();h=cell.read_text()
assert 'XD1 XRX.CP XRX.CN' in a and 'XFB FBG FB' in a
for line in ('XQ P N IP IN QP QN CM 0 pt_rc_quadrature','VCTRL CTRL 0 1.08','XMI RF OIP OIN','XMQ RF OQP OQN','XFI MIP MIN','XFQ MQP MQN','XCSB256 LS 0','XCSB128 LS 0','XCSB64 LS 0'):assert line in b
assert 'XD1 ' not in b
assert 'CHP HP VSS 5p' in h and 'CHN HN VSS 5p' in h and 'wifi_if_transmission_gate' in h
assert 'wifi_if_transmission_gate' not in b
out=dict(status='structural_boundary_audit_not_behavior',input_sha256={str(p.relative_to(R)):sha(p) for p in (old,new,cell)},changes=['Old oscillator drives two AC-coupled LO buffers and divide128; new P/N drive quadrature network without divider.','New path has four LO buffer/final-stage branches, two mixers/filters and448-unit LNA source bypass.','Old path includes sample switches and5pF held nodes; new filter outputs lack ADC/sample loading.'],next_integration=['Use new receiver as baseline; retain every existing LO/RF/baseband load.','Attach divider first-stage input to P/N; preserve divider/reset/feedback conversion and actual PFD input timing.','Replace only VCTRL with actual loop/filter/follower connection; retain independent regeneration bias explicitly.','Keep output ADC/interface loading marked missing; rerun tuning/phase/conversion under new loading.'],limitations=['No latest-load oscillator tuning or autonomous behavior inferred from old-loop evidence.','Both fixtures retain ideal bias/supplies and seeded initial state; RF pad and ADC interface remain incomplete.'])
(P/'evidence/rf-loop-boundary.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'])
