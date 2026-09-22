"""Independent RF waveform quality after managed warm coarse retuning."""
import copy,json,hashlib
from chip_model import P
from coarse_retune_lifecycle import CoarseRetuningChip
from programmable_chip import ProgrammableChip
from calibration_wideband_screen import prepared,PROFILE,PROFILE_PATH
from managed_resources import command
from wideband_clock_quality import simulate
from rf_quality_screen import quality

def warmup(initial,target):
 def prepare(c,mode):
    # Identical absolute-time prelude for ideal and physical-assumption models.
    if hasattr(c,'coarse'):
        assert command(c,'rf_coarse_start',initial)['accepted']
    else:c.configure_rf_carrier(initial)
    c.advance(50e-6)
    # Bypass only the harness's configure wrapper, never the model lifecycle.
    if hasattr(c,'coarse'):CoarseRetuningChip.configure(c,mode,c.time)
    else:ProgrammableChip.configure(c,mode,c.time)
    c.advance(100e-6)
    assert c.state=='active' and c.rf_pll.locked and c.wire_pll.locked
    c.quiesce(c.time,'warm waveform retune')
    c.acknowledge_host_abort(c.epoch,c.time);c.acknowledge_drain(c.epoch,c.time)
    assert command(c,'detect_rearm')['accepted']
    if hasattr(c,'coarse'):
        assert command(c,'rf_coarse_start',target)['accepted']
    else:c.configure_rf_carrier(target)
    c.advance(200e-6)
    if hasattr(c,'coarse'):
        assert c.coarse.qualified and c.coarse.center_history and c.rf_pll.locked
 return prepare

def main():
 rows=[]
 for mode,initial,target in ((0,2500000000,2412000000),(1,2300000000,2437000000)):
    experiment=copy.deepcopy(PROFILE['experiment']);experiment['source_count']=16800
    experiment['source_offset_hz']+=target-2400000000
    common=dict(experiment=experiment,service_pauses={16:16})
    baseline,times,reference=simulate(mode,False,chip_class=prepared(ProgrammableChip,target,True,warmup=warmup(initial,target)),
        chip_options=dict(load_capacitance=0,dac_reference_load_capacitance=0,probe_load_scale=0),**common)
    blockers=[(a,f+target-2400000000) for a,f in PROFILE['blockers']]
    traffic,actual,measured=simulate(mode,True,chip_class=prepared(CoarseRetuningChip,target,warmup=warmup(initial,target)),
        blockers=blockers,cubic=PROFILE['cubic'],chip_options=dict(rf_free_offset=-.08,
        coarse_noise_bound_hz=80000,rf_pulse_bandwidth_hz=PROFILE['rf_pulse_bandwidth_hz'],
        **PROFILE['shared_reference'],**PROFILE['coupling']),**common)
    assert times==actual and len(reference)==len(measured)
    assert actual[-1]<(experiment['source_count']-1)/experiment['source_rate_hz']
    q=quality(reference,measured)
    rows.append(dict(mode=mode,initial_hz=initial,target_hz=target,quality=q,traffic=traffic,reference_traffic=baseline,experiment=experiment))
    report=dict(status='running' if len(rows)<2 else ('passed' if all(r['quality']['screen_pass'] for r in rows) else 'failed'),cases=rows,
        profile_sha256=hashlib.sha256(PROFILE_PATH.read_bytes()).hexdigest(),complete_architecture=False,physical_qualification=False,
        limitations=['Two retunes, one noise/blocker/coupling realization; provisional 10% incremental waveform-error limit.',
        'Both I/Q calibrations are rerun after warm retuning; this does not claim retained calibration accuracy.',
        'Analog state is continuous through prelude, quiescence, passive recentering and acquisition.',
        '420us source covers the fixed 200us warm prelude plus calibration, acquisition and four-path traffic.'])
    (P/'evidence/connected-retuned-wideband.json').write_text(json.dumps(report,indent=2)+'\n')
    print(mode,initial,target,q['corrected_relative_rms'],q['screen_pass'],flush=True)
 assert all(r['quality']['screen_pass'] for r in rows)
if __name__=='__main__':main()
