"""Admission, enable exclusion and stopped RF/wired mode transitions."""
import hashlib,json,copy
from pathlib import Path
from types import MethodType
from fast_exclusive_engine import ExclusiveEngineChip
from fast_loaded_output import P
from managed_resources import command
from chip_model import encode_iq

def reject(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('Forbidden operation accepted')

def clock_ownership_controls():
    def unlocked(pll):
        pll.locked=False
        return False
    rows=[]
    for engine in ('rf','wire'):
        c=ExclusiveEngineChip(watchdog_s=1e-3)
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
    clock_cases=clock_ownership_controls()
    c=ExclusiveEngineChip(watchdog_s=1e-3,tx_relative_gain=True);reject(lambda:c.configure(0,0.))
    bank=copy.deepcopy(c.tx.rx_bank)
    c.configure_rx_gain(2.);assert c.tx.rx_bank==bank
    for code,gain in enumerate((.5,1.,2.)):
        assert command(c,'configure_rx_gain',code)['accepted'] and c.rx_gain==gain
    assert all(c.tx.rx_bank[k]==bank[k] for k in ('poles','weights','cutoff_hz'))
    assert not command(c,'configure_rx_gain',3)['accepted'] and c.rx_gain==2.
    reject(lambda:c.configure_rx_gain(float('nan')))
    rows=[]
    for engine,mode in (('rf',0),('wire',1),('rf',1)):
        c.select_engine(engine);assert not c.tx_cal.valid
        c.reset_memory()
        if engine=='rf':
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
        reject(lambda:c.configure_rx_gain(1.));assert c.rx_gain==2.
        other='wire' if engine=='rf' else 'rf'
        assert c.session.enabled(engine) and not c.session.enabled(other)
        reject(lambda:c.select_engine(other))
        if engine=='rf':
            accepted=c.wire_accepted;queued=list(c.wire_queue)
            reject(lambda:c.accept_wire(17))
            assert c.wire_accepted==accepted and list(c.wire_queue)==queued
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
            before=c.decoder
            reject(lambda:c.descriptor(32))
            reject(lambda:c.execute_management('start_local',3|(32<<2)|(1<<18),c.time))
            assert c.decoder is before and c.remaining==0
            reject(lambda:c.capture(32,c.time+1e-6));reject(lambda:c.schedule(32,c.time+1e-6))
            reject(lambda:c.execute_management('tx_cal_start',0,c.time))
            c.incoming_wire([i%1024 for i in range(64)],c.time+100e-9,.3,0)
            c.advance(c.time+3e-6)
            assert c.live_rx.done
        assert command(c,'stop')['accepted']
        assert command(c,'ack_abort')['accepted'] and command(c,'ack_drain')['accepted']
        assert c.state=='reset' and not c.session.armed
        rows.append(dict(engine=engine,mode=mode,opposite_engine_rejected=True,ingress_rejection_atomic=True,rf_duplex_samples=32 if engine=='rf' else 0,stopped=True))
    c.select_engine('none');reject(lambda:c.configure(0,c.time))
    files=list((P/'system_model/connected').glob('*.py'))+list((P/'system_model/architecture_fast').glob('*.py'))+[P/'verification'/n for n in ('fast_loaded_output.py','fast_exclusive_engine.py','fast_exclusive_engine_check.py')]
    out=dict(status='passed',clock_ownership=clock_cases,source_sha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},cases=rows,
        limitations=['Payload admission/session enables only; inactive clock and bias shutdown remain open.',
        'Python selection API with serialized local-start command; pin-level management/RTL interlock not implemented.',
        'Finite 32-sample RF TX/RX and wired receive checked; sustained duplex, RF quality and calibration validity across mode changes need further coverage.'])
    (P/'evidence/fast-exclusive-engine.json').write_text(json.dumps(out,indent=2)+'\n');print(rows)
if __name__=='__main__':main()
