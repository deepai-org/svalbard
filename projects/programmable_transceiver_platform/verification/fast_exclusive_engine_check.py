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

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    parser=argparse.ArgumentParser();parser.add_argument('--power-gated',action='store_true')
    parser.add_argument('--integrated',action='store_true')
    args=parser.parse_args()
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
