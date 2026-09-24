"""Actual-divider loop with reference buffer; preserve seeded failing baseline."""
import argparse,hashlib,json,re,subprocess
ap=argparse.ArgumentParser();ap.add_argument("--prepared",action="store_true");ap.add_argument("--preflight",action="store_true");ap.add_argument("--latest",action="store_true");args=ap.parse_args()
from pathlib import Path
O=Path('/work');B=Path('/baseline/latest.spice' if args.latest else '/baseline/closed.spice')
NAME='latest' if args.latest else 'closed'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
original=B.read_text()
if args.latest:
 preparation=json.loads(B.with_name('manifest.json').read_text())
 assert sha(B)==preparation['deck_sha256'] and preparation['receiver_exact_reversal']
 deck=original
elif args.prepared:
 preparation=json.loads(B.with_name('manifest.json').read_text())
 assert sha(B)==preparation['prepared_deck_sha256'] and preparation['exact_substitution_reversal_verified']
 deck=original
else:
 assert original.count('VREF REF 0 ')==1
 addition='.include /screen/pll/reference_input_buffer.spice\nXREFBUF REFRAW REF VDIV 0 pt_reference_input_buffer\n'
 deck=original.replace('VREF REF 0 ','VREF REFRAW 0 ').replace('.control',addition+'.control')
 assert deck.replace(addition,'').replace('VREF REFRAW 0 ','VREF REF 0 ')==original
# Enumerate actual include dependencies, including relative PDK includes.
paths={B,Path(__file__).with_name('spice_dependencies.py')}
from spice_dependencies import dependencies
dependencies(deck,B.parent,paths)
p=O/(NAME+'.spice');p.write_text(deck)
before={str(x):sha(x) for x in sorted(paths)}
manifest=dict(status='running',source_sha256_before=before,deck_sha256_before=sha(p),declared_change=('Latest bypassed I/Q receiver with actual autonomous feedback; prepared deck unchanged.' if args.latest else 'Prepared steering pump/follower/reservoir substitution; original autonomous feedback and solver history retained.' if args.prepared else 'Four-FET reference buffer only; original autonomous feedback and all simulation options retained.'),requested_horizon_ns=float(re.search(r"^tran \S+ ([0-9.]+)n",deck,re.M).group(1)),limitations=['Precharged filter, seeded VCO, prebiased LNA: not cold startup.', 'Ideal reference, bias and supply sources; no intrinsic jitter/noise qualification.'])
if (args.prepared or args.latest) and preparation.get('scope'):manifest['declared_change']=preparation['scope']
(O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if args.preflight:
 manifest['status']='dependencies_verified_not_simulated'
 (O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(manifest['status'],len(before),'dependencies');raise SystemExit(0)
with (O/(NAME+'.log')).open('w') as log:
 try:
  result=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=14400)
  code=result.returncode;timeout=False
 except subprocess.TimeoutExpired:
  code=None;timeout=True
after={str(x):sha(x) for x in sorted(paths)}
result=dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,deck_unchanged=sha(p)==manifest['deck_sha256_before'],artifacts_sha256={ext:sha(O/(NAME+ext)) for ext in ('.spice','.log','.dat') if (O/(NAME+ext)).exists()})
(O/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
assert before==after and result['deck_unchanged']
