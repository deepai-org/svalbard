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
    reject(lambda:IntegratedTransceiverChip(coupled_analog=True,wire_hz_per_v=1e6))
    c.select_engine('wire');c.configure(0,0.)
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
        'RF rail feedback has a separate short scheduler check; wired PLL sensitivity remains rejected.',
        'Driver/reference bias is fixed, including inactive engines; power gating is not yet modeled.',
        'Whole-rail energy accounting, operating uncertainty and physical parameters remain unqualified.'])
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

def coupled_acquisition_screen():
    import time
    start=time.monotonic()
    c=IntegratedTransceiverChip(coupled_analog=True,rf_hz_per_v=1e6,watchdog_s=1e-3)
    c.select_engine('rf')
    c.execute_management('rf_coarse_start',2437000000,c.time)
    rows=[]
    for tick in range(1,41):
        c.advance(tick*1e-6)
        rows.append(dict(time_s=c.time,coarse_state=c.coarse.state,locked=c.rf_pll.locked,
            rail_v=c.analog_owner.rail_v,reference_v=c.adc_reference.voltage))
        if tick%5==0:print(dict(elapsed_s=time.monotonic()-start,**rows[-1]),flush=True)
        if c.coarse.qualified and c.rf_pll.locked:break
    assert c.coarse.qualified and c.rf_pll.locked, rows[-1]
    c.configure(0,c.time);c.advance(c.time+3e-6)
    assert c.state=='active' and c.session.enabled('rf') and not c.session.enabled('wire')
    assert c.time==c.rf_pll.time==c.analog_owner.time==c.tx.time
    report=dict(status='passed',elapsed_s=time.monotonic()-start,acquisition=rows,
        active_time_s=c.time,feedback_intervals=c.feedback_intervals,
        full_chip_closure=False,physical_qualification=False,
        limitations=['One RF carrier acquisition with assumed 1 MHz/V rail sensitivity.',
            'No calibrated payload, full mode lifecycle, wired supply feedback or physical qualification.'])
    files=list((P/'system_model/connected').glob('*.py'))+list((P/'system_model/architecture_fast').glob('*.py'))+[Path(__file__),P/'verification/fast_loaded_output.py',P/'verification/fast_exclusive_engine.py']
    report['source_sha256']={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    (P/'evidence/fast-coupled-acquisition.json').write_text(json.dumps(report,indent=2)+'\n')
    print({k:v for k,v in report.items() if k not in ('source_sha256','acquisition')},flush=True)

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    parser=argparse.ArgumentParser();parser.add_argument('--power-gated',action='store_true')
    parser.add_argument('--integrated',action='store_true')
    parser.add_argument('--coupled-analog-screen',action='store_true')
    parser.add_argument('--coupled-acquisition-screen',action='store_true')
    args=parser.parse_args()
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
