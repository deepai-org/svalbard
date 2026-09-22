"""Diagnostic full terminal currents, preserving MOS wrapper internals."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
B=R/'scratch/transceiver-sar-balance-second-instrumented-prepared'
W=R/'scratch/transceiver-sar-balance-second-instrumented'
O=R/'scratch/transceiver-reference-terminal-probe-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=json.loads((P/'evidence/sar-balance-second-refinement.json').read_text())
assert e['completed'] and e['comparisons']['second_pair']['within_10uv_and_decisions']
r=json.loads((W/'result.json').read_text())
assert r['returncode']==0 and not r['timed_out'] and r['sources_before']==r['sources_after']
assert sha(W/'baseline.dat')==e['waveform_hashes']['instrumented']
m=json.loads((B/'manifest.json').read_text())
assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
O.mkdir();originals={};edits={}
for name in ('buffer_scaled.spice','buffer_complement.spice'):
 p=P/'analog/reference'/name;s=p.read_text()
 assert sha(p)==r['sources_before']['/screen/reference/'+name]
 changes={'XIP A OUT T ':'XIP A SENSEG T ', 'XOUT OUT X ':'XOUT SENSED X ', 'XLOAD OUT ':'XLOAD SENSEL '}
 candidate=s
 for old,new in changes.items():
  assert candidate.count(old)==1;candidate=candidate.replace(old,new)
 added='VGATE OUT SENSEG 0\nVDRAIN OUT SENSED 0\nVLOAD OUT SENSEL 0\n'
 candidate=candidate.replace('.ends',added+'.ends')
 reverse=candidate.replace(added,'')
 for old,new in changes.items():reverse=reverse.replace(new,old)
 assert reverse==s
 (O/name).write_text(candidate);originals[name]=sha(p)
 edits[name]=dict(replacements=changes,added=added)
pair=P/'analog/reference/adc_reference_pair.spice'
assert sha(pair)==r['sources_before']['/screen/reference/adc_reference_pair.spice']
(O/'adc_reference_pair.spice').write_text(pair.read_text().replace('/screen/reference/','/prepared/'))
source=(B/'baseline.spice').read_text()
candidate=source.replace('.include /screen/reference/adc_reference_pair.spice','.include /prepared/adc_reference_pair.spice')
probes=[f'i(v.xref.{rail}.{device})' for rail in ('xhigh','xlow') for device in ('vgate','vdrain','vload')]
extra=' '+' '.join(probes)
line=next(l for l in candidate.splitlines() if l.startswith('wrdata '))
candidate=candidate.replace(line,line+extra)
save=next(l for l in candidate.splitlines() if l.startswith('save all'))
candidate=candidate.replace(save,save+extra)
reverse=candidate.replace(line+extra,line).replace(save+extra,save).replace('.include /prepared/adc_reference_pair.spice','.include /screen/reference/adc_reference_pair.spice')
assert reverse==source
(O/'baseline.spice').write_text(candidate)
m.update(candidate='Full terminal currents for input feedback gate and output drain wrappers.',
 parent_preparation_sha256=sha(B/'manifest.json'),parent_result_sha256=sha(W/'result.json'),
 parent_waveform_sha256=sha(W/'baseline.dat'),original_buffer_hashes=originals,buffer_edits=edits,
 probes=probes,artifacts_sha256={p.name:sha(p) for p in O.iterdir()},
 reproduction=dict(window_ns=[70,209],analog_maximum_error_v=1e-5,all_decisions_match=True),
 qualification_plan=['Require exact edit reversal, clean209.9ns transient and unchanged source hashes.',
 'Require unchanged10uV waveform reproduction and24 matching full-swing decisions before current attribution.',
 'Positive terminal-sense current flows outward from rail into device wrapper.',
 'Subtract terminal currents, compensation and reservoir consistently; full terminal current already contains conduction.'],
 limitations=['Zero-volt probes preserve ideal connections but may perturb numerical behavior.','Diagnostic copies only; production buffer files are unchanged.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
