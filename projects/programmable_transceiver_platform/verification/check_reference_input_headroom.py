#!/usr/bin/env python3
"""Verify DC matrix and extract headroom, regulation and current tradeoffs."""
import hashlib,itertools,json,sys
TAIL="--tail" in sys.argv
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-reference-tail-headroom' if TAIL else 'scratch/transceiver-reference-input-headroom')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text())
assert m.get('tail_mode',False)==TAIL
assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
assert sorted((c['width_factor'],c['target_v'],c['load_a']) for c in r['cases'])==sorted(itertools.product([1,2,4],[2,2.15,2.3],[-.002,0,.002]))
rows=[]
for c in r['cases']:
 assert c['returncode']==0
 if TAIL:
  factor=c['width_factor'];target=c['target_v'];load=c['load_a']
  prior=R/'scratch/transceiver-reference-input-headroom'
  oldname=f'w4_v{target:g}_i{load:g}'
  old=json.loads((prior/'result.json').read_text())
  oldcase=next(x for x in old['cases'] if x['name']==oldname)
  assert sha(prior/(oldname+'.spice'))==oldcase['artifacts_sha256']['.spice']
  expected=(prior/(oldname+'.spice')).read_text().replace('/work/'+oldname+'.dat','/work/'+c['name']+'.dat')
  if factor!=1:
   expected=expected.replace('XT T BP VDD VDD pfet_03v3 w=8u l=.5u m={16*S}',f'XT T BPT VDD VDD pfet_03v3 w=8u l=.5u m={{{16*factor}*S}}')
   expected=expected.replace('RC X Z',f'IBPT BPT VSS 20u\nXBPT BPT BPT VDD VDD pfet_03v3 w=8u l=.5u m={factor}\nRC X Z')
  assert (W/(c['name']+'.spice')).read_text()==expected
  if factor==1:
   assert sha(W/(c['name']+'.dat'))==oldcase['artifacts_sha256']['.dat']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(c['name']+ext))==h
 assert c['deck_sha256_before']==c['artifacts_sha256']['.spice']
 with (W/(c['name']+'.dat')).open() as f:assert f.readline().lower().split()[1:]==[p.lower() for p in m['probes']]
 a=np.loadtxt(W/(c['name']+'.dat'),skiprows=1);assert a.shape==(len(m['probes'])+1,) and np.isfinite(a).all()
 v=dict(zip(m['probes'],map(float,a[1:])));assert v==c['values']
 rows.append(dict(width_factor=c['width_factor'],target_v=c['target_v'],load_a=c['load_a'],error_v=v['v(OUT)']-c['target_v'],supply_current_a=-v['i(VDD)'],tail_current_a=v['@m.xbuf.xt.m0[id]'],tail_margin_v=v['@m.xbuf.xt.m0[vds]']-v['@m.xbuf.xt.m0[vdsat]']))
out=dict(completed=True,tail_mode=TAIL,factor_meaning='tail and dedicated bias diode multiplicity at input width4' if TAIL else 'input width',cases=rows,raw_result_sha256=sha(W/'result.json'),limitations=['DC only; no settling, stability, noise, mismatch or process qualification.','Ideal target, supply and 20uA bias sources; load/target scenarios are not guaranteed bounds.'])
(P/('evidence/reference-tail-headroom.json' if TAIL else 'evidence/reference-input-headroom.json')).write_text(json.dumps(out,indent=2)+'\n')
for factor in (1,2,4):
 group=[x for x in rows if x['width_factor']==factor];nom=next(x for x in group if x['target_v']==2.15 and x['load_a']==0)
 print(factor,'nominal',nom,'minimum margin',min(x['tail_margin_v'] for x in group),'max error',max(abs(x['error_v']) for x in group))
