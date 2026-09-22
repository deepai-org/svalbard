"""Independent nominal-carrier TX error and finite-burst spectral observation."""
import copy,json
import numpy as np
from pathlib import Path
from chip_model import P
from coarse_retune_lifecycle import CoarseRetuningChip
from programmable_chip import ProgrammableChip
from calibration_wideband_screen import prepared,PROFILE
from wideband_clock_quality import simulate
from rf_quality_screen import quality
from tx_envelope_observer import observed,spectrum
from tx_host_precondition import conditioner
from host_activation_chip import HostActivationChip
from reconstructed_chip import reconstructed
from tx_output_candidate import output_candidate
from managed_tx_quality import ManagedTxHostChip,UncorrectedManagedTxHostChip,calibration_window
from tx_output_isolation import IsolatedManagedTxHostChip

def main(modes=(0,1),rf_noise_hz=None,rf_supply_hz_per_v=None,output='connected-tx-wideband.json',rf_fast_fraction=.5,rf_bandwidth_hz=None,host_warmup=None,host_delay_s=0.,managed_host=False,require_rx_quality=False,tx_reconstruction=None,tx_output=False,managed_tx=False,disable_tx_correction=False,detector_readout=False,relative_tx_gain=False,output_isolation=False):
 if not modes or any(m not in (0,1) for m in modes):raise ValueError('Unsupported mode')
 bandwidth=PROFILE['rf_pulse_bandwidth_hz'] if rf_bandwidth_hz is None else rf_bandwidth_hz
 if output_isolation and (not managed_tx or disable_tx_correction):raise ValueError('Isolation requires corrected managed TX')
 if relative_tx_gain and not managed_tx:raise ValueError('Relative correction requires managed TX')
 if detector_readout and not managed_tx:raise ValueError('Detector readout requires managed calibration')
 if disable_tx_correction and not managed_tx:raise ValueError('Correction bypass requires managed TX diagnostic')
 candidate=HostActivationChip if managed_host else CoarseRetuningChip
 if managed_tx:
  if not managed_host or tx_reconstruction!='elliptic' or tx_output:raise ValueError('Managed TX needs host/elliptic and excludes fixture output')
  candidate=UncorrectedManagedTxHostChip if disable_tx_correction else ManagedTxHostChip
 if output_isolation:candidate=IsolatedManagedTxHostChip
 golden=ProgrammableChip
 if tx_reconstruction:
  if not managed_tx:candidate=reconstructed(candidate,tx_reconstruction)
  golden=reconstructed(golden,tx_reconstruction)
 if tx_output:
  if not tx_reconstruction:raise ValueError('TX output profile requires reconstruction')
  candidate=output_candidate(candidate)
 def passed(row):return row['quality']['screen_pass'] and (not require_rx_quality or row['receive_quality']['screen_pass'])
 rows=[]
 for mode in modes:
    target=(2412000000,2437000000)[mode]
    experiment=copy.deepcopy(PROFILE['experiment']);experiment['source_count']=18000 if managed_tx else 10400
    experiment['source_offset_hz']+=target-2400000000
    if rf_noise_hz is not None:experiment['rf_noise_rms_hz']=rf_noise_hz
    if rf_supply_hz_per_v is not None:experiment['rf_hz_per_v']=rf_supply_hz_per_v
    ideal=[];actual=[]
    baseline,rx_times,rx_reference=simulate(mode,False,chip_class=observed(prepared(golden,target,True,50e-6,postprepare=conditioner(host_warmup,host_delay_s),before_mode=calibration_window(True) if managed_tx else None),target,ideal),
        chip_options=dict(load_capacitance=0,dac_reference_load_capacitance=0,probe_load_scale=0),experiment=experiment)
    traffic,actual_rx_times,rx_measured=simulate(mode,True,chip_class=observed(prepared(candidate,target,False,50e-6,postprepare=conditioner(host_warmup,host_delay_s),before_mode=calibration_window(False) if managed_tx else None),target,actual),
        blockers=[(a,f+target-2400000000) for a,f in PROFILE['blockers']],cubic=PROFILE['cubic'],
        chip_options=dict(**({'tx_relative_gain':True} if relative_tx_gain else {}),**({'tx_detector_options':dict(gain=1.1,offset=.0002,curvature=.2)} if detector_readout else {}),rf_free_offset=-.08,coarse_noise_bound_hz=80000,rf_fast_fraction=rf_fast_fraction,
          rf_pulse_bandwidth_hz=bandwidth,**PROFILE['shared_reference'],**PROFILE['coupling']),experiment=experiment)
    ti,x=zip(*ideal[0].tx_observations);ta,y=zip(*actual[0].tx_observations)
    assert ti==ta and rx_times==actual_rx_times
    receive_quality=quality(rx_reference,rx_measured)
    q=quality(list(x),list(y))
    ib,ip=zip(*ideal[0].tx_component_observations);ab,ap=zip(*actual[0].tx_component_observations)
    diagnosis=dict(phase_only=quality(list(x),[b*r for b,r in zip(ib,ap)]),
        baseband_only=quality(list(x),[b*r for b,r in zip(ab,ip)]),
        scope='Counterfactual component substitution on recorded states; omits output nonlinearity and isolation; not separate closed-loop experiments or an additive error budget.')
    trace_name=Path(output).stem+f'-mode{mode}-traces.npz'
    np.savez_compressed(P/'evidence'/trace_name,time_s=ti,ideal_tx=x,actual_tx=y,ideal_baseband=ib,actual_baseband=ab,ideal_rotation=ip,actual_rotation=ap,actual_pad_transfer=actual[0].tx_pad_transfers)
    row=dict(output_isolation=output_isolation,isolation_metrics=actual[0].reference_metrics().get("tx_output_isolation"),relative_tx_gain=relative_tx_gain,detector_readout=detector_readout,diagnostic_correction_bypass=disable_tx_correction,managed_tx_calibration=managed_tx,tx_output_stage=tx_output or managed_tx,tx_reconstruction=tx_reconstruction,receive_quality=receive_quality,managed_host=managed_host,host_delay_s=host_delay_s,host_warmup=host_warmup,traces=trace_name,rf_bandwidth_hz=bandwidth,rf_fast_fraction=rf_fast_fraction,experiment=experiment,diagnosis=diagnosis,mode=mode,target_hz=target,quality=q,ideal_spectrum=spectrum(ti,x),actual_spectrum=spectrum(ta,y),traffic=traffic,reference_traffic=baseline)
    rows.append(row)
    report=dict(receive_quality_required=require_rx_quality,status='running' if len(rows)<len(modes) else ('passed' if all(passed(r) for r in rows) else 'failed'),quality_pass=all(passed(r) for r in rows),cases=rows,
       complete_architecture=False,physical_qualification=False,
       limitations=['TX error is measured against an independent carrier, not the shared RX LO.',
       'Spectra include finite launch transient, DAC images and window leakage; no protocol mask is claimed.',
       'TX output stage includes static IQ mismatch, leakage and compression. Managed calibration uses timed internal probes; fixture calibration is separate.',
       'Optional finite isolation uses assumed attenuation/timing and a pre-isolation detector; pad loading, switching injection and bypass leakage remain unmodeled.',
       'No host pauses in this uniform-observation spectral screen; prior separate traffic checks cover pauses.',
       'Provisional 10% incremental waveform-error screen does not constrain ideal-path spectral leakage.'])
    (P/'evidence'/output).write_text(json.dumps(report,indent=2)+'\n')
    print(mode,q['corrected_relative_rms'],q['screen_pass'],row['actual_spectrum']['outside_to_inside_db'],diagnosis,flush=True)
 assert all(passed(r) for r in rows)
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser()
 parser.add_argument('--output-isolation',action='store_true')
 parser.add_argument('--relative-tx-gain',action='store_true')
 parser.add_argument('--detector-readout',action='store_true')
 parser.add_argument('--disable-tx-correction',action='store_true')
 parser.add_argument('--managed-tx-calibration',action='store_true')
 parser.add_argument('--tx-output-stage',action='store_true')
 parser.add_argument('--tx-reconstruction',choices=('elliptic','butterworth','chebyshev'))
 parser.add_argument('--require-rx-quality',action='store_true')
 parser.add_argument('--managed-host',action='store_true')
 parser.add_argument('--host-delay-s',type=float,default=0.)
 parser.add_argument('--host-warmup',choices=('quiet','switching'))
 parser.add_argument('--rf-bandwidth-hz',type=float)
 parser.add_argument('--rf-fast-fraction',type=float,default=.5)
 parser.add_argument('--mode',type=int,choices=(0,1))
 parser.add_argument('--rf-noise-hz',type=float)
 parser.add_argument('--rf-supply-hz-per-v',type=float)
 parser.add_argument('--output',default='connected-tx-wideband.json')
 args=parser.parse_args()
 main((0,1) if args.mode is None else (args.mode,),args.rf_noise_hz,args.rf_supply_hz_per_v,args.output,args.rf_fast_fraction,args.rf_bandwidth_hz,args.host_warmup,args.host_delay_s,args.managed_host,args.require_rx_quality,args.tx_reconstruction,args.tx_output_stage,args.managed_tx_calibration,args.disable_tx_correction,args.detector_readout,args.relative_tx_gain,args.output_isolation)
