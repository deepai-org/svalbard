"""RF startup sensitivity and analytical tuning-range limits; exploratory inputs."""
import json
from chip_model import P
from fractional_rf_chip import ShapedRFClock
from oscillator_noise import FrequencyNoise

def measure(target,free_offset,phase,noise):
    p=ShapedRFClock(reference_hz=40e6,divider=60,free_hz=2.4e9*(1+free_offset),phase_cycles=phase,bandwidth_hz=350e3)
    p.retarget(0,target);p.set_noise(0,FrequencyNoise.seeded(noise,seed=830))
    required=(target-p.gains.free_hz)/p.gains.kvco
    reachable=abs(required)<p.filter.limit
    first=None;losses=0;tail_locked=True;fault=None
    for index in range(1,2401):
        try:
            p.advance(index/40e6);was=p.locked;locked=p.observe_lock()
        except ValueError as error:
            fault=str(error);break
        if locked and first is None:first=p.time
        if was and not locked:losses+=1
        if index>=1600:tail_locked=tail_locked and locked
    sustained=fault is None and first is not None and first<=40e-6 and losses==0 and tail_locked
    if not reachable:assert not sustained
    return dict(target_hz=target,free_offset=free_offset,initial_phase_cycles=phase,noise_rms_hz=noise,
        required_steady_control_v=required,inside_nominal_tuning_span=reachable,
        first_lock_s=first,lock_losses=losses,sustained_qualification=sustained,
        final_frequency_hz=p.frequency_hz,final_control_v=p.filter.v,fault=fault,
        minimum_compliance_margin_v=p.metrics()['minimum_compliance_margin_v'])

def main():
    rows=[]
    for target in (2300000000,2437000000,2500000000):
        for offset in (-.08,-.04,.02):
            for phase in (-.4,.2,.4):
                for noise in (0.,20000.):rows.append(measure(target,offset,phase,noise))
            print('Measured',target,'free offset',offset,flush=True)
    summary=dict(cases=len(rows),sustained=sum(r['sustained_qualification'] for r in rows),
        outside_nominal_tuning_span=sum(not r['inside_nominal_tuning_span'] for r in rows),
        reachable_but_unqualified=sum(r['inside_nominal_tuning_span'] and not r['sustained_qualification'] for r in rows))
    report=dict(status='characterized',summary=summary,cases=rows,
        bandwidth_hz=350e3,complete_architecture=False,physical_qualification=False,
        limitations=['Free-frequency offsets and phases are exploratory model settings, not measured GF180 corners or required operating extremes.',
        'DC reachability uses the assumed 200MHz/V gain and +/-1V control envelope; it does not establish transistor tuning range.',
        'One finite noise spectrum; no full-chip loading or RF quality measurement.'])
    (P/'evidence/connected-fractional-startup.json').write_text(json.dumps(report,indent=2)+'\n')
    print(summary,flush=True)
if __name__=='__main__':main()
