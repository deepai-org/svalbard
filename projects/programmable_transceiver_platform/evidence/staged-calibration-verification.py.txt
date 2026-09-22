"""Independent residual-observation contract; no access to plant truth."""
import math

def assess(*,done,range_limited,observation_v,error_bound_v,tolerance_v,quiet,epoch,observation_epoch):
    if not math.isfinite(tolerance_v) or tolerance_v<=0:
        raise ValueError('Invalid accuracy tolerance')
    result=dict(done=bool(done),range_limited=bool(range_limited),accuracy='unverified',valid=False)
    if not done or not quiet or epoch!=observation_epoch:
        result['reason']='incomplete, not quiet, or stale observation';return result
    if range_limited:
        result.update(accuracy='failed',reason='trim range exhausted');return result
    if error_bound_v is None or observation_v is None:
        result['reason']='missing independent observation or error bound';return result
    if not math.isfinite(error_bound_v) or error_bound_v<0 or not math.isfinite(observation_v):
        raise ValueError('Invalid observation uncertainty')
    low=observation_v-error_bound_v;high=observation_v+error_bound_v
    result['residual_interval_v']=[low,high]
    if low>=-tolerance_v and high<=tolerance_v:
        result.update(accuracy='verified',valid=True,reason='entire bounded residual interval meets tolerance')
    elif low>tolerance_v or high<-tolerance_v:
        result.update(accuracy='failed',reason='entire residual interval violates tolerance')
    else:
        result['reason']='uncertainty overlaps accuracy boundary'
    return result
