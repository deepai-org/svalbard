#!/usr/bin/env python3
"""Prepare controlled autonomous-loop pump substitution; do not simulate/adopt."""
import hashlib,json,re
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
B=R/'scratch/transceiver-closed-loop-buffered';F=R/'scratch/transceiver-pump-follower';O=R/'scratch/transceiver-closed-loop-follower-prepared';O.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for path,name in ((B,'closed'),(F,'follower')):
 result=json.loads((path/'result.json').read_text());assert sha(path/(name+'.spice'))==result['artifacts_sha256']['.spice']
 assert result['source_sha256_before']==result['source_sha256_after']
 # Historical loop failure is an intentional baseline, not a passing run.
 if path==F:assert result['returncode']==0 and not result['timed_out']
base=(B/'closed.spice').read_text();follower=(F/'follower.spice').read_text()
pump=re.search(r'^\.subckt pt_charge_pump .*?^\.ends pt_charge_pump\n',follower,re.M|re.S).group()
start=follower.index('.include /screen/reference/buffer_scaled.spice')
end=follower.index('.control',start)
driver=follower[start:end]
assert 'VCLAMP' not in driver and 'VFB' not in driver
old='.include /screen/pll/charge_pump.spice\n';assert base.count(old)==1
d=base.replace(old,pump)
oldx='XCP UP DN PUMP BPCP BNCP VDIV 0 pt_charge_pump';newx='XCP UP DN PUMP BPCP BNCP VDIV 0 DUMMY pt_charge_pump'
assert d.count(oldx)==1;d=d.replace(oldx,newx).replace('.control',driver+'.control')
extra=' v(DUMMY) i(VDRV) i(VDUMMY) v(BDN) v(BDP) v(XBUF.X) v(XBUF.T) i(v.xcp.vp) i(v.xcp.vn)'
d='\n'.join(line+extra if line.startswith(('save ','wrdata ')) else line for line in d.split('\n'))
# Exact reversal proves the existing feedback/RF circuit and solver history stay.
rev='\n'.join(line.removesuffix(extra) if line.startswith(('save ','wrdata ')) else line for line in d.split('\n'))
rev=rev.replace(driver,'').replace(newx,oldx).replace(pump,old)
assert rev==base
assert not re.search(r'^V(?:FB|CLAMP)\s',d,re.M)
assert 'XFB FBG FB VDIV 0 pt_lo_buffer S=1' in d
assert 'XPFD REF FB RN UP DN VDIV 0 pt_pfd' in d
assert 'XBUF CTRL DDRIVE BDN BDP VDRV 0 pt_reference_buffer_scaled S=0.0625' in d
assert 'tran 2p 3201n 0 2p uic' in d
(O/'closed.spice').write_text(d)
manifest=dict(status='prepared_not_simulated',baseline_loop_sha256=sha(B/'closed.spice'),follower_fixture_sha256=sha(F/'follower.spice'),prepared_deck_sha256=sha(O/'closed.spice'),exact_substitution_reversal_verified=True,limitations=['Retains older RF-load fixture to isolate pump change; not latest complete receiver.','Existing loop baseline aborted before horizon; no successful autonomous run inferred.','Seeded VCO/filter/reservoir, ideal bias currents/supplies/reference remain.','PDK/dependency hashes must be checked again by execution runner; preparation does not validate installed models.'])
(O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(P/'evidence/follower-loop-preparation.json').write_text(json.dumps(manifest,indent=2)+'\n');print(manifest['status'],manifest['exact_substitution_reversal_verified'])
