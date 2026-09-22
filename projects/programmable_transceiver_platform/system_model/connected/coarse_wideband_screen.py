"""Independent wideband quality after real counted coarse and I/Q calibration."""
import copy,json,hashlib
from chip_model import P
from coarse_startup_lifecycle import CoarseStartupChip
from programmable_chip import ProgrammableChip
from calibration_wideband_screen import prepared,PROFILE,PROFILE_PATH
from wideband_clock_quality import simulate
from rf_quality_screen import quality

def main():
    rows=[]
    for mode,target in ((0,2412000000),(1,2437000000)):
        experiment=copy.deepcopy(PROFILE['experiment']);experiment['source_count']=10400
        experiment['source_offset_hz']+=target-2400000000
        common=dict(experiment=experiment,service_pauses={16:16})
        baseline,times,reference=simulate(mode,False,chip_class=prepared(ProgrammableChip,target,True,50e-6),
            chip_options=dict(load_capacitance=0,dac_reference_load_capacitance=0,probe_load_scale=0),**common)
        blockers=[(a,f+target-2400000000) for a,f in PROFILE['blockers']]
        traffic,actual,measured=simulate(mode,True,chip_class=prepared(CoarseStartupChip,target,False,50e-6),
            blockers=blockers,cubic=PROFILE['cubic'],chip_options=dict(rf_free_offset=-.08,
            coarse_noise_bound_hz=80000,rf_pulse_bandwidth_hz=PROFILE['rf_pulse_bandwidth_hz'],
            **PROFILE['shared_reference'],**PROFILE['coupling']),**common)
        assert times==actual and len(reference)==len(measured)
        assert actual[-1]<(experiment['source_count']-1)/experiment['source_rate_hz']
        assert traffic['reference_metrics']['coarse_tuning']['qualified']
        assert traffic['reference_metrics']['calibration']['maintenance']['completed']==2
        q=quality(reference,measured)
        rows.append(dict(mode=mode,target_hz=target,quality=q,traffic=traffic,reference_traffic=baseline,experiment=experiment))
        print(mode,target,q['corrected_relative_rms'],q['screen_pass'],flush=True)
        report=dict(status=('passed' if len(rows)==2 else 'running') if all(r['quality']['screen_pass'] for r in rows) else 'failed',cases=rows,
            profile_sha256=hashlib.sha256(PROFILE_PATH.read_bytes()).hexdigest(),profile=PROFILE,
            complete_architecture=False,physical_qualification=False,
            limitations=['Two carriers and one positive-coupling/noise realization, not full operating-envelope coverage.',
            '50us common preparation preserves real coarse search and matched baseline sampling times.',
            '10400-sample source explicitly covers longer preparation; no analog state reset at test start.',
            'The bank tuning law and observer bounds are mathematical assumptions.'])
        (P/'evidence/connected-coarse-wideband.json').write_text(json.dumps(report,indent=2)+'\n')
    assert all(r['quality']['screen_pass'] for r in rows)
if __name__=='__main__':main()
