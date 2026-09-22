"""Hypothetical bounded resistor errors; these are not PDK matching guarantees."""
import itertools,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]
def alpha(top,bottom):return bottom/(top+bottom)
assert alpha(10000,30000)==.75
rows=[]
for error in (.001,.005,.01,.05):
 outputs=[]
 for corners in itertools.product((-error,error),repeat=4):
  it,ib,ft,fb=corners
  outputs.append(2.15*alpha(10000*(1+it),30000*(1+ib))/alpha(10000*(1+ft),30000*(1+fb)))
 rows.append(dict(independent_resistor_fractional_bound=error,output_min_v=min(outputs),output_max_v=max(outputs),worst_target_error_v=max(abs(v-2.15) for v in outputs)))
# Common scaling of all resistors leaves both ratios unchanged.
for scale in (.5,1,2):assert alpha(10000*scale,30000*scale)==.75
loading=[dict(target_source_resistance_ohm=r,ideal_output_v=2.15*40000/(40000+r),target_error_v=2.15*r/(40000+r)) for r in (0,10,100,1000,10000)]
assert loading[0]['target_error_v']==0
# Solve E=V*Rs/(Rdivider+Rs) independently for a stated1mV allowance.
source_limit=40000*.001/(2.15-.001)
assert abs(2.15*source_limit/(40000+source_limit)-.001)<1e-15
out=dict(target_loading_cases=loading,target_source_resistance_for_1mv_error_ohm=source_limit,status='ideal_ratio_sensitivity_only',cases=rows,nominal_divider_current_a=2.15/40000,nominal_feedback_factor=.75,limitations=['Independent symmetric hypothetical bounds, not established fab mismatch limits.','Infinite amplifier gain; ratio sweep uses ideal target, loading sweep uses specified DC Thevenin resistance. No noise, parasitics or input currents.','Common-centroid layout can improve correlation but has not been designed or quantified.','Calibration is not implemented and cannot be assumed to remove dynamic errors.'])
(P/'evidence/reference-divider-sensitivity.json').write_text(json.dumps(out,indent=2)+'\n')
for r in rows:print(r)
print('Source resistance for1mV error',source_limit,'ohm')
