"""Declare a schedule-wide10ps UPDATE-fall separation; circuit remains actual-loaded."""
import hashlib,json,re
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-rx-adc-loading/loaded';O=R/'scratch/transceiver-rx-adc-separated-events-prepared-v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
e=P/'evidence/rx-adc-event-offsets.json';audit=json.loads(e.read_text());assert audit['matrix_terminal'] and not audit['completed']
for case in audit['cases']:
 assert abs(case['actual_stop_ns']-528.5)<1e-6 and max(case['pre_event_max_errors_v'].values())==0
 root=R/'scratch/transceiver-rx-adc-event-offsets'/case['case']
 for ext,h in case['artifacts_sha256'].items():assert sha(root/('connected'+ext))==h
original=(B/'connected.spice').read_text()
line=lambda prefix:next(x for x in original.splitlines() if x.startswith(prefix+' '))
old=line('VUPDATE');clock=next(x for x in original.splitlines() if x.startswith('VC CLK 0 PWL('))
def tokens(s):return re.search(r'PWL\(([^)]*)\)',s)[1].split()
c=tokens(clock);u=tokens(old);changed=list(u)
clock_falls={float(c[i][:-1]) for i in range(2,len(c),2) if c[i+1]=='0' and c[i-1]=='3.3'}
changes=[]
for i in range(0,len(u)-2,2):
 start=float(u[i][:-1]);end=float(u[i+2][:-1])
 if u[i+1]=='3.3' and u[i+3]=='0' and start in clock_falls:
  assert start>=470 and abs(end-start-.1)<1e-9
  changed[i]=f'{start+.01:.2f}n';changed[i+2]=f'{end+.01:.2f}n'
  changes.append(dict(start_ns=start,end_ns=end,new_start_ns=start+.01,new_end_ns=end+.01))
assert len(changes)==24
new=old[:old.index('PWL(')]+'PWL('+' '.join(changed)+')'
d=original.replace(old,new);assert d.replace(new,old)==original
assert u[1::2]==changed[1::2] and all(float(changed[i][:-1])<float(changed[i+2][:-1]) for i in range(0,len(changed)-2,2))
O.mkdir();p=O/'separated.spice';p.write_text(d)
m=dict(parent_deck_sha256=sha(B/'connected.spice'),signed_evidence_sha256=sha(e),cases=[dict(case='separated',deck_sha256=sha(p),original_line=old,changed_line=new)],changes=changes,
 timing_effect='Only24 UPDATE falling ramps move+10ps; rise times and100ps ramp widths unchanged. High plateaus lengthen10ps; following low plateaus shorten10ps.',
 limitations=['One selected separation, not a robust timing bound or implemented clock generator.','No acquisition, sample release, comparator clock or circuit change.','Must complete610ns and audit analog/code behavior; simulation completion alone is not a repair.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
(P/'evidence/rx-adc-separated-event-preparation.json').write_text(json.dumps(m,indent=2)+'\n');print('Verified24 falling ramps; all other deck text unchanged.')
