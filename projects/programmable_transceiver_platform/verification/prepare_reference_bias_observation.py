"""Expose previously saved reference bias nodes; no circuit/save-set changes."""
import hashlib,json,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
B=R/'scratch/transceiver-reference-terminal-probe-prepared'
W=R/'scratch/transceiver-reference-terminal-probe'
O=R/'scratch/transceiver-reference-bias-observation-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=P/'evidence/reference-terminal-probe.json';r=json.loads(e.read_text())
assert r['completed'] and r['reproduction_pass']
assert sha(W/'baseline.dat')==r['waveform_sha256']
m=json.loads((B/'manifest.json').read_text())
for name,h in m['artifacts_sha256'].items():assert sha(B/name)==h
s=(B/'baseline.spice').read_text()
assert any(l.startswith('save all') for l in s.splitlines())
line=next(l for l in s.splitlines() if l.startswith('wrdata '))
extra=' v(RBN) v(RBP)'
candidate=s.replace(line,line+extra)
assert candidate.replace(line+extra,line)==s
# Bias is current-fed through diode-connected devices, not a stiff voltage.
for fragment in ('IRBN VREFSUP RBN 20u','IRBP RBP 0 20u',
                 'XRBN RBN RBN 0 0','XRBP RBP RBP VREFSUP VREFSUP'):
 assert fragment in s
O.mkdir()
for name in m['artifacts_sha256']:
 if name!='baseline.spice':shutil.copyfile(B/name,O/name)
(O/'baseline.spice').write_text(candidate)
m.update(candidate='Output-only observation of current-fed shared bias nodes.',
 parent_preparation_sha256=sha(B/'manifest.json'),parent_result_sha256=sha(W/'result.json'),
 parent_waveform_sha256=r['waveform_sha256'],parent_reproduction_sha256=sha(e),
 appended_output_vectors=['v(RBN)','v(RBP)'],
 artifacts_sha256={p.name:sha(p) for p in O.iterdir()},
 qualification_plan=['Require clean full run, unchanged sources and exact wrdata-only reversal.',
 'Require exact equality of every preexisting waveform vector and time grid; no tolerance relaxation for output-only change.',
 'Measure gate motion before selecting a rail-only nonlinear charge law.'],
 limitations=['Current-fed diode bias can couple high/low rails through shared gates; motion is not yet measured.',
 'Output-only instrumentation does not provide independent stimulus validation.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
