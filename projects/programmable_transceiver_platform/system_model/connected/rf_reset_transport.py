"""RF reset across actual host frames, preserving independent wired traffic.

Candidate management contract: host stops old RF production, acknowledges its
last old frame, and waits for the chip's drain acknowledgement before restarting.
The acknowledgement is an abstract coherent sideband, not implemented SPI/CDC.
"""
import hashlib
import json
import math
from pathlib import Path
from chip_model import Packer, encode_iq, decode_iq, Receiver, encode, slots, P
from rf_tx_state import RfTxState, controls
from session import Session


def run(mode, reset_position, unsafe_rearm=False, active=False):
    bits, word_rate, fs = (12, 250e6, 40e6) if mode == 0 else (8, 312.5e6, 20e6)
    width = 2 * bits
    session = Session()
    session.configure(mode)
    session.host_ready = True
    session.ready.update(rf=True, wire=True)
    session.arm()
    tx = RfTxState(session, 128)
    receiver = Receiver(mode)
    plan = slots(mode)
    packer = Packer()
    old, new = [], []
    for target, sign in ((old, 1), (new, -1)):
        for i in range(50):
            target.extend(packer.push(encode_iq(sign * (.25 + i / 512), bits), width, 10))
        assert packer.count == 0
    old_frames = math.ceil(len(old) / plan.count('iq'))
    new_frames = math.ceil(len(new) / plan.count('iq'))
    unpack_value = unpack_count = 0
    wires, expected_wires = [], []
    accepted_after_reset = []
    reset_tick = (256 if active else 64) + reset_position
    barrier_tick = old_frames * 64
    held_at_reset = None
    consumed_before_reset = None
    decay_error = None
    peak = 0
    next_sample = 192.0
    # Old traffic is never edited after reset: it really drains through framing.
    for frame_index in range(old_frames + new_frames):
        if frame_index == old_frames:
            assert receiver.pos == 0 and not receiver.fault
            assert unpack_count == 0
            # Sideband host acknowledgement names this last old frame. A timer
            # alone cannot establish that old producer/transport queues drained.
            tx.advance(barrier_tick / word_rate)
            if not unsafe_rearm:
                expected = held_at_reset * math.exp(-tx.pole * (barrier_tick-reset_tick)/word_rate)
                decay_error = abs(tx.filtered-expected)
                assert decay_error < 1e-14
            session.ready['rf'] = True
            next_sample = max(next_sample, barrier_tick + 192)
        source = old if frame_index < old_frames else new
        local_frame = frame_index if frame_index < old_frames else frame_index - old_frames
        quota = plan.count('iq')
        payload = source[local_frame * quota:(local_frame + 1) * quota]
        wire = [(frame_index * 53 + i) & 1023 for i in range(plan.count('wire'))]
        expected_wires.extend(wire)
        frame = encode(mode, wire, payload, frame_index % 64)
        for position, word in enumerate(frame):
            tick = frame_index * 64 + position
            while next_sample < tick:
                tx.clock(next_sample / word_rate)
                next_sample += word_rate / fs
            if tick == reset_tick:
                tx.reset(tick / word_rate)
                held_at_reset = tx.filtered
                consumed_before_reset = tx.consumed
                if active:
                    assert consumed_before_reset > 0 and abs(held_at_reset) > .01
                if unsafe_rearm:
                    session.ready['rf'] = True
            event = receiver.feed(word)
            if event and event[0] == 'wire':
                assert session.enabled('wire')
                wires.append(event[1])
            elif event and event[0] == 'iq':
                unpack_value |= event[1] << unpack_count
                unpack_count += 10
                while unpack_count >= width:
                    value = decode_iq(unpack_value & ((1 << width) - 1), bits)
                    unpack_value >>= width
                    unpack_count -= width
                    accepted = tx.accept(value)
                    if accepted and tick >= reset_tick:
                        accepted_after_reset.append(value)
                    peak = max(peak, len(tx.queue))
            if next_sample == tick:
                tx.clock(tick / word_rate)
                next_sample += word_rate / fs
    while tx.queue:
        tx.clock(next_sample / word_rate)
        next_sample += word_rate / fs
    assert wires == expected_wires and unpack_count == 0
    assert held_at_reset is not None
    stale = sum(v.real > 0 for v in accepted_after_reset)
    if not unsafe_rearm:
        assert stale == 0 and len(accepted_after_reset) == 50
        assert tx.accounting()['pending'] == 0
    else:
        assert stale > 0, 'Negative control failed to expose old-epoch samples'
    return dict(mode=mode, reset_word_position=reset_position, active_playback_reset=active,
                consumed_before_reset=consumed_before_reset, filter_magnitude_at_reset=abs(held_at_reset),
                filter_decay_error_at_barrier=decay_error,
                stale_samples_accepted=stale, post_reset_samples=len(accepted_after_reset),
                wired_words_preserved=len(wires), peak_dac_queue=peak,
                drain_barrier_tick=barrier_tick, accounting=tx.accounting())


def main():
    controls()
    cases = [run(mode, position, active=active)
             for active in (False, True) for mode in (0, 1) for position in range(64)]
    negative = [run(mode, 31, True, active=active)
                for active in (False, True) for mode in (0, 1)]
    files = [Path(__file__), *[Path(__file__).with_name(name) for name in
             ('rf_tx_state.py', 'session.py', 'chip_model.py')],
             P/'verification/stream_codec.py', P/'verification/transport_model.py']
    report = dict(status='passed', complete_architecture=False, cases=cases,
                  premature_rearm_negative_controls=negative,
                  source_hashes={str(f.relative_to(P)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
                  limitations=[
                      'Drain acknowledgement is a candidate coherent management API, not implemented SPI/CDC.',
                      'Host cooperates and stops old RF production; a noncooperating host must remain disabled.',
                      'RF readiness is externally asserted; analog oscillator reacquisition is not modeled.',
                      'Bursts contain integral transport words; arbitrary-length flush remains separate.',
                      'Independent wired payload is preserved through host framing; this test does not rerun its analog channel.',
                      'DAC underflows are counted, not hidden; this reset screen does not qualify continuous playout.'])
    (P/'evidence/connected-rf-reset-transport.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'{len(cases)} framed reset positions passed; all premature-rearm controls expose stale data')


if __name__ == '__main__':
    main()
