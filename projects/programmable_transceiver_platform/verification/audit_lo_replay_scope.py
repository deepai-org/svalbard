"""Post-observation, narrowly scoped replay-use decision, not qualification."""
import hashlib
import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]
E=P/'evidence/lo-receiver-replay.json'
e=json.loads(E.read_text())
assert e['completed'] and not e['errors']
nodes=e['nodes']; outputs=[nodes[f'v(o{x})'] for x in ('ip','in','qp','qn')]
assert all(n['replay_rises']==n['parent_rises'] for n in outputs)
assert all(n['ordinal_max_displacement_ps'] is not None for n in outputs)
max_edge=max(n['ordinal_max_displacement_ps'] for n in outputs)
max_output=max(n['max_abs_difference_v'] for n in outputs)
max_input=max(nodes[f'v(b{x})']['max_abs_difference_v'] for x in ('ip','in','qp','qn'))
# Explicit post-observation guardrails for reproducing multi-cycle failures only.
# These are not system specifications and do not retroactively qualify a circuit.
within_scope=max_edge<1.0 and max_output<0.003 and max_input<0.00005
out=dict(completed=True,scope_use_approved=within_scope,
 upstream_sha256=hashlib.sha256(E.read_bytes()).hexdigest(),
 criteria_origin='Post-observation diagnostic scope; not predeclared design acceptance limits.',
 observations=dict(max_edge_displacement_ps=max_edge,max_output_difference_v=max_output,max_buffer_input_difference_v=max_input,all_output_rising_counts_equal=True),
 guardrails=dict(max_edge_displacement_ps=1.0,max_output_difference_v=0.003,max_buffer_input_difference_v=0.00005),
 rationale='Sub-picosecond edge disagreement and millivolt output disagreement are small relative to observed multi-cycle gaps exceeding800ps. Identical counts and ordinal matching support reproducing that severe output symptom, not all internal dynamics.',
 allowed=['Locate candidate mechanisms for the reproduced multi-cycle LO output failure.', 'Compare candidate circuits against this exact replay baseline as a screening experiment.'],
 excluded=['Direct validation of MID/PRE: parent did not record these nodes.', 'All-node identity: LNA gate difference reaches1.431mV.', 'Noise, phase noise, startup, autonomous feedback/loading or receiver sensitivity qualification.', 'Acceptance of a repair without restoring the autonomous connected simulation.'],
 original_unqualified_reproduction_flag=e['diagnostic_use_approved'])
(P/'evidence/lo-replay-scope.json').write_text(json.dumps(out,indent=2)+'\n')
print('scoped diagnostic use:',within_scope)
