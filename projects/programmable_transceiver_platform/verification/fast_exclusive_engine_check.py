"""Admission, enable exclusion and stopped RF/wired mode transitions."""
import argparse,hashlib,json,copy,math
from pathlib import Path
from types import MethodType
from fast_exclusive_engine import ExclusiveEngineChip,SwitchablePLL,PoweredExclusiveChip,IntegratedTransceiverChip
from fast_loaded_output import P
from managed_resources import command
from chip_model import encode_iq

def reject(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('Forbidden operation accepted')

def power_state_controls():
    c=SwitchablePLL(off_tau_s=1e-3)
    for i in range(1,401):c.advance(i/40e6);c.observe_lock()
    assert c.locked
    c.set_power(False,c.time)
    phase=c.output_phase_cycles;integral=c.integral;start=c.time
    split=copy.copy(c)
    c.advance(start+1e-3)
    for i in range(1,101):split.advance(start+i*1e-5)
    assert c.frequency_hz==0 and not c.observe_lock()
    assert abs(c.output_phase_cycles-phase)<1e-8
    assert abs(c.integral-integral/math.e)<1e-14
    assert abs(split.integral-c.integral)<1e-14
    assert abs(split.output_phase_cycles-c.output_phase_cycles)<1e-8
    reject(lambda:c.edge_time(phase+1))
    c.set_power(True,c.time)
    assert not c.locked and abs(c.output_phase_cycles-phase)<1e-8
    for i in range(1,801):c.advance(start+1e-3+i/40e6);c.observe_lock()
    assert c.locked and c.output_phase_cycles>phase
    return dict(stopped_phase_preserved=True,leakage_subdivision_invariant=True,
        off_edges_rejected=True,restart_requalified=True,off_tau_s=1e-3)

def clock_ownership_controls(chip_factory=ExclusiveEngineChip):
    def unlocked(pll):
        pll.locked=False
        return False
    rows=[]
    for engine in ('rf','wire'):
        c=chip_factory(watchdog_s=1e-3)
        c.select_engine(engine);c.configure(0,0.)
        selected=c.rf_pll if engine=='rf' else c.wire_pll
        inactive=c.wire_pll if engine=='rf' else c.rf_pll
        original=selected.observe_lock
        selected.observe_lock=MethodType(unlocked,selected)
        inactive.observe_lock=MethodType(unlocked,inactive)
        c.advance(8e-6)
        assert c.state=='acquiring' and not c.session.armed
        selected.observe_lock=original
        c.advance(c.time+8e-6)
        assert selected.locked and not inactive.locked and c.state=='active'
        assert c.session.enabled(engine)
        # Inject a lock-loss edge on the unused clock while payload is enabled.
        inactive.locked=True;c.advance(c.time+1e-6)
        assert not inactive.locked and c.state=='active'
        selected.observe_lock=MethodType(unlocked,selected)
        c.advance(c.time+1e-6)
        assert c.state=='draining' and not c.session.enabled(engine),(engine,c.state,c.session.armed,c.session.enabled(engine),c.events[-3:])
        rows.append(dict(engine=engine,selected_lock_required=True,
            inactive_unlock_ignored=True,selected_lock_loss_stops=True))
    return rows

def coupled_analog_screen():
    c=IntegratedTransceiverChip(coupled_analog=True,return_charge_per_transition=50e-15)
    c.select_engine('wire');c.configure(0,0.)
    c.quiesce(c.time,'boundary fixture preparation')
    c.acknowledge_host_abort(c.epoch,c.time);c.acknowledge_drain(c.epoch,c.time)
    c.select_engine('rf')
    c.advance(30e-9)
    owner=c.analog_owner;r=c.adc_reference
    assert c.dac_reference is r and c.output_network is owner.network
    assert c.tx.rx_bank is owner.rx_bank
    reject(lambda:r.advance(c.time+1e-9))
    # Exercise actual converter transfer and return-bus charge callbacks at one
    # boundary; no acquisition/calibration or sustained-traffic claim here.
    c.tx.apply_sample(.3+.1j,c.time)
    c.output_network.configure(True,False)
    assert r.dac_updates==1 and r.dac_charge>0
    before=owner.rail_v
    c.emitted_return_word(0xffff,c.time)
    assert abs(owner.rail_v-(before-17*50e-15/c.supply.c))<1e-14
    c.advance(60e-9)
    c.convert_adc(c.tx.received)
    assert r.samples==1 and r.charge>r.dac_charge
    assert abs(c.tx.received)>0 and abs(c.output_network.voltage[1])>0
    assert c.time==c.tx.time==owner.time==r.time==c.supply.time==c.tx_detector.time
    assert abs(c.supply.delta-(owner.rail_v-owner.law.nominal_v))<1e-14
    result=dict(status='passed',rf_scheduler=coupled_rf_scheduler_screen(),full_chip_closure=False,physical_qualification=False,
        time_s=c.time,rail_v=owner.rail_v,reference_v=r.voltage,
        received_magnitude=abs(c.tx.received),converter_charge_c=r.charge,
        host_return_charge_c=c.return_charge,shared_state_alignment=True,
        independent_reference_advance_rejected=True,
        limitations=['Finite boundary integration screen, not acquired payload or signal quality.',
        'RF rail feedback has a separate short scheduler check; integrated wired traffic is a separate test.',
        'Driver bias follows engine selection; shared reference bias is fixed and clock/converter/receiver operating currents remain incomplete.',
        'Lumped rail energy accounting is checked separately; full domain budgets, operating uncertainty and physical parameters remain unqualified.'])
    files=list((P/'system_model/connected').glob('*.py'))+list((P/'system_model/architecture_fast').glob('*.py'))+[Path(__file__),P/'verification/fast_loaded_output.py',P/'verification/fast_exclusive_engine.py']
    result['source_sha256']={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    (P/'evidence/fast-coupled-analog-integration.json').write_text(json.dumps(result,indent=2)+'\n')
    print({k:v for k,v in result.items() if k!='source_sha256'})

def coupled_rf_scheduler_screen():
    def build():
        c=IntegratedTransceiverChip(coupled_analog=True,rf_hz_per_v=1e8,
            return_charge_per_transition=50e-15)
        c.select_engine('rf')
        c.external_source([.2+.1j,-.1+.2j,.3-.1j],0.,7e-9)
        return c
    a=build();b=build()
    a.advance(20e-9)
    for t in (7e-9,14e-9,20e-9):b.advance(t)
    assert a.external_updates==b.external_updates==3
    assert a.tx.received!=0
    assert a.time==a.analog_owner.time==a.rf_pll.time==a.adc_reference.time
    assert abs(a.rf_pll.output_phase_cycles-b.rf_pll.output_phase_cycles)<1e-8
    assert abs(a.tx.received-b.tx.received)<1e-8
    phase=a.rf_pll.output_phase_cycles
    a.emitted_return_word(0xffff,a.time)
    assert a.rf_pll.output_phase_cycles==phase
    assert abs(a.rf_pll.rail_frequency(a.time)-a.rf_hz_per_v*a.supply.delta)<1e-6
    reject(lambda:a.rf_pll.edge_time(phase+1))
    a.advance(23e-9)
    assert a.rf_pll.output_phase_cycles>phase and a._analog_forecast is None
    return dict(external_updates=a.external_updates,intervals=a.feedback_intervals,
        maximum_iterations=a.feedback_max_iterations,
        aligned_analog_and_clock=True,host_impulse_preserves_phase=True,
        out_of_horizon_edge_rejected=True,full_payload_qualification=False)

def domain_chip_screen():
    import numpy as np
    from shared_supply_lifecycle import DomainSupply
    names=('CORE','HOST_A','HOST_B','WIRE_A','WIRE_B','RF','PLL')
    rows=[]
    for engine in ('rf','wire'):
        c=IntegratedTransceiverChip(coupled_analog=True,rf_hz_per_v=1e6,wire_hz_per_v=1e5,
            charge_per_transition=50e-15,return_charge_per_transition=50e-15,
            domain_supply=DomainSupply(names,[3.3]*7,[2.]*7,[100e-12]*7,.1),
            domain_minimum_v=[2.5]*7,domain_load=lambda t,v:[.02,.02,.02,0,0,.01,.008])
        c.select_engine(engine);c.advance(10e-9)
        o=c.analog_owner;d=o.domains
        assert c.time==o.time==d.time==c.rf_pll.time
        assert c.rf_pll.supply_trajectory.deltas[-1]==o.domain_trajectories['PLL'].deltas[-1]
        assert o.reference.driver_voltage==d.voltage[6]
        assert c.clock_supply_delta()==d.voltage[6]-d.nominal[6]
        assert abs(o.rail_v-d.voltage[5])<1e-12
        energy=d.source_energy_j-d.feed_loss_j-d.load_energy_j-.5*np.sum(d.c*(d.voltage**2-d.nominal**2))
        assert abs(energy)<1e-18
        before=(c.time,d.voltage.copy())
        reject(lambda:c.supply.draw(c.time,1e-15))
        assert c.time==before[0] and np.array_equal(d.voltage,before[1])
        before_v=d.voltage.copy();phase=c.rf_pll.output_phase_cycles
        c.emitted_return_word(31,c.time)
        expected=np.zeros(7);expected[1]=5*c.return_q/d.c[1];expected[2]=c.return_q/d.c[2]
        assert np.max(abs(before_v-d.voltage-expected))<1e-14
        assert c.rf_pll.output_phase_cycles==phase
        assert abs(c.return_charge-6*c.return_q)<1e-27 and abs(c.supply.charge-6*c.return_q)<1e-27
        c.advance(12e-9)
        energy=d.source_energy_j-d.feed_loss_j-d.load_energy_j-d.impulse_energy_j-.5*np.sum(d.c*(d.voltage**2-d.nominal**2))
        assert abs(energy)<1e-18 and d.impulse_energy_j>0
        rows.append(dict(engine=engine,voltage_v=d.voltage.tolist(),energy_residual_j=float(energy),intervals=c.feedback_intervals))
    return dict(cases=rows,scope='12 ns startup and one host output event; illustrative constant background loads',
        host_impulses_integrated=True,payload_qualified=False,physical_qualification=False)

def install_independent_rx(c):
    """Testbench antenna stimulus; preserve the selected physical filter bank.

    The old configure_rx command also retunes single-pole filters and is not
    applicable to this fixed multipole candidate. This selects the existing
    external receive path directly, not a newly qualified management command.
    """
    if c.session.armed:raise ValueError('External fixture requires disarmed setup')
    c.tx.advance(c.time)
    tones=[[.18,0.,2.5e6],[.04,0.,7.5e6]]
    offset=c.rf_target_hz-c.rf_carrier
    c.tx.rx_route='external_tone'
    c.tx.external_amplitude=complex(*tones[0][:2])
    c.tx.external_frequency=offset+tones[0][2]
    c.configure_rf_input([(complex(*row[:2]),offset+row[2]) for row in tones[1:]])
    return dict(tones=tones,enabled_time_s=c.time,target_hz=c.rf_target_hz,
        envelope_frame_hz=c.rf_carrier,testbench_route_selection=True)


def coupled_acquisition_screen(payload=False,domains=False,mode=0,independent_rx=False,noise_rms_hz=0.,physical_host=False,canonical=False):
    import time
    if not math.isfinite(noise_rms_hz) or noise_rms_hz<0:raise ValueError('Invalid RF noise')
    if (independent_rx or noise_rms_hz) and not (payload and domains):
        raise ValueError('Independent/noisy RF screen requires domain payload')
    if canonical and not physical_host:raise ValueError('Canonical model requires explicit host bank')
    if physical_host and not (payload and domains):raise ValueError('Host bank requires domain payload')
    start=time.monotonic()
    files=list((P/'system_model/connected').glob('*.py'))+list((P/'system_model/architecture_fast').glob('*.py'))+[Path(__file__),P/'verification/fast_loaded_output.py',P/'verification/fast_exclusive_engine.py',P/'verification/host_bank_supply.py',P/'verification/full_chip_model.py']
    hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    output=P/(('evidence/fast-domain-rf-mode1-payload.json' if mode==1 else 'evidence/fast-domain-rf-payload.json') if domains else 'evidence/fast-coupled-rf-calibrated-payload.json' if payload else 'evidence/fast-coupled-acquisition.json')
    if independent_rx or noise_rms_hz:
        output=P/f'evidence/fast-domain-rf-{"external" if independent_rx else "loopback"}-mode{mode}-noise{noise_rms_hz:g}-payload.json'
    if physical_host:output=output.with_name(output.name.replace('fast-domain-rf','fast-host-bank-rf'))
    if canonical:output=output.with_name(output.name.replace('fast-host-bank-rf','canonical-rf'))
    progress=dict(status='running',stage='acquisition',source_sha256=hashes,
        full_chip_closure=False,physical_qualification=False)
    def save():output.write_text(json.dumps(progress,indent=2)+'\n')
    save()
    options={};domain_fixture=None
    if domains:
        from shared_supply_lifecycle import DomainSupply
        names=('CORE','HOST_A','HOST_B','WIRE_A','WIRE_B','RF','PLL')
        background=[.02,.002,.002,0,0,.012,.008] if physical_host else [.02,.02,.02,0,0,.012,.008]
        domain_fixture=dict(names=list(names),feed_r_ohm=2.,capacitance_f=100e-12,
            common_return_r_ohm=.1,background_current_a=background,complete_current_inventory=False)
        options=dict(domain_supply=DomainSupply(names,[3.3]*7,[2.]*7,[100e-12]*7,.1),
            domain_minimum_v=[2.5]*7,domain_load=lambda t,v:background,return_charge_per_transition=0. if physical_host else 50e-15)
        progress['domain_fixture']=domain_fixture;save()
    if physical_host:
        from host_bank_supply import LimitedHostBankSupply
        options['host_bank']=LimitedHostBankSupply([3.3]*7,[2.]*7,[100e-12]*7,.1,
            [1]*5+[2]*6,[10e-12]*11,[100.]*11,[80.]*11,
            pullup_limit_a=[.01]*11,pulldown_limit_a=[.012]*11,
            rising_charge_c=[7e-12]*11,falling_charge_c=[7e-12]*11,
            switching_tau_s=.5e-9,minimum_supply_v=[2.5]*7)
        progress['physical_host_fixture']=dict(capacitance_f=10e-12,pullup_r_ohm=100.,
            pulldown_r_ohm=80.,pullup_limit_a=.01,pulldown_limit_a=.012,
            internal_charge_per_edge_c=7e-12,switching_tau_s=.5e-9,
            electrical_timing_qualified=False)
    from oscillator_noise import FrequencyNoise
    noise=FrequencyNoise.seeded(noise_rms_hz,seed=839)
    if canonical:
        from full_chip_model import make_chip
        c=make_chip(rf_noise_rms_hz=noise_rms_hz)
    else:
        c=IntegratedTransceiverChip(coupled_analog=True,rf_hz_per_v=1e6,watchdog_s=1e-3,tx_relative_gain=payload,
            rf_noise_rms_hz=noise_rms_hz,noise_seed=839,coarse_noise_bound_hz=noise.bound_hz,**options)
    progress['oscillator_noise']=dict(rms_hz=noise_rms_hz,tones=noise.tones,bound_hz=noise.bound_hz,
        scope='Assumed finite spectral frequency-noise realization, not a measured device spectrum')
    save()
    c.select_engine('rf')
    c.execute_management('rf_coarse_start',2437000000,c.time)
    rows=[]
    for tick in range(1,41):
        c.advance(tick*1e-6)
        rows.append(dict(time_s=c.time,coarse_state=c.coarse.state,locked=c.rf_pll.locked,
            rail_v=c.analog_owner.rail_v,reference_v=c.adc_reference.voltage))
        progress.update(acquisition=rows,elapsed_s=time.monotonic()-start);save()
        print(dict(elapsed_s=time.monotonic()-start,**rows[-1]),flush=True)
        if c.coarse.qualified and c.rf_pll.locked:break
    assert c.coarse.qualified and c.rf_pll.locked, rows[-1]
    calibration=None
    rx_calibration=[]
    if payload:
        progress.update(stage='receiver_calibration',acquisition=rows);save()
        for target in (0,1):
            c.execute_management('cal_start',9|(target<<16),c.time)
            deadline=c.time+10e-6
            while c.cal.busy and c.time<deadline:
                c.advance(min(c.time+225e-9,deadline))
            assert c.cal.state=='done',c.cal.result
            rx_calibration.append(dict(target=target,code=c.trim.code,
                result=c.cal.result,observations=list(c.maintenance_trace)))
            progress['rx_calibration']=rx_calibration;save()
            print(dict(stage='receiver_calibration',target=target,result=c.cal.result),flush=True)
        c.configure_rx_gain(2.)
        progress.update(stage='calibration',acquisition=rows);save()
        reply=c.execute_management('tx_cal_start',0,c.time)
        while c.tx_cal.next_event is not None:
            c.advance(c.tx_cal.next_event)
            print(dict(stage='calibration',time_s=c.time,state=c.tx_cal.state,
                probes=len(c.tx_cal.powers),elapsed_s=time.monotonic()-start),flush=True)
            progress['calibration_state']=dict(state=c.tx_cal.state,powers=c.tx_cal.powers,
                reason=getattr(c.tx_cal,'reason',None));save()
        if c.tx_cal.state!='ready':
            progress.update(status='failed',stage='calibration');save()
            raise AssertionError(progress['calibration_state'])
        c.execute_management('tx_cal_commit',reply['value'],c.time)
        calibration=dict(powers=list(c.tx_cal.powers),valid=c.tx_cal.valid,shared_adc_samples=c.tx_adc_samples)
        import cmath
        values=[.18*cmath.exp(2j*math.pi*i/16)+.04*cmath.exp(2j*math.pi*i/4) for i in range(32)]
        for i,value in enumerate(values):c.write_playback(i,encode_iq(value,12 if mode==0 else 8))
        c.select_playback(True);c.configure_capture(True)
        progress.update(stage='payload',calibration=calibration);save()
    external=install_independent_rx(c) if independent_rx else None
    c.configure(mode,c.time);c.advance(c.time+3e-6)
    assert c.state=='active' and c.session.enabled('rf') and not c.session.enabled('wire')
    assert c.time==c.rf_pll.time==c.analog_owner.time==c.tx.time
    payload_result=None
    if payload:
        c.tx_probe.clear();c.probe_times.clear()
        observations=[];original=c.convert_adc
        def observe(value):
            observations.append(dict(time_s=c.tx.time,receiver_real=value.real,receiver_imag=value.imag,
                rx_lo_phase_rad=2*math.pi*c.tx.rx_lo_hz*c.tx.time+c.tx.rx_lo_phase))
            return original(value)
        c.convert_adc=observe
        c.execute_management('start_local',3|(32<<2)|(8<<18),c.time)
        c.advance(c.time+5e-6)
        assert len(c.adc_words)==32 and c.tx.consumed==32 and c.capture_bank.done
        assert [c.capture_bank.read(i) for i in range(32)]==c.adc_words
        assert any(c.adc_words) and c.tx_cal.valid and c.state=='active'
        c.dac_accounting();c.adc_accounting()
        payload_result=dict(sample_words=c.adc_words,desired_iq=[[z.real,z.imag] for z in values],
            pad_iq=[[z.real,z.imag] for z in c.tx_probe],observations=observations,
            played=[[t,z.real,z.imag] for t,z in c.played],sample_rate_hz=40e6 if mode==0 else 20e6,mode=mode,bits_per_component=c.bits,
            rx_gain=c.rx_gain,capture_gain=c.gain,signal_quality_qualified=False)
        if external:payload_result['independent_rx']=external
    report=dict(status='passed',elapsed_s=time.monotonic()-start,acquisition=rows,calibration=calibration,rx_calibration=rx_calibration,payload=payload_result,
        oscillator_noise=progress['oscillator_noise'],
        active_time_s=c.time,feedback_intervals=c.feedback_intervals,
        full_chip_closure=False,physical_qualification=False,
        limitations=['One RF carrier acquisition with assumed 1 MHz/V rail sensitivity.',
            'Optional payload is a 32-sample diagnostic; held-out signal quality, full lifecycle and physical qualification remain open.'])
    files=list((P/'system_model/connected').glob('*.py'))+list((P/'system_model/architecture_fast').glob('*.py'))+[Path(__file__),P/'verification/fast_loaded_output.py',P/'verification/fast_exclusive_engine.py',P/'verification/host_bank_supply.py',P/'verification/full_chip_model.py']
    report['source_sha256']=hashes
    if domains:
        import numpy as np
        d=c.analog_owner.domains
        stored=.5*float(np.sum(d.c*(d.voltage**2-d.nominal**2)))
        if physical_host:
            h=c.analog_owner.host_bank
            stored=h.cap_energy()-h.initial_energy
            assert h.time==c.time and h.injected_charge.sum()>0
            assert max(abs(h.injected_charge-h.consumed_charge-h.pending_charge))<1e-21
            report['physical_host_fixture']=progress['physical_host_fixture']
            report['physical_host_result']=dict(internal_charge_c=float(h.injected_charge.sum()),return_word_edges=c.return_ticks)
            report['limitations'].append('Host voltage timing is not sampled by an external receiver; pad parameters and background currents remain hypotheses.')
        residual=d.source_energy_j-d.feed_loss_j-d.load_energy_j-d.impulse_energy_j-stored
        assert abs(residual)<1e-15
        report['domain_fixture']=domain_fixture
        report['domain_result']=dict(voltage_v=d.voltage.tolist(),energy_residual_j=residual,host_return_charge_c=c.return_charge)
        report['limitations'].append('Illustrative domain impedance and background current inventory; not a power-budget or package qualification.')
    assert all(hashlib.sha256((P/n).read_bytes()).hexdigest()==h for n,h in hashes.items()), 'Sources changed during run'
    if canonical:
        from full_chip_model import parameters
        report['canonical_model']=parameters()
    output.write_text(json.dumps(report,indent=2)+'\n')
    print({k:v for k,v in report.items() if k not in ('source_sha256','acquisition')},flush=True)

def coupled_wire_screen(domains=False, physical_host=False, canonical=False):
    import time
    if canonical and not physical_host:raise ValueError('Canonical model requires explicit host bank')
    if physical_host and not domains:raise ValueError('Physical host requires domains')
    files=list((P/'system_model/connected').glob('*.py'))+list((P/'system_model/architecture_fast').glob('*.py'))+[Path(__file__),P/'verification/fast_loaded_output.py',P/'verification/fast_exclusive_engine.py',P/'verification/host_bank_supply.py',P/'verification/full_chip_model.py']
    hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    rows=[];started=time.monotonic()
    for mode in (0,1):
        options={}
        if domains:
            from shared_supply_lifecycle import DomainSupply
            names=('CORE','HOST_A','HOST_B','WIRE_A','WIRE_B','RF','PLL')
            options=dict(domain_supply=DomainSupply(names,[3.3]*7,[2.]*7,[100e-12]*7,.1),
                domain_minimum_v=[2.5]*7,domain_load=lambda t,v:[.02,.02,.02,0,.005,0,.008])
        if physical_host:
            from host_bank_supply import LimitedHostBankSupply
            options['domain_load']=lambda t,v:[.02,.002,.002,0,.005,0,.008]
            options['host_bank']=LimitedHostBankSupply([3.3]*7,[2.]*7,[100e-12]*7,.1,
                [1]*5+[2]*6,[10e-12]*11,[100.]*11,[80.]*11,
                pullup_limit_a=[.01]*11,pulldown_limit_a=[.012]*11,
                rising_charge_c=[7e-12]*11,falling_charge_c=[7e-12]*11,
                switching_tau_s=.5e-9,minimum_supply_v=[2.5]*7)
        if canonical:
            from full_chip_model import make_chip
            c=make_chip()
        else:
            c=IntegratedTransceiverChip(coupled_analog=True,wire_hz_per_v=1e5,
                return_charge_per_transition=0. if physical_host else 50e-15,watchdog_s=1e-3,**options)
        c.select_engine('wire');c.configure(mode,0.)
        c.advance(8e-6)
        assert c.state=='active' and c.wire_pll.locked
        assert not c.rf_pll.powered and abs(c.output_network.voltage[1])<1e-12
        c.start_wire_return(c.time+20e-9)
        tx=[17,801,0,1023,511,7];rx=[(29*i+7)%1024 for i in range(64)]
        for word in tx:c.accept_wire(word)
        start=c.time+30e-9;c.schedule_wire(len(tx),start);c.incoming_wire(rx,start,.3,0)
        c.advance(c.time+2e-6)
        assert c.wired_output==tx and c.host_wire==rx and c.state=='active'
        assert c.oscillator_supply_events>0
        assert c.analog_owner.host_bank.injected_charge.sum()>0 if physical_host else c.return_charge>0
        assert not c.adc_words and c.adc_reference.samples==0
        assert c.time==c.analog_owner.time==c.wire_pll.time==c.rf_pll.time
        c.wire_accounting()
        owner=c.analog_owner
        if domains:
            import numpy as np
            d=owner.domains
            assert d.time==c.time
            assert d.impulse_energy_j==0 if physical_host else d.impulse_energy_j>0
            stored=.5*float(np.sum(d.c*(d.voltage**2-d.nominal**2)))
        else:stored=.5*owner.c*(owner.rail_v**2-owner.law.nominal_v**2)
        if physical_host:stored=owner.host_bank.cap_energy()-owner.host_bank.initial_energy
        residual=owner.source_energy_j-owner.rail_resistor_energy_j-owner.load_energy_j-owner.impulse_energy_j-stored
        assert abs(residual)<1e-16 and owner.extra_load_energy_j>0
        rows.append(dict(mode=mode,tx_words=len(tx),host_rx_words=len(rx),return_charge_c=c.return_charge,
            rail_v=owner.rail_v,feedback_intervals=c.feedback_intervals,rf_oscillator_off=True,
            wired_power_parameters=c.wired_power_parameters,additional_load_energy_j=owner.extra_load_energy_j,
            rail_energy_residual_j=residual,source_energy_j=owner.source_energy_j))
        if physical_host:
            h=owner.host_bank
            assert max(abs(h.injected_charge-h.consumed_charge-h.pending_charge))<1e-22
            rows[-1].update(internal_host_charge_c=float(h.injected_charge.sum()),host_output_v=h.state[7:].tolist())
        print(dict(elapsed_s=time.monotonic()-started,**rows[-1]),flush=True)
    assert all(hashlib.sha256((P/name).read_bytes()).hexdigest()==value for name,value in hashes.items()), 'Sources changed during run'
    report=dict(status='passed',cases=rows,full_chip_closure=False,physical_qualification=False,
        source_sha256=hashes,
        limitations=['Assumed regulated wired swing/termination efficiency and bias; gate switching charge, output compliance and clock/converter bias remain open.',
        'Short finite bursts, not full throughput or protocol compliance; RF bias gating and physical parameters remain open.'])
    if domains:
        report['domain_fixture']=dict(names=list(names),feed_r_ohm=2.,capacitance_f=100e-12,
            common_return_r_ohm=.1,minimum_v=2.5,background_current_a=[.02,.002,.002,0,.005,0,.008] if physical_host else [.02,.02,.02,0,.005,0,.008],
            complete_current_inventory=False)
        report['limitations'].append('Illustrative domain parameters and background currents; no full-chip power qualification.')
    if physical_host:
        report['physical_host_fixture']=dict(output_capacitance_f=10e-12,pullup_r_ohm=100.,pulldown_r_ohm=80.,pullup_limit_a=.01,pulldown_limit_a=.012,internal_charge_per_edge_c=7e-12,switching_tau_s=.5e-9)
        report['limitations'].append('Exploratory output law; host electrical timing, propagation delay and complete current inventory unqualified.')
    if canonical:
        from full_chip_model import parameters
        report['canonical_model']=parameters()
    (P/('evidence/canonical-wire.json' if canonical else 'evidence/fast-host-bank-wire.json' if physical_host else 'evidence/fast-domain-wire.json' if domains else 'evidence/fast-coupled-wire.json')).write_text(json.dumps(report,indent=2)+'\n')

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    parser=argparse.ArgumentParser();parser.add_argument('--power-gated',action='store_true')
    parser.add_argument('--integrated',action='store_true')
    parser.add_argument('--canonical',action='store_true')
    parser.add_argument('--domain-chip-screen',action='store_true')
    parser.add_argument('--domain-wire-screen',action='store_true')
    parser.add_argument('--host-bank-wire-screen',action='store_true')
    parser.add_argument('--domain-rf-screen',action='store_true')
    parser.add_argument('--host-bank-rf',action='store_true')
    parser.add_argument('--rf-mode',type=int,choices=(0,1),default=0)
    parser.add_argument('--independent-rx',action='store_true')
    parser.add_argument('--rf-noise-rms-hz',type=float,default=0.)
    parser.add_argument('--coupled-analog-screen',action='store_true')
    parser.add_argument('--coupled-acquisition-screen',action='store_true')
    parser.add_argument('--coupled-wire-screen',action='store_true')
    parser.add_argument('--coupled-rf-payload-screen',action='store_true')
    args=parser.parse_args()
    if args.canonical and not (args.host_bank_wire_screen or (args.domain_rf_screen and args.host_bank_rf)):
        parser.error('--canonical requires host-bank wired or RF screen')
    if args.host_bank_rf and not args.domain_rf_screen:parser.error('--host-bank-rf requires --domain-rf-screen')
    if (args.independent_rx or args.rf_noise_rms_hz) and not args.domain_rf_screen:
        parser.error('Independent input/noise options require --domain-rf-screen')
    if args.domain_rf_screen:return coupled_acquisition_screen(payload=True,domains=True,mode=args.rf_mode,
        independent_rx=args.independent_rx,noise_rms_hz=args.rf_noise_rms_hz,physical_host=args.host_bank_rf,canonical=args.canonical)
    if args.host_bank_wire_screen:return coupled_wire_screen(domains=True,physical_host=True,canonical=args.canonical)
    if args.domain_wire_screen:return coupled_wire_screen(domains=True)
    if args.domain_chip_screen:
        print(domain_chip_screen());return
    if args.coupled_rf_payload_screen:return coupled_acquisition_screen(payload=True)
    if args.coupled_wire_screen:return coupled_wire_screen()
    if args.coupled_acquisition_screen:return coupled_acquisition_screen()
    if args.coupled_analog_screen:return coupled_analog_screen()
    if args.integrated:args.power_gated=True
    chip_factory=IntegratedTransceiverChip if args.integrated else PoweredExclusiveChip if args.power_gated else ExclusiveEngineChip
    power_case=power_state_controls()
    clock_cases=[] if args.integrated else clock_ownership_controls(chip_factory)
    c=chip_factory(watchdog_s=1e-3,tx_relative_gain=True);reject(lambda:c.configure(0,0.))
    bank=copy.deepcopy(c.tx.rx_bank)
    c.configure_rx_gain(2.);assert c.tx.rx_bank==bank
    for code,gain in enumerate((.5,1.,2.)):
        assert command(c,'configure_rx_gain',code)['accepted'] and c.rx_gain==gain
    assert all(c.tx.rx_bank[k]==bank[k] for k in ('poles','weights','cutoff_hz'))
    assert not command(c,'configure_rx_gain',3)['accepted'] and c.rx_gain==2.
    reject(lambda:c.configure_rx_gain(float('nan')))
    rows=[]
    for engine,mode in (('rf',0),('wire',0),('rf',1),('wire',1)):
        c.select_engine(engine);assert not c.tx_cal.valid
        if args.integrated:assert not c.coarse.qualified
        c.reset_memory()
        if engine=='rf':
            if args.integrated:
                target=2437000000 if mode==0 else 2500000000
                assert command(c,'rf_coarse_start',target)['accepted']
                c.advance(c.time+35e-6)
                assert c.coarse.qualified and c.rf_pll.locked and c.rf_target_hz==target
            c.advance(c.time+8e-6)
            reply=command(c,'tx_cal_start');assert reply['accepted']
            reject(lambda:c.configure_rx_gain(1.))
            c.advance(c.time+25e-6)
            assert command(c,'tx_cal_commit',reply['value'])['accepted']
            bits=12 if mode==0 else 8
            for i in range(32):c.write_playback(i,encode_iq(complex((i%7-3)/16,.1),bits))
            c.select_playback(True);c.configure_capture(True)
        c.configure(mode,c.time);c.advance(c.time+8e-6)
        assert c.state=='active'
        if args.power_gated:
            inactive=c.wire_pll if engine=='rf' else c.rf_pll
            phase=inactive.output_phase_cycles
            c.advance(c.time+100e-9)
            assert not inactive.powered and inactive.frequency_hz==0
            assert abs(inactive.output_phase_cycles-phase)<1e-8
        reject(lambda:c.configure_rx_gain(1.));assert c.rx_gain==2.
        other='wire' if engine=='rf' else 'rf'
        assert c.session.enabled(engine) and not c.session.enabled(other)
        reject(lambda:c.select_engine(other))
        if engine=='rf':
            accepted=c.wire_accepted;queued=list(c.wire_queue)
            reject(lambda:c.accept_wire(17))
            assert c.wire_accepted==accepted and list(c.wire_queue)==queued
            reject(lambda:c.execute_management('wire_return_start',8,c.time))
            reject(lambda:c.schedule_wire(32,c.time+1e-6))
            reject(lambda:c.incoming_wire([1],c.time+1e-6))
            before=len(c.adc_words);consumed=c.tx.consumed
            assert command(c,'start_local',3|(32<<2)|(8<<18))['accepted']
            c.advance(c.time+5e-6)
            assert len(c.adc_words)-before==32 and c.tx.consumed-consumed==32
            assert c.capture_bank.done and c.play_index==32
            assert [c.capture_bank.read(i) for i in range(32)]==c.adc_words[before:]
            assert any(c.adc_words[before:])
            assert c.output_network.output_on and not c.output_network.dummy_on
        else:
            if args.integrated:assert not command(c,'rf_coarse_start',2437000000)['accepted']
            before=c.decoder
            reject(lambda:c.descriptor(32))
            reject(lambda:c.execute_management('start_local',3|(32<<2)|(1<<18),c.time))
            assert c.decoder is before and c.remaining==0
            reject(lambda:c.capture(32,c.time+1e-6));reject(lambda:c.schedule(32,c.time+1e-6))
            reject(lambda:c.execute_management('tx_cal_start',0,c.time))
            assert command(c,'detect_rearm')['accepted']
            assert command(c,'wire_return_start',8)['accepted']
            assert not command(c,'wire_return_start',8)['accepted']
            tx_words=[(i*37+11)%1024 for i in range(32)]
            rx_words=[(i*43+17)%1024 for i in range(64)]
            tx_before=len(c.wired_output);rx_before=len(c.host_wire)
            adc_before=len(c.adc_words)
            for word in tx_words:c.accept_wire(word)
            start=c.time+100e-9;c.schedule_wire(len(tx_words),start)
            c.incoming_wire(rx_words,start,.3,0)
            c.advance(c.time+3e-6)
            assert c.live_rx.done and c.wired_output[tx_before:]==tx_words
            assert c.host_wire[rx_before:]==rx_words and len(c.adc_words)==adc_before
            c.wire_accounting()
        assert command(c,'stop')['accepted']
        assert command(c,'ack_abort')['accepted'] and command(c,'ack_drain')['accepted']
        assert c.state=='reset' and not c.session.armed
        rows.append(dict(engine=engine,mode=mode,opposite_engine_rejected=True,ingress_rejection_atomic=True,rf_duplex_samples=32 if engine=='rf' else 0,wire_tx_words=32 if engine=='wire' else 0,wire_host_rx_words=64 if engine=='wire' else 0,stopped=True))
    c.select_engine('none');reject(lambda:c.configure(0,c.time))
    reference_metrics=None
    if args.integrated:
        r=c.adc_reference
        assert c.dac_reference is r and r.dac_updates>0 and r.samples>0
        residual=r.recharge_c-r.absorbed_c-r.charge-r.c*(r.voltage-1.)
        assert abs(residual)<1e-21
        reference_metrics=dict(source_limit_a=r.source_current_limit,sink_limit_a=r.sink_current_limit,
            minimum_v=r.minimum,peak_current_a=r.peak_current_a,limited_s=r.limited_s,
            recharge_c=r.recharge_c,conversion_charge_c=r.charge,charge_residual_c=residual)
    files=list((P/'system_model/connected').glob('*.py'))+list((P/'system_model/architecture_fast').glob('*.py'))+[P/'verification'/n for n in ('fast_loaded_output.py','fast_exclusive_engine.py','fast_exclusive_engine_check.py')]
    out=dict(status='passed',finite_reference=reference_metrics,integrated=args.integrated,power_gated=args.power_gated,standalone_power_state=power_case,clock_ownership=clock_cases,source_sha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},cases=rows,
        limitations=['Power-gated variant checks oscillator shutdown; physical bias-current and settling behavior remain open.',
        'Python selection API with serialized local-start command; pin-level management/RTL interlock not implemented.',
        'Finite RF TX/RX and wired TX/host RX checked; sustained duplex, RF quality and calibration validity across mode changes need further coverage.'])
    (P/('evidence/fast-integrated-engine.json' if args.integrated else 'evidence/fast-powered-exclusive-engine.json' if args.power_gated else 'evidence/fast-exclusive-engine.json')).write_text(json.dumps(out,indent=2)+'\n');print(rows)
if __name__=='__main__':main()
