"""One-factor reservoir experiment using the exactly reproduced intact SAR fixture."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
B=R/'scratch/transceiver-sar-command-replay-prepared';O=R/'scratch/transceiver-sar-reservoir-double-prepared'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
e=P/'evidence/sar-command-baseline.json';evidence=json.loads(e.read_text())
assert evidence['completed'] and evidence['reproduction_pass']
m=json.loads((B/'manifest.json').read_text())
assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
s=(B/'baseline.spice').read_text();extra='XHR_EXTRA VH 0 pt_ref_reservoir_2048\nXLR_EXTRA VL 0 pt_ref_reservoir_2048\n'
needle='XLR VL 0 pt_ref_reservoir_2048\n';assert s.count(needle)==1
candidate=s.replace(needle,needle+extra);assert candidate.replace(extra,'')==s
O.mkdir();(O/'baseline.spice').write_text(candidate)
m.update(candidate='Double both 2048-unit reservoirs to 4096 units; no other circuit or timing changes.',baseline_preparation_sha256=sha(B/'manifest.json'),baseline_evidence_sha256=sha(e),artifacts_sha256={'baseline.spice':sha(O/'baseline.spice')},evaluation={'window_ns':[70,79],'decision_times_ns':[72.4,77.4],'metrics':['rail target errors','span error','held differential residue','comparator decisions'],'acceptance':'Diagnostic only; improvement must include decision correctness and area/power tradeoffs. No production adoption.'},limitations=['Only first two decisions of one frame are simulated.','Ideal external reference targets and bias remain.','Doubling reservoir MIM area may be unacceptable; do not infer chip-fit.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
