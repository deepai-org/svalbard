"""Change only RF frequency in the completed actual receiver/ADC fixture."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-rx-adc-separated-events-v2/separated';O=R/'scratch/transceiver-rx-adc-inband-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=P/'evidence/rx-adc-separated-events.json';audit=json.loads(e.read_text());assert audit['completed']
for ext,h in audit['cases'][0]['artifacts_sha256'].items():assert sha(B/('connected'+ext))==h
s=(B/'connected.spice').read_text();old='VRF RFS 0 SIN(0 0.001 2.51542263g)';new='VRF RFS 0 SIN(0 0.001 2.5004222935g)'
assert s.count(old)==1;d=s.replace(old,new);assert d.replace(new,old)==s
O.mkdir();q=O/'inband.spice';q.write_text(d)
(O/'manifest.json').write_text(json.dumps(dict(parent_deck_sha256=sha(B/'connected.spice'),parent_evidence_sha256=sha(e),cases=[dict(case='inband',deck_sha256=sha(q),original_line=old,changed_line=new)],question='Does actual connected acquisition follow changing approximately5MHz IF over successive50ns samples?',prediction='Approximately90degree IF advance per frame rather than near-repetition; measure actual source and held values.',limitations=['Three sub-LSB-scale frames do not establish ENOB or full-scale acquisition.','Seeded oscillator and ideal10ps-separated control schedule remain.','No gain or reference circuit change; no physical qualification threshold.']),indent=2)+'\n')
print(O)
