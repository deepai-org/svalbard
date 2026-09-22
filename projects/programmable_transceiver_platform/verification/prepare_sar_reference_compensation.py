"""Bracket reference compensation with actual SAR loading, fixed sample rate."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=P/'evidence/sar-driver-physical.json';report=json.loads(e.read_text())
assert report['completed']
case=next(c for c in report['cases'] if c['name']=='sar-driver-physical-400')
b=R/'scratch/transceiver-sar-driver-physical-400-prepared'
assert sha(b/'manifest.json')==case['preparation_sha256']
s=(b/'baseline.spice').read_text()
m=json.loads((b/'manifest.json').read_text());assert sha(b/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
pair=P/'analog/reference/adc_reference_pair.spice'
cell=pair.read_text().rstrip()
assert cell.count(' S=4')==2
include='.include /screen/reference/adc_reference_pair.spice'
assert s.count(include)==1
for label,value in [('half','0.5p'),('double','2p')]:
 changed=cell.replace(' S=4',' S=4 CC='+value)
 assert changed.replace(' CC='+value,'')==cell
 candidate=s.replace(include,changed)
 assert candidate.replace(changed,include)==s
 out=R/('scratch/transceiver-sar-reference-cc-'+label+'-prepared');out.mkdir()
 (out/'baseline.spice').write_text(candidate)
 manifest=dict(candidate='Both reference compensation capacitors '+label+'; original reservoir and 2k sample driver.',
  compensation_parameter=value,actual_capacitance_per_driver_pf=2 if label=='half' else 8,
  baseline_preparation_sha256=sha(b/'manifest.json'),source_evidence_sha256=sha(e),
  pair_source_sha256=sha(pair),artifacts_sha256={'baseline.spice':sha(out/'baseline.spice')},
  qualification_plan=['Require terminal clean completion and source/artifact hashes.',
   'Reverse only the two CC overrides and inlining to recover exact baseline.',
   'Compare all24 decisions and three final codes against physical77/179/76 and source ideal76/179/76.',
   'Examine per-decision rail recovery and acquisition; peak excursion alone cannot qualify.',
   'Any promising direction requires matched small-input testing before adoption.'],
  limitations=['Compensation capacitors are ideal schematic passives pending physical implementation.',
   'Ideal target/bias and phase controls; nominal supply/process/temperature only.',
   'No autonomous sample-rate, linearity, noise, mismatch or loop-stability qualification.'])
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(out)
