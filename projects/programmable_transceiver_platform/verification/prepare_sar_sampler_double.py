"""Double sampler fingers at original acquisition timing, ideal rails diagnostic."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-sar-reference-clamped-prepared';O=R/'scratch/transceiver-sar-sampler-double-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((B/'manifest.json').read_text());assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
s=(B/'baseline.spice').read_text();needle='XS IP IN HP HN SC SCB VDD 0 wifi_if_transmission_gate\n';assert s.count(needle)==1
extra=needle.replace('XS ','XS_EXTRA ',1);candidate=s.replace(needle,needle+extra);assert candidate.replace(extra,'')==s
O.mkdir();(O/'baseline.spice').write_text(candidate)
e=P/'evidence/sar-reference-clamped.json';assert json.loads(e.read_text())['clamps_verified']
m.update(candidate='Two parallel identical physical sampler banks instead of one; ideal rails and original209.9ns timing retained.',baseline_preparation_sha256=sha(B/'manifest.json'),baseline_evidence_sha256=sha(e),artifacts_sha256={'baseline.spice':sha(O/'baseline.spice')},qualification_plan=['Verify exact one-instance addition and terminal source integrity.','Compare pre-edge tracking, post-edge held error and all three final codes against clamped baseline.','Reject a settling-only gain if switching disturbance or accuracy worsens.'],limitations=['Ideal sampling controls hide extra clock-drive power and edge degradation.','Extra gate/diffusion capacitance, injection, noise and physical clock distribution need qualification.','Ideal reference rails; promising result requires restored physical regulation before adoption.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
