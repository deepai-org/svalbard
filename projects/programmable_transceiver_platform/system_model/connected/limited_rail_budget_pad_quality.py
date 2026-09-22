"""Unified driver/PLL/reference candidate on unchanged independent traffic quality."""
import copy,json
import numpy as np
from chip_model import P
from phase_loaded_tx_chip import PhaseLoadedTxChip
from host_activation_chip import HostActivationChip
from programmable_chip import ProgrammableChip
from reconstructed_chip import reconstructed
from rf_loaded_detector import LoadedDetector
from tx_output_terms import output_terms
from loaded_pad_capture import captured
from calibration_wideband_screen import prepared,PROFILE
from managed_tx_quality import calibration_window
from tx_host_precondition import conditioner
from wideband_clock_quality import simulate
from rf_quality_screen import quality
from tx_envelope_observer import spectrum

from loaded_pad_quality import IdealLoadedChip
from managed_limited_rail_budget import ManagedLimitedRailBudgetChip

class IdealCarrierChip(IdealLoadedChip):
    def __init__(self,network_carrier_hz=2412000000,**kwargs):
        super().__init__(**kwargs)
        self.loaded_tx.network.reframe(network_carrier_hz,0.)

def before_traffic(ideal,failure_path=None):
    def prepare(c):
        try:
            calibration_window(ideal)(c)
        except TimeoutError as error:
            if failure_path is not None:
                pll=c.rf_pll
                conditions=dict(reference_present=bool(c.reference),
                    coarse_qualified=bool(c.coarse.qualified),pll_locked=bool(pll.locked),
                    quiet=bool(c.quiet()),tx_queue_empty=not bool(c.tx.queue),
                    calibration_not_busy=not bool(c.tx_cal.busy))
                report=dict(status='failed_readiness',error=str(error),time_s=c.time,
                    conditions=conditions,pll_time_s=pll.time,
                    phase_error_cycles=pll.error,frequency_hz=pll.frequency_hz,
                    reference_frequency_error_hz=pll.frequency_hz/pll.divider-pll.reference_hz,
                    phase_limit_cycles=pll.lock_phase,frequency_limit_hz=pll.lock_frequency,
                    pll_good=pll.good,pll_present=pll.present,pll_fault=pll.fault,
                    filter_v=pll.filter.v,filter_w=pll.filter.w,
                    driver_rail_v=c.loaded_tx.driver.rail_v,reference_v=c.adc_reference.voltage,
                    recent_lock_history=c.rf_lock_history[-32:],recent_events=c.events[-16:])
                failure_path.write_text(json.dumps(report,indent=2)+'\n')
                print('READINESS FAILURE',report,flush=True)
            raise
        # ADC conversion logs include maintenance reads. Keep them separately;
        # only subsequent receive conversions belong to the RX waveform record.
        c.tx_maintenance_observations=list(zip(c.sample_times,c.analog_samples))
        c.sample_times=[];c.analog_samples=[]
    return prepare

def main(mode=0,phase_diagnostics=False,bandwidth_hz=300e3,actual_chip_class=ManagedLimitedRailBudgetChip,experiment_tag=""):
    target=(2412000000,2437000000)[mode]
    prefix=f"connected-limited-rail20-pad-quality-mode{mode}"
    if experiment_tag:prefix+="-"+experiment_tag
    if bandwidth_hz!=300e3:prefix+=f'-bw{bandwidth_hz:g}'
    if phase_diagnostics:prefix+='-phase-diagnostic'
    experiment=copy.deepcopy(PROFILE['experiment']);experiment['source_count']=18000
    experiment['source_offset_hz']+=target-2400000000
    records=[];instances=[]
    for actual,base in ((False,IdealCarrierChip),(True,actual_chip_class)):
        found=[]
        cls=captured(prepared(base,target,not actual,50e-6,
            postprepare=conditioner('switching',0.),before_mode=before_traffic(not actual,P/'evidence'/(prefix+'-readiness-failure.json'))),target,found,phase_diagnostics=phase_diagnostics and actual)
        options=(dict(tx_relative_gain=True,rf_free_offset=-.08,coarse_noise_bound_hz=80000,
            rf_fast_fraction=.30,rf_pulse_bandwidth_hz=bandwidth_hz,
            **PROFILE['shared_reference'],**PROFILE['coupling']) if actual else
            dict(network_carrier_hz=target,load_capacitance=0,dac_reference_load_capacitance=0,probe_load_scale=0))
        if actual:options.update(resistance=50.,reference_source_limit_a=150e-6,reference_sink_limit_a=150e-6)
        kwargs=dict(blockers=[(a,f+target-2400000000) for a,f in PROFILE['blockers']],cubic=PROFILE['cubic']) if actual else {}
        result=simulate(mode,actual,chip_class=cls,chip_options=options,experiment=experiment,**kwargs)
        records.append(result);instances.append(found[0]);print('actual' if actual else 'ideal','traffic completed',flush=True)
    ti,x=zip(*instances[0].pad_observations);ta,y=zip(*instances[1].pad_observations)
    assert ti==ta and records[0][1]==records[1][1]
    tx=quality(list(x),list(y));rx=quality(records[0][2],records[1][2])
    np.savez_compressed(P/'evidence'/(prefix+'-traces.npz'),time_s=ti,ideal_pad=x,actual_pad=y)
    if phase_diagnostics:
        observations=np.asarray(instances[1].phase_observations)
        assert np.array_equal(observations[:,0],np.asarray(ta))
        np.savez_compressed(P/'evidence'/(prefix+'-phase.npz'),
            time_s=observations[:,0],lo_phase_rad=observations[:,1],
            lo_frequency_hz=observations[:,2],driver_rail_v=observations[:,3],
            reference_v=observations[:,4])
    report=dict(actual_chip_class=actual_chip_class.__name__,experiment_tag=experiment_tag,rf_pulse_bandwidth_hz=bandwidth_hz,shared_adc_samples=instances[1].tx_adc_samples,maintenance_observation_count=len(instances[1].tx_maintenance_observations),status='passed' if tx['screen_pass'] and rx['screen_pass'] else 'failed',mode=mode,
        transmit_quality=tx,receive_quality=rx,actual_spectrum=spectrum(ta,y),
        traffic=records[1][0],reference_traffic=records[0][0],
        driver_feedback_steps=instances[1].driver_feedback_steps,
        driver_rail_v=instances[1].loaded_tx.driver.rail_v,
        driver_rail_resistance_ohm=instances[1].loaded_tx.driver.r,
        coupled_reference_v=instances[1].adc_reference.voltage,
        limitations=['20ohm versus 100ohm driver rail; same 150uA reference limits and 50ohm reference resistance. Supply impedance remains a physical assumption.',
        'Single selected mode; provisional10% held-out quality, not protocol compliance.',
        'Matched passive network/source units; ideal carrier/modulator reference versus actual oscillator and nonlinear stage.',
        'Coupled driver/readout/reference/PLL feedback with 150uA reference limits and entry-state guards; no package extraction or retune/recovery quality.',
        'Calibration uses actual shared12bit ADC transfer and finite readout; physical current limits, aperture and driver laws remain assumptions.'])
    (P/'evidence'/(prefix+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(tx,rx,flush=True)
    assert report['status']=='passed'

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--mode',type=int,choices=(0,1),default=0)
    parser.add_argument('--phase-diagnostics',action='store_true')
    parser.add_argument('--bandwidth-hz',type=float,default=300e3)
    args=parser.parse_args();main(args.mode,args.phase_diagnostics,args.bandwidth_hz)
