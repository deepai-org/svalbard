"""Compare terminal failure events without treating partial runs as conversions passed."""
import hashlib,json,re
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for name,folder in [('baseline','transceiver-rx-adc-loading/loaded'),('early','transceiver-rx-adc-event-offsets/early')]:
 root=R/'scratch'/folder;r=json.loads((root/'result.json').read_text())
 assert r['returncode']!=0 and not r['timed_out'] and r['sources_before']==r['sources_after']
 for ext,h in r['artifacts_sha256'].items():assert sha(root/('connected'+ext))==h
 log=(root/'connected.log').read_text();m=re.search(r'Timestep too small; time = ([\deE.+-]+).*?trouble with node "([^"]+)"',log);assert m
 ns=float(m[1])*1e9;events=[]
 for line in (root/'connected.spice').read_text().splitlines():
  if 'PWL(' not in line:continue
  tokens=re.search(r'PWL\(([^)]*)\)',line)[1].split();assert len(tokens)%2==0
  knots=[]
  for i in range(0,len(tokens),2):
   assert tokens[i].endswith('n');knots.append((float(tokens[i][:-1]),float(tokens[i+1])))
  for i,(time,voltage) in enumerate(knots):
   if abs(time-ns)<1e-7:
    events.append(dict(source=line.split()[0],time_ns=time,voltage_v=voltage,
      preceding_knot=knots[i-1] if i else None,following_knot=knots[i+1] if i+1<len(knots) else None))
 assert {e['source'] for e in events}=={'VC','VUPDATE'}
 clk=next(e for e in events if e['source']=='VC');update=next(e for e in events if e['source']=='VUPDATE')
 assert clk['preceding_knot'][1]==3.3 and clk['voltage_v']==0
 assert update['voltage_v']==3.3 and update['following_knot'][1]==0
 rows.append(dict(case=name,actual_failure_ns=ns,node=m[2],events=events,artifacts_sha256=r['artifacts_sha256']))
assert abs(rows[1]['actual_failure_ns']-rows[0]['actual_failure_ns']-50)<1e-7
out=dict(status='two_terminal_failures_at_repeated_clock_update_boundary',completed=False,cases=rows,
 interpretation='Shifting one UPDATE fall by -10ps allowed advancement to the same clock/update boundary in the next frame. Supports event sensitivity; no physical repair or root-cause proof.',
 next='Wait for existing +10ps run; if consistent, test a declared schedule-wide separation with unchanged circuit and quantify its timing effect.',
 limitations=['Earlier run remains failed; crossing first frame end does not verify code or acquisition accuracy.',
 'Same reported trouble node does not uniquely identify the cause.',
 'The isolated control already failed the original boundary, so receiver back-loading is not necessary for that failure.',
 'A global event change would alter real timing and needs a new schedule audit and connected comparison.'])
(P/'evidence/rx-adc-repeated-failure.json').write_text(json.dumps(out,indent=2)+'\n')
print([(r['case'],r['actual_failure_ns'],r['node']) for r in rows])
