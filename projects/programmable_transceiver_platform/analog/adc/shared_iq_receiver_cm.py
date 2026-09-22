"""Common-mode-only substitution in actual shared-reference dual ADC fixture."""
import argparse,hashlib,json,subprocess
ap=argparse.ArgumentParser();ap.add_argument("--early-input",action="store_true");ap.add_argument("--compensation",action="store_true");ap.add_argument("--fixed-references",action="store_true");ap.add_argument("--damping",action="store_true");ap.add_argument("--two-k",action="store_true");args=ap.parse_args()
if args.two_k:args.damping=True
assert sum((args.early_input,args.compensation,args.fixed_references,args.damping))<=1
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());assert r['returncode']==0 and not r['timed_out'];src=B/'frames.spice';assert sha(src)==r['artifacts_sha256']['.spice']
assert r['source_sha256_before']==r['source_sha256_after']
before={}
for path,h in r['source_sha256_before'].items():
 actual=Path('/screen/adc/shared_iq_receiver_cm_before_early.py') if (args.early_input or args.compensation or args.fixed_references or args.damping) and path==str(Path(__file__)) else Path(path)
 assert sha(actual)==h;before[str(actual)]=h
before[str(Path(__file__))]=sha(Path(__file__))
base=src.read_text();changes={}
for line in base.splitlines():
 if line.split(' ')[0] in ('VIP','VIN','VQ_IP','VQ_IN'):changes[line]=(line.replace('60n ','50n ').replace('60.1n ','50.1n ') if args.early_input else line.replace('1.85','1.27').replace('1.45','0.87'))
if args.compensation:
 changes={line:line.replace('CC=.5p','CC=1p') for line in base.splitlines() if 'pt_sample_driver_headroom CC=.5p' in line}
if args.fixed_references:
 old='XREF HR LR VH VL RBN RBP VREFSUP 0 pt_adc_reference_pair_tuned'
 changes={old:'XREF HR LR VHISO VLISO RBN RBP VREFSUP 0 pt_adc_reference_pair_tuned\nVFIXH VH 0 2.15\nVFIXL VL 0 1.15'}
if args.damping:
 cell=Path('/screen/adc/sample_driver_headroom.spice').read_text()
 assert cell.count('RC X Z 100')==1
 changes={'.include /screen/adc/sample_driver_headroom.spice':cell.replace('RC X Z 100','RC X Z 2k' if args.two_k else 'RC X Z 1k')}
assert len(changes)==(1 if args.fixed_references or args.damping else 4);d=base
for old,new in changes.items():assert d.count(old)==1;d=d.replace(old,new)
p=O/'frames.spice';p.write_text(d);h=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(baseline_deck_sha256=sha(src),source_sha256_before=before,changes=changes,deck_sha256_before=h,scope=('Only sample-driver compensation series resistor100ohm->2kohm; capacitor, devices, actual references and timing retained.' if args.two_k else 'Only sample-driver compensation series resistor100ohm->1kohm; capacitor, devices, actual references and timing retained.' if args.damping else 'Diagnostic ideal reference clamps; actual reference outputs isolated; sampler, drivers, CDAC and timing retained.' if args.fixed_references else 'Only four sample-driver compensation capacitors0.5pF->1pF; all timing and loads retained.' if args.compensation else 'Only first source transition advances60..60.1ns->50..50.1ns; sampling/conversion clocks unchanged.' if args.early_input else 'Four input-source common modes1.65->1.07V; differential swing remains+/-0.4V. Actual sample drivers/CDAC/control/shared reference retained, ideal source impedance/clocks remain.')),indent=2)+'\n')
with (O/'frames.log').open('w') as log:
 try:s=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=900);code=s.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={p:sha(Path(p)) for p in before};assert before==after and sha(p)==h
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={e:sha(O/('frames'+e)) for e in ('.spice','.log','.dat') if (O/('frames'+e)).exists()}),indent=2)+'\n');print(code,timeout)
