#!/usr/bin/env python3
"""Independently parse source pairs; verify actual integration schedule."""
import hashlib,json,re
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
A=R/'scratch/transceiver-adc-reference-current/frames.spice';B=R/'scratch/transceiver-rx-adc-loading/loaded/connected.spice'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def parse(p):
 out={}
 for line in p.read_text().splitlines():
  if 'PWL(' not in line:continue
  name=line.split()[0];raw=re.search(r'PWL\(([^)]*)\)',line).group(1).split();assert len(raw)%2==0
  pairs=[]
  for k in range(0,len(raw),2):
   assert raw[k].endswith('n');pairs.append((float(raw[k][:-1]),float(raw[k+1])))
  assert all(y[0]>x[0] for x,y in zip(pairs,pairs[1:]))
  out[name]=pairs
 return out
old=parse(A);new=parse(B);expected={'VRST','VSTART','VUPDATE','VS','VSB','VC','VMASK'};assert set(new)==expected
for name in expected:
 assert len(new[name])==len(old[name])
 for (ot,ov),(nt,nv) in zip(old[name],new[name]):assert ov==nv and abs(nt-(ot+400 if ot else 0))<1e-10
assert [t for t,_ in new['VS']]==[t for t,_ in new['VSB']]
assert all(abs(x[1]+y[1]-3.3)<1e-12 for x,y in zip(new['VS'],new['VSB']))
def edges(name,rising):
 return [(a[0],b[0]) for a,b in zip(new[name],new[name][1:]) if (b[1]>a[1] if rising else b[1]<a[1])]
release=edges('VS',False);track=edges('VS',True);comparisons=edges('VC',True);resets=edges('VRST',True)
rows=[]
for i,(start,end) in enumerate(release):
 comp=[x for x in comparisons if start<x[0]<start+40]
 assert len(comp)==8 and abs(comp[0][0]-end-.4)<1e-10
 assert all(abs(b[0]-a[0]-5)<1e-10 for a,b in zip(comp,comp[1:]))
 acquire=0 if i==0 else track[i-1][1]
 rows.append(dict(hold_start_ns=start,switch_off_end_ns=end,track_start_end_ns=acquire,fully_on_track_ns=start-acquire,first_comparator_edge_ns=comp[0],release_to_compare_gap_ns=comp[0][0]-end,reset_release_before_hold_ns=max(x[1] for x in resets if x[1]<start)))
out=dict(parent_deck_sha256=sha(A),loaded_deck_sha256=sha(B),seven_source_shift_verified=True,complementary_sampler_verified=True,frames=rows,limitations=['Ideal source schedule only; actual FET clock arrival/skew and analog settling remain unverified.','First470ns tracking interval is startup; subsequent fully-on tracking is9.9ns, not470ns.','400ns pre-conversion allowance does not prove UIC bias settling.'])
(P/'evidence/rx-adc-schedule.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
