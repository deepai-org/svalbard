"""Independent matched-network pad quality on real managed traffic, mode0."""
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

class LoadedHostChip(PhaseLoadedTxChip,HostActivationChip):
    pass

class IdealLoadedChip(reconstructed(ProgrammableChip,'elliptic')):
    """Matched passive network and source units; ideal nominal carrier/modulator."""
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.loaded_tx=LoadedDetector()
        original=self.tx.advance
        def advance(time):
            if time>self.tx.time:
                assert self.tx.time==self.loaded_tx.network.time
                self.loaded_tx.advance(time,output_terms(self.tx.transmit_terms()) or [(0j,0j)])
            original(time)
        self.tx.advance=advance
    def complete_dac(self,time):
        before=self.dac_pipeline_updates
        result=super().complete_dac(time)
        if self.dac_pipeline_updates>before:self.loaded_tx.network.configure(True,False)
        return result
    def quiesce(self,time,reason):
        self.tx.advance(time);self.loaded_tx.network.configure(False,True)
        return super().quiesce(time,reason)

def main():
    mode=0;target=2412000000
    experiment=copy.deepcopy(PROFILE['experiment']);experiment['source_count']=18000
    experiment['source_offset_hz']+=target-2400000000
    records=[];instances=[]
    for actual,base in ((False,IdealLoadedChip),(True,LoadedHostChip)):
        found=[]
        cls=captured(prepared(base,target,not actual,50e-6,
            postprepare=conditioner('switching',0.),before_mode=calibration_window(not actual)),target,found)
        options=(dict(tx_relative_gain=True,rf_free_offset=-.08,coarse_noise_bound_hz=80000,
            rf_fast_fraction=.30,rf_pulse_bandwidth_hz=300e3,
            **PROFILE['shared_reference'],**PROFILE['coupling']) if actual else
            dict(load_capacitance=0,dac_reference_load_capacitance=0,probe_load_scale=0))
        kwargs=dict(blockers=[(a,f+target-2400000000) for a,f in PROFILE['blockers']],cubic=PROFILE['cubic']) if actual else {}
        result=simulate(mode,actual,chip_class=cls,chip_options=options,experiment=experiment,**kwargs)
        records.append(result);instances.append(found[0]);print('actual' if actual else 'ideal','traffic completed',flush=True)
    ti,x=zip(*instances[0].pad_observations);ta,y=zip(*instances[1].pad_observations)
    assert ti==ta and records[0][1]==records[1][1]
    tx=quality(list(x),list(y));rx=quality(records[0][2],records[1][2])
    np.savez_compressed(P/'evidence/connected-loaded-pad-quality-mode0-traces.npz',time_s=ti,ideal_pad=x,actual_pad=y)
    report=dict(status='passed' if tx['screen_pass'] and rx['screen_pass'] else 'failed',mode=mode,
        transmit_quality=tx,receive_quality=rx,actual_spectrum=spectrum(ta,y),
        traffic=records[1][0],reference_traffic=records[0][0],
        phase_substeps=instances[1].phase_steps,phase_residual=instances[1].phase_residual,
        limitations=['Mode0 only; provisional10% held-out quality, not protocol compliance.',
        'Matched passive network/source units; ideal carrier/modulator reference versus actual oscillator and nonlinear stage.',
        'No DC driver feedback, package extraction, shared detector-ADC resource closure or retune/recovery quality.',
        'Calibration uses finite loaded10bit detector without optional readout curvature in this case.'])
    (P/'evidence/connected-loaded-pad-quality-mode0.json').write_text(json.dumps(report,indent=2)+'\n')
    print(tx,rx,flush=True)
    assert report['status']=='passed'

if __name__=='__main__':main()
