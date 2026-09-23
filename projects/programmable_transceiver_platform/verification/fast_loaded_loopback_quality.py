"""Nonlinear internal loopback quality with independent TX observation."""
import argparse,hashlib,json,time,sys
from pathlib import Path
FAST=Path(__file__).resolve().parents[1]/'system_model/architecture_fast'
sys.path.insert(0,str(FAST))
from continuous_four_path import run
from fast_loaded_traffic import PreparedLoadedChip as PreparedChip,PreparedPoweredChip
from continuous_duplex import run as run_rf
from shared_tx_traffic import scenario
from rf_quality_screen import quality
from chip_model import decode_iq
from managed_resources import command
from rf_modulated_quality import Multicarrier


def simulate(mode,impaired,power_gated=False,wideband=False):
    chips=[]
    class Observed(PreparedPoweredChip if power_gated else PreparedChip):
        def __init__(self,**kwargs):
            options=dict(load_capacitance=0,output_parameters=dict(
                gain_imbalance_db=0.,phase_error_deg=0.,lo_feedthrough=0j,cubic=0.))
            if impaired:
                options=dict(load_capacitance=1e-12,dac_reference_load_capacitance=.2e-12,
                    return_charge_per_transition=50e-15,rf_hz_per_v=1e6,wire_hz_per_v=1e5,
                    rf_noise_rms_hz=20000,wire_noise_rms_hz=20000,noise_seed=839,
                    frontend=dict(gain_error=.03,phase_error=.03,saturation=.8,noise_rms=.001,seed=800))
            self.adc_analog=[]
            super().__init__(**options,**kwargs)
            assert command(self,'configure_rx_gain',2)['accepted']
            self.adc_analog.clear()
            self.tx_probe.clear();self.probe_times.clear()
            assert self.tx.rx_route=="loopback"
            chips.append(self)
        def quantize_adc(self,value):
            self.adc_analog.append(value)
            return super().quantize_adc(value)
    waveform=Multicarrier(seed=804) if wideband else None
    traffic=(run_rf if power_gated else run)(mode,True,True,chip_factory=Observed,waveform=waveform)
    if wideband:traffic['waveform']=waveform.metadata
    if power_gated:
        assert chips[0].off_clock_checks>128
        assert not chips[0].wired_output and not chips[0].host_wire
        traffic['off_clock_checks']=chips[0].off_clock_checks
    c=chips[0];bits=12 if mode==0 else 8
    return [decode_iq(w,bits) for w in c.host_samples],c.tx_probe,c.probe_times,traffic,c.adc_analog[:len(c.host_samples)]


def coupled_linear_reference(data):
    import math,cmath
    import numpy as np
    from chip_model import encode_iq
    from rf_switched_load import SwitchedLoad
    from rf_loaded_detector import voltage_terms
    from rf_cascade_state import RfCascadeState,convolution
    from tx_reconstruction import Reconstruction
    from session import Session
    played=data['played'];observations=data['observations']
    bits=data.get('bits_per_component',12)
    if bits not in (8,12):raise ValueError('Unsupported sample precision')
    desired=[decode_iq(encode_iq(complex(*z),bits),bits) for z in data['desired_iq']]
    reconstruction=Reconstruction();dc=float(reconstruction.response([0])[0].real)
    network=SwitchedLoad(frequency_hz=2437e6)
    cascade=RfCascadeState(Session());cascade.set_butterworth(5,9157407.055691985)
    bank=cascade.rx_bank
    epoch=min(observations[0]['time_s'],played[0][0])
    network.time=reconstruction.time=epoch
    held=0j;rx=[];tx=[]
    events=sorted([(t,0,i) for i,(t,_,_) in enumerate(played)]+
                  [(row['time_s'],1,i) for i,row in enumerate(observations)])
    for time,kind,index in events:
        dt=time-network.time
        modes=voltage_terms(network,reconstruction.terms(held))
        bank['states']=[old*cmath.exp(-pole*dt)+sum(v[1]*convolution(rate,pole,dt) for v,rate in modes)
            for old,pole in zip(bank['states'],bank['poles'])]
        network.voltage=sum((v*np.exp(rate*dt) for v,rate in modes),np.zeros(4,complex))
        network.time=time;reconstruction.advance(time,held)
        if kind==0:
            held=desired[index]/dc;network.configure(True,False)
        else:
            tx.append(complex(network.voltage[1]))
            value=data.get('capture_gain',1.)*data['rx_gain']*sum(w*x for w,x in zip(bank['weights'],bank['states']))
            rx.append(complex(value))
    return rx,tx

def fixed_carrier_envelope(values,times,offset_hz):
    """Translate a laboratory envelope using only the requested carrier."""
    import cmath,math
    if not times or len(values)!=len(times):raise ValueError('Unaligned carrier record')
    return [z*cmath.exp(-2j*math.pi*offset_hz*(t-times[0]))
        for z,t in zip(values,times)]


def independent_rx_reference(data):
    """Ideal external tones through the declared five-pole receive filter.

    This uses transmitter frequencies, never the chip's measured LO phase or
    TX samples. The long settling precondition makes initial filter memory
    negligible for this fixed diagnostic profile.
    """
    import cmath,math
    source=data['independent_rx']
    if source.get('target_hz')!=2437e6 or source.get('envelope_frame_hz')!=2400e6:
        raise ValueError('External reference supports only the declared carrier profile')
    times=[row['time_s'] for row in data['observations']]
    if not times or min(times)-source['enabled_time_s']<2e-6:
        raise ValueError('Independent RX reference requires settled input')
    tones=source['tones']
    if not tones or any(len(row)!=3 for row in tones):raise ValueError('Missing external tones')
    cutoff=9157407.055691985;order=5
    poles=[-2*math.pi*cutoff*cmath.exp(1j*math.pi*(2*k+order+1)/(2*order))
        for k in range(order)]
    gain=data['rx_gain']*data['capture_gain']
    return [gain*sum(complex(real,imag)*math.prod(p/(p+2j*math.pi*hz) for p in poles)
        *cmath.exp(2j*math.pi*hz*t) for real,imag,hz in tones) for t in times]


def independent_rx_reference_controls():
    """Check frequency response against a separately integrated serial filter."""
    import cmath,math
    import numpy as np
    from scipy.integrate import solve_ivp
    times=[3e-6+i/20e6 for i in range(32)]
    tones=[[.18,0.,2.5e6],[.04,0.,7.5e6]]
    data=dict(rx_gain=2.,capture_gain=.5,observations=[dict(time_s=t) for t in times],
        independent_rx=dict(enabled_time_s=0.,tones=tones,target_hz=2437e6,envelope_frame_hz=2400e6))
    expected=independent_rx_reference(data)
    poles=np.array([-2*math.pi*9157407.055691985*cmath.exp(
        1j*math.pi*(2*k+6)/10) for k in range(5)])
    def rhs(t,y):
        signal=sum(complex(re,im)*cmath.exp(2j*math.pi*f*t) for re,im,f in tones)
        return poles*(np.r_[signal,y[:-1]]-y)
    solution=solve_ivp(rhs,(0.,times[-1]),np.zeros(5,complex),t_eval=times,
        method='DOP853',rtol=1e-10,atol=1e-12,max_step=5e-9)
    if not solution.success:raise AssertionError(solution.message)
    error=max(abs(a-b) for a,b in zip(expected,solution.y[-1]))
    assert error<1e-8,error
    # A receiver tracking its own loopback cannot stand in for this input.
    wrong=[z*cmath.exp(2j*math.pi*1e6*(t-times[0])) for z,t in zip(expected,times)]
    assert not quality(expected,wrong)['screen_pass']
    return dict(maximum_serial_filter_ode_error=float(error),
        wrong_carrier_rejected=True,physical_qualification=False)


def coupled_record_quality(path):
    """Compare a saved coupled payload with an independent linear modal path."""
    import math,cmath
    import numpy as np
    from chip_model import encode_iq
    from rf_switched_load import SwitchedLoad
    from rf_loaded_detector import voltage_terms
    from rf_cascade_state import RfCascadeState,convolution
    from tx_reconstruction import Reconstruction
    from session import Session
    record=json.loads(path.read_text())
    if record.get('status')!='passed' or not record.get('payload'):
        raise ValueError('Completed coupled RF payload record required')
    p=path.parent.parent
    mismatches=[f for f,h in record['source_sha256'].items() if hashlib.sha256((p/f).read_bytes()).hexdigest()!=h]
    if mismatches:raise ValueError('Payload sources differ from reference profile: '+str(mismatches))
    data=record['payload'];observations=data['observations'];played=data['played']
    if len(played)!=32 or len(observations)!=32 or len(data['sample_words'])!=32:
        raise ValueError('Reference supports the declared 32-sample diagnostic')
    rx,tx=coupled_linear_reference(data)
    if data.get('independent_rx'):rx=independent_rx_reference(data)
    measured_rx=[decode_iq(word,data.get('bits_per_component',12)) for word in data['sample_words']]
    measured_tx=[complex(*z)*cmath.exp(-1j*row['rx_lo_phase_rad'])
        for z,row in zip(data['pad_iq'],observations)]
    if len(measured_tx)!=len(tx):raise ValueError('Unaligned pad observations')
    rx_quality=quality(rx,measured_rx);tx_quality=quality(tx,measured_tx)
    # Pad voltages are already envelopes in the fixed rf_carrier frame (see
    # LoadedOutputChip.output_source_terms). Do not remove the DUT oscillator's
    # phase when judging transmission against an independent receiver.
    # This diagnostic tunes 2.437 GHz while the inherited envelope frame remains
    # 2.4 GHz. Translate by the ideal 37 MHz difference, never by measured phase.
    # Choosing a local epoch only changes the constant phase absorbed by gain.
    ideal_offset_hz=2437e6-2400e6
    tx_fixed_carrier=quality(tx,fixed_carrier_envelope(
        [complex(*z) for z in data['pad_iq']],
        [row['time_s'] for row in observations],ideal_offset_hz))
    # An error confined to validation samples must not be absorbed by the fit.
    corrupted=[v if i<8 else -v for i,v in enumerate(rx)]
    assert not quality(rx,corrupted)['screen_pass']
    report=dict(status='passed' if all(q['screen_pass'] for q in
        (rx_quality,tx_quality,tx_fixed_carrier)) else 'failed',
        payload_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        reference_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        reference_controls=coupled_reference_controls(data.get('bits_per_component',12),data['sample_rate_hz'],data.get('capture_gain',1.)),rx=rx_quality,tx=tx_quality,
        tx_fixed_carrier=tx_fixed_carrier,rx_source='independent_tones' if data.get('independent_rx') else 'internal_loopback',ideal_carrier_hz=2437e6,
        envelope_frame_hz=2400e6,physical_qualification=False,full_chip_closure=False,
        limitations=['32 samples, with eight fitting and 24 validation samples; no sustained or modem qualification.',
            'Linear modal reconstruction, finite output load and receive filter at nominal 2.437 GHz; zero initial state after the diagnostic settling interval is assumed.',
            'Uses recorded event times but desired digital samples, not fitted nonlinear DAC values; sample-clock error relative to an ideal schedule remains unqualified.',
            'tx removes saved shared-LO phase to isolate conversion distortion; tx_fixed_carrier retains oscillator error and is also required to pass. Only one constant complex gain is fitted; no frequency or time-varying phase correction.',
            ('RX uses independently generated tones; this finite record does not establish wideband modem, blocker or noise performance.' if data.get('independent_rx') else 'RX is internal loopback and can cancel shared oscillator error; independent external reception and declared phase-noise bounds remain open.'),
            'Fixed profile reference must be revisited if topology, gain, carrier or sample format changes.'])
    if data.get('independent_rx'):report['independent_rx_reference_controls']=independent_rx_reference_controls()
    path.with_name(path.stem.replace('payload','quality')+'.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report)
    if report['status']!='passed':raise AssertionError('Coupled RF waveform exceeded the provisional quality screen')
    return report

def coupled_reference_controls(bits=12,sample_rate_hz=40e6,capture_gain=1.):
    import cmath,math
    from chip_model import encode_iq
    from limited_coupled_driver import LimitedCoupledDriver
    from rf_driver_supply import DriverSupplyLaw
    from rf_switched_load import SwitchedLoad
    from rf_cascade_state import RfCascadeState
    from tx_reconstruction import Reconstruction
    from session import Session
    class LinearLaw(DriverSupplyLaw):
        def source(self,command,rail):return command
    values=[.18*cmath.exp(2j*math.pi*i/16)+.04*cmath.exp(2j*math.pi*i/4) for i in range(32)]
    data=dict(desired_iq=[[z.real,z.imag] for z in values],rx_gain=2.,bits_per_component=bits,capture_gain=capture_gain,
        played=[[20e-9+i/sample_rate_hz,0.,0.] for i in range(32)],
        observations=[dict(time_s=10e-9+i/sample_rate_hz) for i in range(32)])
    expected_rx,expected_tx=coupled_linear_reference(data)
    cascade=RfCascadeState(Session());cascade.set_butterworth(5,9157407.055691985)
    d=LimitedCoupledDriver(network=SwitchedLoad(frequency_hz=2437e6),law=LinearLaw(),rx_bank=cascade.rx_bank)
    r=Reconstruction();dc=float(r.response([0])[0].real);held=0j
    rx=[];tx=[]
    events=sorted([(row[0],0,i) for i,row in enumerate(data['played'])]+
        [(row['time_s'],1,i) for i,row in enumerate(data['observations'])])
    for time,kind,index in events:
        d.advance(time,lambda t:r.value(t,held),rtol=1e-10,atol=1e-13)
        r.advance(time,held)
        if kind==0:
            held=decode_iq(encode_iq(values[index],bits),bits)/dc
            d.network.configure(True,False)
        else:
            rx.append(2*capture_gain*d.received);tx.append(complex(d.network.voltage[1]))
    rx_error=max(abs(a-b) for a,b in zip(rx,expected_rx))
    tx_error=max(abs(a-b) for a,b in zip(tx,expected_tx))
    assert max(rx_error,tx_error)<1e-8
    assert quality(expected_rx,rx)['screen_pass'] and quality(expected_tx,tx)['screen_pass']
    damaged=[z if i<8 else -z for i,z in enumerate(rx)]
    assert not quality(expected_rx,damaged)['screen_pass']
    # A shared-LO comparison can entirely conceal this phase disturbance.
    # The independent carrier comparison must reject it instead.
    phase=[0. if i<8 else .3 for i in range(len(tx))]
    disturbed=[z*cmath.exp(1j*p) for z,p in zip(tx,phase)]
    assert not quality(expected_tx,disturbed)['screen_pass']
    assert quality(expected_tx,[z*cmath.exp(-1j*p)
        for z,p in zip(disturbed,phase)])['screen_pass']
    times=[row['time_s'] for row in data['observations']]
    laboratory=[z*cmath.exp(2j*math.pi*37e6*(t-times[0])) for z,t in zip(tx,times)]
    assert quality(expected_tx,fixed_carrier_envelope(laboratory,times,37e6))['screen_pass']
    disturbed_lab=[z*cmath.exp(1j*p) for z,p in zip(laboratory,phase)]
    assert not quality(expected_tx,fixed_carrier_envelope(disturbed_lab,times,37e6))['screen_pass']
    return dict(samples=32,maximum_rx_ode_error=rx_error,maximum_tx_ode_error=tx_error,
        validation_only_error_rejected=True,shared_lo_hidden_phase_error_rejected=True,
        physical_qualification=False)

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    parser=argparse.ArgumentParser();parser.add_argument('--power-gated',action='store_true')
    parser.add_argument('--wideband',action='store_true')
    parser.add_argument('--coupled-record',type=Path)
    parser.add_argument('--coupled-reference-controls',action='store_true')
    args=parser.parse_args()
    if args.coupled_reference_controls:
        print(coupled_reference_controls());return
    if args.coupled_record is not None:return coupled_record_quality(args.coupled_record.resolve())
    p=scenario.architecture.P;start=time.monotonic()
    files=list(scenario.architecture.D.glob('*.py'))+list(FAST.glob('*.py'))+[Path(__file__),p/'verification/fast_loaded_output.py',p/'verification/fast_loaded_traffic.py',p/'verification/fast_exclusive_engine.py']+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',power_gated=args.power_gated,wideband=args.wideband,source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Finite continuous-service record with timed lossy stop, not indefinite service bounds.',
                     'RX follows nonlinear TX loopback; --wideband selects 50 changing QPSK carriers through +/-7.8125 MHz, otherwise a repeating pattern. Neither is protocol compliance.',
                     'Assumed device/noise parameters; no spectral mask or physical qualification.',
                     'Both baseline and impaired candidate use finite pad/monitor network, relative-gain calibration and the same 2x RX gain.',
                     'Independent TX observation is actual loaded pad voltage; no source reconstruction or normalization.',
                     'Pre-quantizer diagnostics include frontend/reference/recovery; they isolate quantization, not individual analog impairments.'])
    prefix='fast-powered' if args.power_gated else 'fast-loaded'
    output=p/('evidence/'+prefix+('-wideband' if args.wideband else '')+'-loopback-quality.json')
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for mode in (0,1):
            rx0,tx0,t0,baseline_traffic,analog0=simulate(mode,False,args.power_gated,args.wideband)
            rx,tx,t,traffic,analog=simulate(mode,True,args.power_gated,args.wideband)
            assert t==t0 and len(rx)==len(rx0)
            if args.wideband:assert traffic['waveform']==baseline_traffic['waveform']
            rq=quality(rx0,rx);tq=quality(tx0,tx)
            diagnostics=dict(analog_rx_quality=quality(analog0,analog),
                baseline_quantization=quality(analog0,rx0),impaired_quantization=quality(analog,rx),
                baseline_adc_rms=(sum(abs(z)**2 for z in analog0)/len(analog0))**.5,
                impaired_adc_rms=(sum(abs(z)**2 for z in analog)/len(analog))**.5)
            report['cases'].append(dict(mode=mode,rx_quality=rq,tx_quality=tq,traffic=traffic,diagnostics=diagnostics));save()
            print(mode,rq['corrected_relative_rms'],tq['corrected_relative_rms'],flush=True)
            assert rq['screen_pass'] and tq['screen_pass']
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:
        report['elapsed_s']=time.monotonic()-start
        save()

if __name__=='__main__':main()
