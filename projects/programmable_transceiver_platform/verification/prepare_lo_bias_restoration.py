"""RF I-leg bias-restoration experiment with unchanged recorded ring input."""
import hashlib,json,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
B=R/'scratch/transceiver-lo-common-mode-recorded-prepared'
O=R/'scratch/transceiver-lo-bias-restoration-prepared'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
e=P/'evidence/lo-common-mode-reproduction.json';r=json.loads(e.read_text())
assert r['completed'] and r['reproduction_pass']
m=json.loads((B/'manifest.json').read_text())
for name,h in m['artifacts_sha256'].items():assert sha(B/name)==h
source=(B/'replay.spice').read_text();candidate=source
changes={'RFBIP BIP XBIP.MID 100k':'RFBIP BIP XBIP.MID 10k',
         'RFBIN BIN XBIN.MID 100k':'RFBIN BIN XBIN.MID 10k'}
for old,new in changes.items():
 assert candidate.count(old)==1;candidate=candidate.replace(old,new)
reverse=candidate
for old,new in changes.items():reverse=reverse.replace(new,old)
assert reverse==source
O.mkdir();(O/'replay.spice').write_text(candidate)
shutil.copyfile(B/'ring_pwl.spice',O/'ring_pwl.spice')
m.update(candidate='Tenfold stronger existing I-leg AC-coupled bias restoration.',
 parent_preparation_sha256=sha(B/'manifest.json'),reproduction_report_sha256=sha(e),
 parent_waveform_sha256=r['waveform_hashes']['recorded'],changes=changes,
 artifacts_sha256={p.name:sha(p) for p in O.iterdir()},
 hypothesis='Lower I-leg self-bias resistance may reject slow common-mode movement while passing GHz carrier; feedback dynamics and loading can also degrade performance.',
 qualification_plan=['Require full terminal/source/artifact checks and exact two-resistor edit reversal.',
 'Compare all four legs with recorded baseline over800–1000ns using existing amplitude/duty/boundary-gap diagnostics.',
 'Retain unchanged actual recorded P/N input; do not replace common mode with an ideal source.',
 'A favorable replay still requires a separately prepared autonomous run with PLL feedback untouched.'],
 limitations=['10k resistors are lumped diagnostic elements; physical resistor parasitics/variation remain unqualified.',
 'No new bias supply or ideal common-mode cancellation is introduced.',
 'Recorded ring sources hide reverse loading on the oscillator; this test cannot qualify autonomous operation.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
