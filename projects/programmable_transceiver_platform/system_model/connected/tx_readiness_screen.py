"""Read-only calibration readiness timeline at the failed managed mode0 start."""
import copy,json
from chip_model import P
from managed_tx_quality import ManagedTxHostChip
from managed_resources import command
from calibration_wideband_screen import prepared,PROFILE
from wideband_clock_quality import simulate

class Finished(Exception):pass
rows=[]
def snapshot(c,label):
    rows.append(dict(label=label,time_s=c.time,quiet=c.quiet(),reference=c.reference,
        coarse_qualified=c.coarse.qualified,pll_locked=c.rf_pll.locked,good=c.rf_pll.good,
        queue=len(c.tx.queue),state=c.state,frequency_hz=c.rf_pll.frequency_hz))
class Traced(ManagedTxHostChip):
    def execute_management(self,operation,payload,time):
        if operation=='tx_cal_start':snapshot(self,'start execution')
        return super().execute_management(operation,payload,time)
def observe(c):
    snapshot(c,'after retarget')
    result=command(c,'tx_cal_start')
    snapshot(c,'start reply')
    origin=c.time
    for i in range(1,41):
        c.advance(origin+i*.5e-6);snapshot(c,'post reply')
    (P/'evidence/connected-tx-readiness.json').write_text(json.dumps(dict(status='characterized',command=result,rows=rows,
        limitation='One mode0 noise/supply realization; snapshots are diagnostics, not a new readiness policy.'),indent=2)+'\n')
    print(result);print('first sampled lock',next((r for r in rows if r['pll_locked']),None))
    raise Finished()
def main():
    target=2412000000;exp=copy.deepcopy(PROFILE['experiment']);exp['source_count']=14000
    exp['source_offset_hz']+=target-2400000000
    try:
        simulate(0,True,chip_class=prepared(Traced,target,False,50e-6,before_mode=observe),
            blockers=[(a,f+target-2400000000) for a,f in PROFILE['blockers']],cubic=PROFILE['cubic'],
            chip_options=dict(rf_free_offset=-.08,coarse_noise_bound_hz=80000,rf_fast_fraction=.35,
                rf_pulse_bandwidth_hz=PROFILE['rf_pulse_bandwidth_hz'],**PROFILE['shared_reference'],**PROFILE['coupling']),experiment=exp)
    except Finished:pass
    else:raise AssertionError('Diagnostic never reached preparation boundary')
if __name__=='__main__':main()
