"""Replace finite ideal reference feeds by actual FET driver pair, nominal MIM first."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');base=json.loads((B/'result.json').read_text());rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
extra='''.include /screen/reference/adc_reference_pair.spice
VREFSUP VREFSUP 0 3.3
IRBN VREFSUP RBN 20u
IRBP RBP 0 20u
XRBN RBN RBN 0 0 nfet_03v3 w=8u l=.5u
XRBP RBP RBP VREFSUP VREFSUP pfet_03v3 w=8u l=.5u
XREF HR LR VH VL RBN RBP VREFSUP 0 pt_adc_reference_pair
'''
for c in base['cases']:
 if c['corner']!='typical':continue
 name=c['name'];src=B/(name+'.spice');assert sha(src)==c['artifacts_sha256']['.spice'];d=src.read_text()
 assert 'RHR HR VH 10\nRLR LR VL 10\n' in d
 d=d.replace('RHR HR VH 10\nRLR LR VL 10\n',extra)
 d=d.replace('v(VH) v(VL)\n','v(VH) v(VL) i(VREFSUP) v(XREF.XHIGH.X) v(XREF.XLOW.X)\n')
 (O/(name+'.spice')).write_text(d)
 with (O/(name+'.log')).open('w') as log:r=subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,timeout=1800)
 rows.append(dict(name=name,corner=c['corner'],first_sign=c['first_sign'],returncode=r.returncode,baseline_deck_sha256=sha(src),artifacts_sha256={s:sha(O/(name+s)) for s in ('.spice','.dat','.log') if (O/(name+s)).exists()}));print(name,r.returncode,flush=True)
source=base['source_sha256'].copy()
for name in ('buffer_scaled.spice','buffer_complement.spice','adc_reference_pair.spice'):
 p=Path('/screen/reference')/name;source[str(p)]=sha(p)
(O/'result.json').write_text(json.dumps(dict(status='connected_reference_driver_candidate_unverified',cases=rows,source_sha256=source,limitations=['Actual reference output drivers; ideal target voltages and bias currents remain.', '10pF reservoirs and driver compensation remain ideal.', 'Nominal MIM only, two selected streams; no transfer/noise/mismatch/startup/loop-stability qualification.', 'Separate ideal reference supply omits full-chip supply coupling.']),indent=2)+'\n')
