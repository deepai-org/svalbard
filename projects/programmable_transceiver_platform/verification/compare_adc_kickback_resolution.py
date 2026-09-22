"""Compare 2ps/1ps charge diagnostics; report convergence, not ADC acceptance."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]
paths=[P/'evidence'/f'adc-kickback{suffix}-excursion.json' for suffix in ['', '-fine']]
a,b=[json.loads(p.read_text()) for p in paths]
assert a['status']==b['status']=='clamped_charge_controls_pass'
rows=[]
for x,y in zip(a['results'],b['results'],strict=True):
 assert x['differential_v']==y['differential_v']
 row=dict(differential_v=x['differential_v'])
 for key in ['net_differential_charge_c','maximum_absolute_cumulative_charge_c']:
  row[key]=dict(coarse=x[key],fine=y[key],absolute_change_c=abs(y[key]-x[key]))
 rows.append(row)
report=dict(status='two_resolution_comparison',sources_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},results=rows,limitations=['Only two timestep settings; not an asymptotic convergence proof.', 'Tiny signed net charges require absolute comparisons, not misleading relative percentages.', 'Clamped-input diagnostic remains distinct from floating ADC behavior.'])
(P/'evidence/adc-kickback-resolution.json').write_text(json.dumps(report,indent=2)+'\n')
print('largest charge change fC',max(v['absolute_change_c'] for r in rows for v in [r['net_differential_charge_c'],r['maximum_absolute_cumulative_charge_c']])*1e15)
