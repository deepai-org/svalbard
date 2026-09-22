"""Compare completed cycle-local LO diagnostics without claiming matched cohorts."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]
files={'baseline':'lo-gap-state-contiguous.json','doubled':'lo-second-stage-gap-state.json','halved':'lo-second-stage-half-gap-state.json'}
rows={};hashes={}
for variant,name in files.items():
    path=P/'evidence'/name
    d=json.loads(path.read_text());assert d['completed']
    hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    rows[variant]={}
    for leg,groups in d['legs'].items():
        rows[variant][leg]={}
        for group,data in groups.items():
            nodes={}
            for node,x in data['nodes'].items():
                nodes[node]=dict(mean_cycle_peak_to_peak_v=x['mean'][1]-x['mean'][0],
                                 cycle_mean_min_v=x['min'][2],cycle_mean_max_v=x['max'][2],
                                 cycle_mean_range_v=x['max'][2]-x['min'][2])
            rows[variant][leg][group]=dict(cycles=data['cycles'],nodes=nodes)
report=dict(status='diagnostic_comparison_only',sources_sha256=hashes,variants=rows,
            limitations=['Gap membership differs between variants; these are not matched cycle cohorts.',
                         'Cycle mean movement is observed, not proof of feedback instability.',
                         'No supply-current evidence, startup, process spread or autonomous-loop validation.'],
            next_experiment='Test self-bias feedback resistance in both directions around 100kohm with original transistor sizes; preserve baseline and loaded replay scope. Check attenuation as well as bias drift, output edges and baseband disturbance.')
(P/'evidence/lo-gap-variant-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
print('Compared three completed variants; no candidate accepted')
