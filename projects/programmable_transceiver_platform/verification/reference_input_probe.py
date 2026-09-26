"""Selected differential REF_IN model and explicit single-ended controls.

Run --check for independent passive-network validation, or without flags for
matched assigned-ENOB RF controls. Add --causal to test SAR/load feedback at
the current package target, including both mismatch and supply-delay signs.
These are conditional circuit requirements, not protocol qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import baseline_envelope as b
from oscillator_noise import loaded_clock_input_phase
from selected_rf import wideband_receive
from converter_dynamics import coupled_reference_load_transfer

p=Path(__file__).resolve().parents[1]
contract=json.loads((p/'spec/contract.json').read_text())

def port(f,candidate,injection,*,source_diff=0.,mismatch=0.,opposed=False,cm_gain=.1):
    w=2*np.pi*f;delta=np.array([1.,-1.])*mismatch
    cap=3e-12*(1+delta);inductance=2e-9*(1+(-delta if opposed else delta));resistance=50.2*(1+delta/2)
    mutual=.4e-9
    zc=1/(1j*w*cap)
    z=np.diag(resistance+1j*w*inductance+zc)+1j*w*mutual*np.array([[0.,1.],[1.,0.]])
    y=np.linalg.inv(z);one=np.ones(2)
    # One differential source with a 5 ps leg-skew probe when mismatched.
    skew=5e-12 if mismatch else 0.
    sources=source_diff/2*np.array([(1+mismatch/2)*np.exp(.5j*w*skew),-(1-mismatch/2)*np.exp(-.5j*w*skew)])
    drive=np.array(injection,complex,copy=True);load=one@y@one;drive[3]+=one@y@sources
    result=b.partitioned_return_solution(f,candidate,drive,link_r_ohm=1e-5,quiet_load_s=load)
    v=result['voltage'];currents=y@(sources-v[3]*one);local=zc*currents
    effective=local[0]-local[1]+cm_gain*np.mean(local)
    supplied=float(np.real(np.vdot(currents,sources))/2)
    host_power=float(np.real(np.vdot(v,injection))/2)
    network_power=float(np.real(np.vdot(v,drive))/2)-abs(v[3])**2*load.real/2
    input_loss=float(np.sum(resistance*abs(currents)**2)/2)
    return dict(network=v,local=local,effective=effective,return_current=sum(currents),source_power=supplied,
        power_residual=supplied+host_power-network_power-input_loss,kcl=result['kcl_residual_a'])


def full(f,candidate,injection,source_diff,mismatch,opposed):
    w=2*np.pi*f;n=candidate['network'];m=np.zeros((7,7),complex);source=np.r_[np.asarray(injection,complex),0j,0j]
    def branch(a,b,y):
        m[a,a]+=y
        if b is not None:m[b,b]+=y;m[a,b]-=y;m[b,a]-=y
    def capacitor(c,r,l):return 1j*w*c/(1+1j*w*c*r-w*w*c*l)
    branch(0,None,1/(n['feed_r']+1j*w*n['feed_l']))
    branch(0,1,1/(n['package_r']+1j*w*n['package_l']))
    branch(0,None,capacitor(n['board_c'],n['board_esr'],n['board_esl']))
    z=candidate['return_r_ohm']+1j*w*candidate['return_l_h']
    branch(2,4,.5/(.9*z));branch(3,4,.5/(.9*z));branch(4,None,1/(.1*z))
    branch(2,3,1e5+1j*w*20e-12)
    branch(1,3,capacitor(n['die_c'],n['die_esr'],n['die_esl']))
    d=np.array([1.,-1.])*mismatch;c=3e-12*(1+d);l=2e-9*(1+(-d if opposed else d));r=50.2*(1+d/2)
    zs=np.diag(r+1j*w*l)+1j*w*.4e-9*np.array([[0.,1.],[1.,0.]])
    ys=np.linalg.inv(zs);skew=5e-12 if mismatch else 0.
    vs=source_diff/2*np.array([(1+mismatch/2)*np.exp(.5j*w*skew),-(1-mismatch/2)*np.exp(-.5j*w*skew)])
    m[5:,5:]+=ys;source[5:]+=ys@vs
    branch(5,3,1j*w*c[0]);branch(6,3,1j*w*c[1])
    v=np.linalg.solve(m,source)
    return v,ys@(vs-v[5:]),float(max(abs(m@v-source)))


def check_network():
    rng=np.random.default_rng(813);maximum=0.;residual=0.;power=0.;count=0;load_error=0.;load_count=0
    for label,ret,esl in b.NETWORK_CASES:
        e=b.selected_environment(contract,'wire',2.5e9,312.5e6,return_l=ret,die_esl=esl)
        for mismatch,opposed in ((0.,False),(.1,True),(.2,False)):
            for f in np.geomspace(1e3,1e10,51):
                injection=.001*(rng.normal(size=5)+1j*rng.normal(size=5));drive=.7*np.exp(.2j)
                reduced=port(f,e['network'],injection,source_diff=drive,mismatch=mismatch,opposed=opposed,cm_gain=.1)
                nodes,currents,kcl=full(f,e['network'],injection,drive,mismatch,opposed)
                np.testing.assert_allclose(reduced['network'],nodes[:5],rtol=1e-7,atol=1e-10)
                np.testing.assert_allclose(reduced['local'],nodes[5:]-nodes[3],rtol=1e-7,atol=1e-10)
                np.testing.assert_allclose(reduced['return_current'],sum(currents),rtol=1e-7,atol=1e-10)
                maximum=max(maximum,float(max(abs(reduced['local']-(nodes[5:]-nodes[3])))))
                residual=max(residual,kcl);power=max(power,abs(reduced['power_residual']));count+=1
            frequencies=np.r_[0.,np.geomspace(1e3,1e10,51)]
            for cm_gain in (-.1,0.,.1):
                coupled=coupled_reference_load_transfer(frequencies,e['network'],
                    differential=dict(mismatch=mismatch,opposed=opposed,cm_gain=cm_gain))
                for i,f in enumerate(frequencies):
                    nodes,_,_=full(f,e['network'],[0,-1,0,1,0],0.,mismatch,opposed)
                    legs=nodes[5:]-nodes[3]
                    expected=dict(rail_v_per_a=nodes[1]-nodes[3],return_v_per_a=nodes[3],
                        input_v_per_a=legs[0]-legs[1]+cm_gain*np.mean(legs),input_leg_v_per_a=legs)
                    for key,value in expected.items():
                        np.testing.assert_allclose(coupled[key][i],value,rtol=1e-7,atol=1e-9)
                        load_error=max(load_error,float(np.max(abs(coupled[key][i]-value))))
                    load_count+=1
    return dict(compared_points=count,maximum_input_voltage_difference_v=maximum,maximum_kcl_residual_a=residual,maximum_power_residual_w=power,
        load_transfer_points=load_count,maximum_load_transfer_difference_ohm=load_error)

def paired_environment(original,opts,*,sign=1.,sensitivity_ps_per_mv=.025,ledger=None,source_peak_v=1.):
    """Reusable paired input for either engine; DC bias is included once in the selected mode ledger."""
    if not np.isfinite(source_peak_v) or source_peak_v<=0:raise ValueError('Positive finite differential source peak required')
    carrier=original['carrier_hz'];gain=b.supply_delay_gain(sensitivity_ps_per_mv,sign)
    if ledger is None:
        _,base=b.single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False)
        ledger=base['ledger']
    wanted=port(carrier,original['network'],np.zeros(5),source_diff=source_peak_v,**opts)
    tones=[];rails=[];delays=[];bound=abs(wanted['local']).copy()
    for frequency,injection in b.partitioned_host_sources(original).items():
        r=port(frequency,original['network'],injection,**opts)
        tones.append((frequency,r['effective']));bound+=abs(r['local'])
        v=r['network'][1]-r['network'][3]
        rails.append(dict(frequency_hz=frequency,clock_rail_voltage_peak_v=float(abs(v)),voltage_phase_rad=float(np.angle(v))))
        delays.append((frequency,v*gain/(1+1j*frequency/1e9)))
    v=wanted['network'][1]-wanted['network'][3]
    rails.append(dict(frequency_hz=carrier,clock_rail_voltage_peak_v=float(abs(v)),voltage_phase_rad=float(np.angle(v))))
    delays.append((carrier,v*gain/(1+1j*carrier/1e9)))
    capture={}
    resolved=b.reference_edge_screen(carrier,wanted['effective'],tones,downstream_delay_tones=delays,substeps=64,capture=capture)
    coarse=b.reference_edge_screen(carrier,wanted['effective'],tones,downstream_delay_tones=delays,substeps=32)
    stable=all(resolved[k]==coarse[k] for k in ('missing_rising_edge_windows','multiple_rising_edge_windows'))
    accepted=bool(capture['complete'] and stable and resolved['assigned_0p6v_incremental_envelope_met'] and max(bound)<=.6)
    row=dict(carrier_hz=carrier,**opts,supply_sign=sign,sensitivity_ps_per_mv=sensitivity_ps_per_mv,
        accepted=accepted,per_leg_bound_v=bound.tolist(),current_a=ledger['total_chip_supply_current_a'],clock=resolved)
    if not accepted:return None,row
    equivalent=original['external_clock_input']['source_peak_v']*abs(wanted['effective'])/original['external_clock_input']['receiver_peak_v']
    noise,input_report=loaded_clock_input_phase(carrier,receiver_noise_v=np.sqrt(2)*75e-6,downstream_stage_rms_s=15e-15,source_peak_v=equivalent)
    reference=[]
    for t in rails:
        h=.1/(1+1j*t['frequency_hz']/10e6)
        reference.append((t['frequency_hz'],t['clock_rail_voltage_peak_v']*abs(h),t['voltage_phase_rad']+np.angle(h)))
    e=dict(original,ledger=ledger,host_spectrum=dict(original['host_spectrum'],tones=rails),reference_fraction_tones=reference,
        rail_maximum_offset_hz=max(t['frequency_hz'] for t in rails),crossing_delay_tones=[],
        periodic_clock=dict(carrier_hz=carrier,period_s=capture['period_s'],edges_s=capture['output_edges_s']),
        delivered_phase_tones=tuple(original['phase_components']['source'])+tuple(noise.tones),
        reference_return_options=dict(link_r_ohm=1e-5),local_supply_delay_sign=sign,local_supply_sensitivity_ps_per_mv=sensitivity_ps_per_mv,
        reference_load_parameters=dict(differential=opts),
        external_clock_input=dict(input_report,topology='differential',physical_source_peak_v=source_peak_v,
            source_peak_interpretation='source_peak_v is gain-equivalent; physical_source_peak_v is differential Thevenin peak'),
        phase_components=dict(source=original['phase_components']['source'],input=noise.tones,supply=()),
        reference_threshold=dict(carrier_v=wanted['effective'],input_tones=tones,
            downstream_delay_tones=delays,threshold_v=.020,input_edges_s=capture['input_edges_s'],period_s=capture['period_s']))
    return e,row


def paired_rf(causal=False):
    rows=[]
    for label,return_l,die_esl in b.NETWORK_CASES[:2]:
        for carrier in (2.4e9,2.484e9):
            original=b.selected_environment(contract,'rf',carrier,carrier/16,return_l=return_l,die_esl=die_esl)
            for mismatch,opposed,cm_gain in ((.1,True,.1),(.2,False,-.1)):
                for sign in (1.,-1.):
                    e,row=paired_environment(original,dict(mismatch=mismatch,opposed=opposed,cm_gain=cm_gain),sign=sign)
                    row['network_case']=label
                    if e is not None:
                        row['rf']=wideband_receive(e,oversample=256,wanted_dbm=-85.,gain_settings_db=(54.,))
                        if causal and label==b.BASELINE_PACKAGE_CASE:
                            row['causal']=b.coupled_wideband_feedback(e,wanted_dbm=-85.,gain_db=54.,oversample=256)
                            loads=[step['load'] for step in row['causal']['iterations']]
                            row['causal_input_leg_bounds_v']=(np.array(row['per_leg_bound_v'])+np.max([x['input_leg_voltage_abs_peak_v'] for x in loads],axis=0)).tolist()
                            row['causal_input_leg_envelope_met']=max(row['causal_input_leg_bounds_v'])<=.6
                    rows.append(row)
                    print(label,carrier,mismatch,sign,row['accepted'],[g['observation']['bpsk_errors'] for g in row.get('rf',{}).get('gain_cases',[])],flush=True)
    return rows

def single_rf(causal=False):
    rows=[]
    for label,return_l,die_esl in b.NETWORK_CASES[:2]:
     for carrier in (2.4e9,2.484e9):
      original=b.selected_environment(contract,'rf',carrier,carrier/16,return_l=return_l,die_esl=die_esl)
      for peak in (.5,.75,1.):
       for sign in (1.,-1.):
        e,report=b.single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False,source_peak_v=peak,supply_sign=sign)
        row=dict(network_case=label,carrier_hz=carrier,source_peak_v=peak,supply_sign=sign,clock=report)
        if e is not None:
         row['rf']=wideband_receive(e,oversample=256,wanted_dbm=-85.,gain_settings_db=(54.,))
         if causal and label==b.BASELINE_PACKAGE_CASE and peak==1.:
          row['causal']=b.coupled_wideband_feedback(e,wanted_dbm=-85.,gain_db=54.,oversample=256)

        rows.append(row)
        print(label,carrier,peak,sign,[x['observation']['bpsk_errors'] for x in row.get('rf',{}).get('gain_cases',[])],flush=True)
    return rows


def shared_internal_campaign(*,single=False):
    """Costed paired clocks and wired readiness under internal switching."""
    from wired_lock_probe import peer_for_environment,resolved_case
    rows=[];saved={mode:b.MODE_CURRENT_A[mode]['timing'] for mode in ('rf','wire')}
    try:
        for mode in saved:b.MODE_CURRENT_A[mode]['timing']=saved[mode]
        for mode,carrier,word in (('rf',2.4e9,150e6),('rf',2.484e9,155.25e6),('wire',2.5e9,312.5e6)):
            original=b.selected_environment(contract,mode,carrier,word)
            original['internal_switching_loads']=[dict(owner='timing',mean_a=.010,event_hz=carrier/16,tau_s=.2e-9,harmonics=64),
                dict(owner='core',mean_a=.020,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)]
            base=None
            if not single:_,base=b.single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False)
            for mismatch,opposed,cm_gain in (((0.,False,0.),) if single else ((.1,True,.1),(.2,False,-.1))):
                for sensitivity in (.1,.025):
                    for sign in (1.,-1.):
                        if single:
                            e,report=b.single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False,source_peak_v=1.,supply_sign=sign,sensitivity_ps_per_mv=sensitivity)
                            row=dict(carrier_hz=carrier,supply_sign=sign,sensitivity_ps_per_mv=sensitivity,
                                accepted=e is not None,current_a=report['ledger']['total_chip_supply_current_a'],clock=report['resolved_crossings'])
                        else:
                            e,row=paired_environment(original,dict(mismatch=mismatch,opposed=opposed,cm_gain=cm_gain),sign=sign,sensitivity_ps_per_mv=sensitivity,ledger=base['ledger'])
                        row['frontend']='single' if single else 'paired'
                        row['mode']=mode;row['wired']=[]
                        if mode=='wire' and e is not None:
                            for offset in (0,4,8,12):
                                peer,edges,_=peer_for_environment(e,offset)
                                for phase in (-.35,.35):
                                    for ppm in (-100.,100.):
                                        row['wired'].append(dict(launch_offset_ui=offset,result=resolved_case(peer,edges,phase,ppm,4,True)))
                        rows.append(row)
                        print('Shared input',mode,carrier,mismatch,sensitivity,sign,flush=True)
    finally:
        for mode,value in saved.items():b.MODE_CURRENT_A[mode]['timing']=value
    return dict(cases=rows,frontend='single' if single else 'paired',scope='Single-ended 1 V source control or differential 1 V total source fallback, plus full internal switching; 500 pF/current package target. Paired input needs one extra signal. Both controls charge 4 mA DC timing bias: RF 240 mA/wired 292 mA. Both mismatch cases and sensitivity signs; 0.1/0.025 ps/mV downstream coefficients. Extra bias is the input allowance, not evidence that reduced downstream sensitivity is funded. RF clock screens only; wired uses unchanged CTLE/CDR, four launch phases and four receiver corners. Nominal coherent internal pulse phase; no RF payload, physical CMRR/bias, asynchronous phase, BER or protocol qualification.')


def shared_rf_campaign(carrier,output,*,acquisition=False,transmit=False):
    """Matched causal RF payloads with internal currents and reduced sensitivity."""
    sources=set(json.loads((p/'evidence/selected-baseline.json').read_text())['sources_sha256'])|{'verification/reference_input_probe.py'}
    if acquisition:sources.add('verification/wideband_packet.py')
    hashes={name:hashlib.sha256((p/name).read_bytes()).hexdigest() for name in sorted(sources)}
    report=dict(cases=[],campaign_complete=False,expected_cases=3 if acquisition else 6,sources_sha256=hashes,
        scope='Matched 1 V nominal source amplitude and +4 mA input bias allowance, RF 240 mA. Differential input still consumes one extra signal. Full internal pulse loads, 500 pF, current package target, 0.025 ps/mV downstream sensitivity and both signs. Two mismatch cases for paired input; no CMRR mismatch model for single-ended control. Causal SAR/reference-load feedback at 20.48 GHz numerical rate, -85 dBm wanted, -30 dBm blocker at +12 MHz, fixed 54 dB gain and known DATA training. No real preamble, AGC, FEC/PER, TX, full phase/variation or physical input/sensitivity qualification. Source power, delivered voltage and pad loading differ between topologies.')
    if acquisition:
        report['scope']='Matched single-ended and 20% aligned-mismatch paired input under full internal switching and causal SAR feedback. 240 mA, 500 pF, current package target, 1 V source, negative 0.025 ps/mV sensitivity. Preselected seed 431, unknown arrival 137 samples and -120 kHz CFO; paired no-wanted control. Real legacy preamble plus diagnostic coded HE20 DATA, not a valid HE packet: known DATA training, fixed gain, no HE fields/AGC/sample-rate ppm or PER qualification. Three cases per frequency; not all seeds, signs or mismatch corners.'
    if transmit:
        report['scope']='Matched single/paired clock input with full internal switching, 240 mA RF budget, 500 pF, current package target, 1 V source, 0.025 ps/mV and both signs/mismatches. Native DAC, third-order reconstruction, upconversion and resistive output port at 20.48 GHz numerical rate. Warm driver with fixed current budget; no causal signal-dependent DAC/driver current, physical glitches, external filter, real framing, FIFO or standard emission-mask qualification. Broad band powers and diagnostic peer decoding only.'
    saved=b.MODE_CURRENT_A['rf']['timing']
    try:
        b.MODE_CURRENT_A['rf']['timing']=saved
        original=b.selected_environment(contract,'rf',carrier,carrier/16)
        original['internal_switching_loads']=[dict(owner='timing',mean_a=.010,event_hz=carrier/16,tau_s=.2e-9,harmonics=64),
            dict(owner='core',mean_a=.020,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)]
        _,base=b.single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False)
        variants=([(None,True),(dict(mismatch=.2,opposed=False,cm_gain=-.1),True),(dict(mismatch=.2,opposed=False,cm_gain=-.1),False)] if acquisition else
            [(opts,True) for opts in (None,dict(mismatch=.1,opposed=True,cm_gain=.1),dict(mismatch=.2,opposed=False,cm_gain=-.1))])
        for opts,wanted_present in variants:
            for sign in ((-1.,) if acquisition else (1.,-1.)):
                if opts is None:
                    e,clock=b.single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False,source_peak_v=1.,supply_sign=sign,sensitivity_ps_per_mv=.025)
                else:
                    e,clock=paired_environment(original,opts,sign=sign,sensitivity_ps_per_mv=.025,ledger=base['ledger'])
                row=dict(carrier_hz=carrier,frontend='single' if opts is None else 'paired',input_parameters=opts,supply_sign=sign,clock=clock,receiver=None)
                if e is not None:
                    if transmit:
                        row['transmitter']=b.wideband_transmit(e,oversample=1024)
                    elif acquisition:
                        from wideband_packet import run_acquisition_case
                        packet=run_acquisition_case(e,431,start_sample=137,carrier_offset_hz=-120e3,transmit=wanted_present,oversample=1024)
                        row['receiver']=packet.pop('analog');row['acquisition']=packet
                    else:
                        row['receiver']=b.coupled_wideband_feedback(e,wanted_dbm=-85.,gain_db=54.,oversample=1024)
                    if opts is not None and not transmit:
                        loads=[step['load'] for step in row['receiver']['iterations']]
                        row['causal_input_leg_bounds_v']=(np.array(clock['per_leg_bound_v'])+np.max([x['input_leg_voltage_abs_peak_v'] for x in loads],axis=0)).tolist()
                        row['causal_input_leg_envelope_met']=max(row['causal_input_leg_bounds_v'])<=.6
                report['cases'].append(row)
                write_report(output,report)
                print('Shared RF',carrier,opts,sign,'complete',flush=True)
    finally:
        b.MODE_CURRENT_A['rf']['timing']=saved
    if any(hashlib.sha256((p/name).read_bytes()).hexdigest()!=h for name,h in hashes.items()):raise RuntimeError('Sources changed during campaign')
    report['campaign_complete']=len(report['cases'])==report['expected_cases']
    write_report(output,report)
    return report


def shared_wake_campaign(carrier,output):
    sources=set(json.loads((p/'evidence/selected-baseline.json').read_text())['sources_sha256'])|{'verification/reference_input_probe.py'}
    hashes={name:hashlib.sha256((p/name).read_bytes()).hexdigest() for name in sorted(sources)}
    report=dict(cases=[],campaign_complete=False,expected_cases=6,sources_sha256=hashes,
        scope='240 mA full-mode budget, full internal pulses, 500 pF/current package target, 1 V source, negative 0.025 ps/mV. Single-ended and 20% aligned-mismatch paired input. Driver starts warm or ramps from 0 to its already-budgeted 28 mA at nominal source start, in 20 ns or 1 us. Coupled rail/input/reference/delay and available tail-current limit are applied. Early waveform is compared with matched warm output without fitting away phase/amplitude. No physical bias-readiness, RF switch, preamble, TX mask, signal-dependent DAC/driver current or protocol turnaround qualification.')
    saved=b.MODE_CURRENT_A['rf']['timing']
    try:
        b.MODE_CURRENT_A['rf']['timing']=saved
        original=b.selected_environment(contract,'rf',carrier,carrier/16)
        original['internal_switching_loads']=[dict(owner='timing',mean_a=.010,event_hz=carrier/16,tau_s=.2e-9,harmonics=64),dict(owner='core',mean_a=.020,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)]
        _,base=b.single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False)
        for opts in (None,dict(mismatch=.2,opposed=False,cm_gain=-.1)):
            if opts is None:
                e,clock=b.single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False,source_peak_v=1.,supply_sign=-1.,sensitivity_ps_per_mv=.025)
            else:e,clock=paired_environment(original,opts,sign=-1.,sensitivity_ps_per_mv=.025,ledger=base['ledger'])
            if e is None:raise ValueError('Wake clock rejected')
            warm={}
            for ramp in (None,20e-9,1e-6):
                trial=e;load=None;captured={}
                if ramp is not None:
                    response,load=b.driver_wake_response(e,released_current_a=.028,wake_start_s=2e-6,ramp_s=ramp,grid_s=.25e-9,reference_input=e.get('reference_load_parameters',{}))
                    trial=dict(e,local_load_response=response)
                tx=b.wideband_transmit(trial,oversample=1024,onset_capture=captured)
                if ramp is None:warm=captured
                np.testing.assert_array_equal(captured['times_s'],warm['times_s'])
                mask=(captured['times_s']>=2e-6)&(captured['times_s']<3e-6)
                relative=float(np.sqrt(np.sum(abs(captured['emitted_v'][mask]-warm['emitted_v'][mask])**2)/np.sum(abs(warm['emitted_v'][mask])**2)))
                row=dict(carrier_hz=carrier,frontend='single' if opts is None else 'paired',ramp_s=ramp,clock=clock,load=load,transmitter=tx,first_us_relative_waveform_error=relative)
                if opts is not None and load is not None:
                    bound=np.array(clock['per_leg_bound_v'])+load['input_leg_voltage_abs_peak_v']
                    row.update(input_leg_bound_v=bound.tolist(),input_leg_envelope_met=bool(max(bound)<=.6))
                report['cases'].append(row);write_report(output,report)
                print('Shared wake',carrier,opts,ramp,relative,flush=True)
    finally:b.MODE_CURRENT_A['rf']['timing']=saved
    if any(hashlib.sha256((p/name).read_bytes()).hexdigest()!=h for name,h in hashes.items()):raise RuntimeError('Sources changed during campaign')
    report['campaign_complete']=len(report['cases'])==6;write_report(output,report)


def write_report(path,report):
    normalized=json.loads(json.dumps(report,allow_nan=False,default=lambda value:value.item()))
    b.write_evidence(path,normalized)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--causal',action='store_true',help='Join SAR feedback at current package target; single-ended control uses 1 V peak')
    parser.add_argument('--output',type=Path,default=p/'evidence/reference-input-probe.json')
    parser.add_argument('--shared-internal',action='store_true')
    parser.add_argument('--shared-single',action='store_true')
    parser.add_argument('--shared-rf-mhz',type=int,choices=(2400,2484))
    parser.add_argument('--shared-acquisition-mhz',type=int,choices=(2400,2484))
    parser.add_argument('--shared-tx-mhz',type=int,choices=(2400,2484))
    parser.add_argument('--shared-wake-mhz',type=int,choices=(2400,2484))
    args=parser.parse_args()
    if args.shared_wake_mhz is not None:
        shared_wake_campaign(args.shared_wake_mhz*1e6,p/f'evidence/shared-input-wake-{args.shared_wake_mhz}.json')
        return
    if args.shared_tx_mhz is not None:
        shared_rf_campaign(args.shared_tx_mhz*1e6,p/f'evidence/shared-input-tx-{args.shared_tx_mhz}.json',transmit=True)
        return
    if args.shared_acquisition_mhz is not None:
        shared_rf_campaign(args.shared_acquisition_mhz*1e6,p/f'evidence/shared-input-acquisition-{args.shared_acquisition_mhz}.json',acquisition=True)
        return
    if args.shared_rf_mhz is not None:
        shared_rf_campaign(args.shared_rf_mhz*1e6,p/f'evidence/shared-input-rf-{args.shared_rf_mhz}.json')
        return
    validation=check_network()
    if args.check:
        print(json.dumps(validation,indent=2)); return
    if args.shared_internal or args.shared_single:
        report=shared_internal_campaign(single=args.shared_single);report['validation']=validation
        sources=set(json.loads((p/'evidence/selected-baseline.json').read_text())['sources_sha256'])|{'verification/reference_input_probe.py','verification/wired_lock_probe.py'}
        report['sources_sha256']={name:hashlib.sha256((p/name).read_bytes()).hexdigest() for name in sorted(sources)}
        write_report(p/('evidence/shared-single-internal.json' if args.shared_single else 'evidence/shared-input-internal.json'),report)
        return
    original=b.MODE_CURRENT_A['rf']['timing']
    try:
        b.MODE_CURRENT_A['rf']['timing']=original
        paired=paired_rf(args.causal)
        controls=single_rf(args.causal)
    finally:
        b.MODE_CURRENT_A['rf']['timing']=original
    baseline=json.loads((p/'evidence/selected-baseline.json').read_text())
    sources=set(baseline['sources_sha256'])|{'verification/reference_input_probe.py'}
    report=dict(validation=validation,paired=paired,single=controls,causal_requested=args.causal,
        scope='Unselected differential clock-input hypothesis. One extra functional signal, +4 mA timing bias charged to both comparisons, 1 V differential Thevenin peak; each leg 3 pF, 2 nH, 50.2 ohms, 0.4 nH mutual inductance. Opposed 10% or aligned 20% C/L mismatch, half that source resistance/amplitude mismatch, 5 ps leg skew, signed 20 dB common-mode rejection. The rf field is assigned ENOB. When requested, causal fields add SAR reference-load feedback at the 0.25 nH target for both differential probes and the 1 V single-ended control. No physical receiver bias/headroom, measured CMRR, direct pad crosstalk or protocol qualification. Two RF frequencies, two package cases, two supply-delay signs; not a continuous uncertainty bound.',
        sources_sha256={name:hashlib.sha256((p/name).read_bytes()).hexdigest() for name in sorted(sources)})
    args.output.write_text(json.dumps(report,indent=2,default=lambda v:v.item())+'\n')

if __name__=='__main__':main()
