"""Independent matched-network pad quality on real managed traffic, mode0."""
import copy,json
import numpy as np
from chip_model import P
from loaded_pad_capture import captured
from calibration_wideband_screen import prepared,PROFILE
from tx_host_precondition import conditioner
from wideband_clock_quality import simulate
from rf_quality_screen import quality
from tx_envelope_observer import spectrum

from pad_quality_fixture import IdealCarrierChip, before_traffic
from shared_phase_loaded_tx import SharedPhaseLoadedTxChip



def main(mode=0, *, rail_budget=False):
    actual_chip_class=SharedPhaseLoadedTxChip
    if rail_budget:
        from managed_rail_budget import ManagedRailBudgetChip
        actual_chip_class=ManagedRailBudgetChip
    target=(2412000000,2437000000)[mode]
    prefix=f"connected-{'rail20' if rail_budget else 'shared'}-pad-quality-mode{mode}"
    experiment=copy.deepcopy(PROFILE['experiment']);experiment['source_count']=18000
    experiment['source_offset_hz']+=target-2400000000
    records=[];instances=[]
    for actual,base in ((False,IdealCarrierChip),(True,actual_chip_class)):
        found=[]
        cls=captured(prepared(base,target,not actual,50e-6,
            postprepare=conditioner('switching',0.),before_mode=before_traffic(not actual)),target,found)
        options=(dict(tx_relative_gain=True,rf_free_offset=-.08,coarse_noise_bound_hz=80000,
            rf_fast_fraction=.30,rf_pulse_bandwidth_hz=300e3,
            **PROFILE['shared_reference'],**PROFILE['coupling']) if actual else
            dict(network_carrier_hz=target,load_capacitance=0,dac_reference_load_capacitance=0,probe_load_scale=0))
        kwargs=dict(blockers=[(a,f+target-2400000000) for a,f in PROFILE['blockers']],cubic=PROFILE['cubic']) if actual else {}
        result=simulate(mode,actual,chip_class=cls,chip_options=options,experiment=experiment,**kwargs)
        records.append(result);instances.append(found[0]);print('actual' if actual else 'ideal','traffic completed',flush=True)
    ti,x=zip(*instances[0].pad_observations);ta,y=zip(*instances[1].pad_observations)
    assert ti==ta and records[0][1]==records[1][1]
    tx=quality(list(x),list(y));rx=quality(records[0][2],records[1][2])
    np.savez_compressed(P/'evidence'/(prefix+'-traces.npz'),time_s=ti,ideal_pad=x,actual_pad=y)
    actual=instances[1]
    diagnostics=(dict(driver_feedback_steps=actual.driver_feedback_steps,
        driver_rail_v=actual.loaded_tx.driver.rail_v,
        driver_rail_resistance_ohm=actual.loaded_tx.driver.r,
        driver_rail_capacitance_f=actual.loaded_tx.driver.c,
        coupled_reference_v=actual.adc_reference.voltage) if rail_budget else
        dict(phase_substeps=actual.phase_steps,phase_residual=actual.phase_residual))
    report=dict(shared_adc_samples=instances[1].tx_adc_samples,maintenance_observation_count=len(instances[1].tx_maintenance_observations),status='passed' if tx['screen_pass'] and rx['screen_pass'] else 'failed',mode=mode,
        transmit_quality=tx,receive_quality=rx,actual_spectrum=spectrum(ta,y),
        traffic=records[1][0],reference_traffic=records[0][0],
        **diagnostics,
        limitations=['Single selected mode; provisional10% held-out quality, not protocol compliance.',
        'Matched passive network/source units; ideal carrier/modulator reference versus actual oscillator and nonlinear stage.',
        'No DC driver feedback, package extraction, analog mux settling/load closure or retune/recovery quality.',
        'Calibration uses actual shared12bit ADC transfer/reference with explicit power-to-voltage scale; mux analog settling absent.'])
    if rail_budget:
        report['limitations'].insert(0, '20ohm driver rail versus 100ohm failed baseline; nonbinding reference current limits preserve its reference law. Rail impedance is an assumption requiring physical justification.')
        report['limitations'][-2:]=[
            'Coupled driver/readout/reference/PLL feedback included; no package extraction, reverse mux loading or retune/recovery quality.',
            'Calibration uses actual shared12bit ADC transfer and finite readout; physical current limits, aperture and driver laws remain assumptions.']
    (P/'evidence'/(prefix+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(tx,rx,flush=True)
    assert report['status']=='passed'

def cli(*, rail_budget=False):
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--mode',type=int,choices=(0,1),default=0)
    main(parser.parse_args().mode,rail_budget=rail_budget)

if __name__ == '__main__':
    cli()
