"""Remove ideal rail clamps for two damping candidates and missing small-input control."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for name,source,amplitude in [('sar-driver-physical-400','sar-driver-damping-400',.4),('sar-driver-physical-100','sar-driver-damping-100',.1),('sar-physical-control-100','sar-amplitude-bank1',.1)]:
 B=R/('scratch/transceiver-'+source+'-prepared');O=R/('scratch/transceiver-'+name+'-prepared');m=json.loads((B/'manifest.json').read_text());assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
 s=(B/'baseline.spice').read_text();clamps='VCLH VH 0 2.15\nVCLL VL 0 1.15\n';assert s.count(clamps)==1;candidate=s.replace(clamps,'');assert candidate.replace('.control',clamps+'.control')==s
 O.mkdir();(O/'baseline.spice').write_text(candidate)
 m.update(candidate='Physical references restored by removing only ideal VH/VL clamps.',amplitude_v=amplitude,clamped_source=source,baseline_preparation_sha256=sha(B/'manifest.json'),artifacts_sha256={'baseline.spice':sha(O/'baseline.spice')},qualification_plan=['Verify exact removal of rail clamps.','Compare physical-reference baseline versus damped driver at each amplitude.','Check24 decisions, code error, acquisition and reference motion before adoption.'],limitations=['Reference targets/bias and phase controls remain ideal.','Only two amplitudes and nominal process; no INL/DNL,noise or mismatch qualification.','Existing reference error is not excused by a better sampling driver.'])
 (O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
