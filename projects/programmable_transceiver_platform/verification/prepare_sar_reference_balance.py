"""Instrument CDAC reference branches in a diagnostic copy; reproduction required."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
B=R/'scratch/transceiver-sar-bottom-plates-prepared';O=R/'scratch/transceiver-sar-reference-balance-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((B/'manifest.json').read_text());assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
s=(B/'baseline.spice').read_text();assert s.count('XD HP HN VH VL ')==1
senses='VSENSEH VH CDACH 0\nVSENSEL VL CDACL 0\n'
candidate=s.replace('XD HP HN VH VL ',senses+'XD HP HN CDACH CDACL ')
probes=['i(VSENSEH)','i(VSENSEL)','v(CDACH)','v(CDACL)','v(XREF.XHIGH.Z)','v(XREF.XLOW.Z)']
for rail in ('xhigh','xlow'):
    for dev in ('xout','xload'):
        for param in ('id','vds'):probes.append(f'@m.xref.{rail}.{dev}.m0[{param}]')
extra=' '+' '.join(probes)
line=next(l for l in candidate.splitlines() if l.startswith('wrdata '));candidate=candidate.replace(line,line+extra)
assert candidate.count('tran 5p 209.9n 0 5p')==1
candidate=candidate.replace('tran 5p 209.9n 0 5p','save all'+extra+'\ntran 5p 209.9n 0 5p')
reverse=candidate.replace('save all'+extra+'\n','').replace(line+extra,line).replace(senses,'').replace('XD HP HN CDACH CDACL ','XD HP HN VH VL ')
assert reverse==s
O.mkdir();(O/'baseline.spice').write_text(candidate)
m.update(candidate='CDAC rail current sense plus compensation/output probes; diagnostic only.',
    baseline_preparation_sha256=sha(B/'manifest.json'),artifacts_sha256={'baseline.spice':sha(O/'baseline.spice')},probes=probes,
    reproduction=dict(window_ns=[70,209],analog_maximum_error_v=1e-5,all_decisions_match=True),
    qualification_plan=['Require clean full transient and exact edit reversal.','Require waveform/decision reproduction before current attribution.',
      'Sense-source positive current flows from reference rail into CDAC.'],
    limitations=['Zero-volt sources preserve ideal electrical connection but can perturb numerical behavior.','Device ID remains conduction-only; displacement may remain in KCL residual.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
