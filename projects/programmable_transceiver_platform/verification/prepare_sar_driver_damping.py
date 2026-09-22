"""Transfer an earlier driver damping hypothesis into intact two-amplitude SAR."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
cell=(P/'analog/adc/sample_driver_headroom.spice').read_text();assert cell.count('RC X Z 100')==1;changed=cell.replace('RC X Z 100','RC X Z 2k').rstrip();needle='.include /screen/adc/sample_driver_headroom.spice'
for label,amplitude,source in [('400',.4,'sar-reference-clamped'),('100',.1,'sar-amplitude-bank1')]:
 B=R/('scratch/transceiver-'+source+'-prepared');O=R/('scratch/transceiver-sar-driver-damping-'+label+'-prepared');m=json.loads((B/'manifest.json').read_text());assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
 s=(B/'baseline.spice').read_text();assert s.count(needle)==1;candidate=s.replace(needle,changed);assert candidate.replace(changed,needle)==s
 O.mkdir();(O/'baseline.spice').write_text(candidate)
 m.update(candidate='Only sample-driver compensation series resistor100ohm to2k; original transistor sizes,0.5p compensation, sampler and timing.',amplitude_v=amplitude,comparison_source=source,baseline_preparation_sha256=sha(B/'manifest.json'),artifacts_sha256={'baseline.spice':sha(O/'baseline.spice')},qualification_plan=['Compare matched full conversion at both amplitudes.','Score driver/held errors before and after sampling, all comparisons and final code error.'],limitations=['Prior reduced driver evidence had different common mode and omitted controller/comparator loading.','Ideal reference rails and sampling controls; no physical clock or reference qualification.','No adoption from selected correct codes alone.'])
 (O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
