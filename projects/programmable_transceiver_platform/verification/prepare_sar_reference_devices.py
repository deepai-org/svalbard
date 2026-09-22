"""Observation-only actual baseline SAR; save existing-device internal vectors."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';D=R/'scratch/transceiver-adc-sar8-reference-reservoir';O=R/'scratch/transceiver-sar-reference-devices-prepared'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
e=P/'evidence/adc-sar8-reference-reservoir-screen.json';case=next(c for c in json.loads(e.read_text())['cases'] if c['name']=='typical_first1')
for ext in ('.spice','.dat'):assert sha(D/('typical_first1'+ext))==case['artifacts_sha256'][ext]
contract=P/'evidence/device-probe-contract.json';assert json.loads(contract.read_text())['status']=='device_probe_conventions_verified_at_selected_DC_points'
s=(D/'typical_first1.spice').read_text()
probes=[f'v(XREF.{rail}.{node})' for rail in ('XHIGH','XLOW') for node in ('A','T','Z')]
probes += [f'@m.xref.{rail}.{dev}.m0[{param}]' for rail in ('xhigh','xlow') for dev in ('xin','xip','xt','xmp','xmn','xout','xload') for param in ('id','vds','vgs','vdsat')]
save='save all '+' '.join(probes)+'\n';tran='tran 5p 209.9n 0 5p';assert s.count(tran)==1
candidate=s.replace(tran,save+tran).replace('/work/typical_first1.dat','/work/baseline.dat');lines=candidate.splitlines();extra=' '+' '.join(probes);lines=[l+extra if l.startswith('wrdata ') else l for l in lines];candidate='\n'.join(lines)+'\n'
restored=candidate.replace(save,'');restored='\n'.join(l[:-len(extra)] if l.startswith('wrdata ') else l for l in restored.splitlines())+'\n';assert restored.replace('/work/baseline.dat','/work/typical_first1.dat')==s
O.mkdir();(O/'baseline.spice').write_text(candidate)
m=dict(candidate='Observation-only saves; unchanged original circuit and209.9ns timing.',probes=probes,probe_contract_sha256=sha(contract),donor_artifacts_sha256=case['artifacts_sha256'],artifacts_sha256={'baseline.spice':sha(O/'baseline.spice')},reproduction=dict(window_ns=[70,209],analog_nodes=['hp','hn','vh','vl'],max_error_v=10e-6,all_decisions_match=True),limitations=['Device ID is not complete terminal current including displacement.','Reporting convention validated at selected forward-conduction DC points only.','No headroom interpretation before waveform reproduction and time-vector checks pass.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O,len(probes),'extra probes')
