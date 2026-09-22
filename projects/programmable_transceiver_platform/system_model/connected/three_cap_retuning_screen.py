"""Finite-time centering lifecycle, coarse-bank writes and fractional retarget continuity."""
import copy,json
import numpy as np
from chip_model import P
from three_cap_retuning_clock import ThreeCapRetuningClock

import argparse,time
parser=argparse.ArgumentParser()
parser.add_argument('--exact',action='store_true')
args=parser.parse_args()
started=time.perf_counter()
p=ThreeCapRetuningClock(reference_hz=40e6,divider=60,free_hz=2.4e9*.92)
if args.exact:
    from three_cap_exact_centering import ExactCenteringFilter
    from three_cap_retuning_clock import BALANCED_FILTER
    p.filter=ExactCenteringFilter(**BALANCED_FILTER)
p.filter.state[:3]=[.3,-.2,.1]
phase=p.output_phase_cycles;charge=p.integral
p.write_bank(0.,15,2e-6)
assert p.output_phase_cycles==phase and p.integral==charge
assert p.frequency_hz==2.4e9*.92+p.gains.kvco*.1
end=p.start_center(0.)
for action in (lambda:p.finish_center(end/2),lambda:p.set_reference(True,0.)):
    state=p.filter.state.copy()
    try:action()
    except ValueError:pass
    else:raise AssertionError('Invalid centering transition accepted')
    assert np.array_equal(state,p.filter.state)
# Cancellation must retain physical discharge accrued before the cancellation.
trial=copy.copy(p);trial.advance(100e-9)
p.cancel_center(100e-9)
np.testing.assert_allclose(p.filter.state,trial.filter.state,rtol=1e-12,atol=1e-24)
assert not p.coarse_initial_ready and not p.filter.center_enabled
end=p.start_center(p.time)
p.finish_center(end)
assert p.coarse_initial_ready and not p.filter.center_enabled
assert max(abs(p.filter.state[:3]))<=p.center_voltage_bound
phase=p.output_phase_cycles;charge=p.integral
p.retarget(p.time,2437000000)
assert p.output_phase_cycles==phase and p.integral==charge
p.set_reference(True,p.time)
p.advance(p.time+50e-9)
assert p.fault is None and not p.filter.center_enabled
report=dict(status='passed_local_retuning_lifecycle',time_s=p.time,final_nodes_v=p.filter.state[:3].tolist(),
    checks=['Coarse write preserves phase and all three charges; frequency settles continuously.',
        'Early finish and active pump during centering rejected.',
        'Cancel preserves accrued passive discharge; restart finishes below declared voltage bound.',
        'Fractional retarget preserves phase and charges; fine loop resumes.'],
    limitations=['No counted coarse acquisition or post-retune sustained-lock proof.',
        'No full-chip RF quality, rail-feedback or uncertainty qualification.'])
report['elapsed_s']=time.perf_counter()-started
if args.exact:
    baseline=json.loads((P/'evidence/three-cap-retuning-screen.json').read_text())
    np.testing.assert_allclose(report['final_nodes_v'],baseline['final_nodes_v'],rtol=1e-9,atol=1e-11)
    assert report['time_s']==baseline['time_s']
    report['reference_final_node_error_v']=float(max(abs(np.array(report['final_nodes_v'])-baseline['final_nodes_v'])))
output=P/('evidence/three-cap-exact-retuning-screen.json' if args.exact else 'evidence/three-cap-retuning-screen.json')
output.write_text(json.dumps(report,indent=2)+'\n')
print(report)
