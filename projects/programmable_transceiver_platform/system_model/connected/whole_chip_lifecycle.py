"""Executable candidate management contract around real framed data blocks.

Management messages are coherent events, not an implemented SPI register map.
Epoch IDs are simulator-side drain tokens, not added payload pins or words.
"""
import json
import math
from pathlib import Path
from chip_model import P, encode, Receiver, encode_iq, decode_iq
from burst_codec import BurstEncoder, BurstDecoder
from rf_tx_state import RfTxState
from session import Session
from wired_blocks import WiredChannel,CurrentSwitchChannel


class WholeChip:
    def __init__(self, acquisition_s=2e-6, watchdog_s=2e-6):
        self.wire_swing=1.;self.wire_postcursor=0.
        self.session = Session()
        self.tx = RfTxState(self.session)
        self.acquisition_s = acquisition_s
        self.watchdog_s = watchdog_s
        self.streaming_watchdog_enabled = True
        self.time = 0.
        self.epoch = 0
        self.state = 'reset'
        self.reference = True
        self.lock_at = math.inf
        self.last_host = 0.
        self.events = []
        self.wired_output = []
        self.inflight = 0
        self.decoder = None
        self.rejected_stale = 0
        self.host_frame_words = 64

    def make_host_receiver(self):
        return Receiver(self.session.mode,frame_words=self.host_frame_words)

    def make_return_receiver(self):
        if getattr(self,'record_return',False):
            self.require_record_configuration()
            from bit_event_codec import StreamingRecordReceiver
            return StreamingRecordReceiver()
        return self.make_host_receiver()

    def host_quota(self,source):
        from stream_codec import slots
        return slots(self.session.mode,self.host_frame_words).count(source)

    def encode_host_frame(self,wire,iq,sequence):
        return encode(self.session.mode,wire,iq,sequence,frame_words=self.host_frame_words)

    def advance(self, time):
        if time < self.time:
            raise ValueError('Nonmonotonic time')
        if self.streaming_watchdog_enabled and self.state == 'active' and time-self.last_host > self.watchdog_s:
            self.quiesce(self.last_host+self.watchdog_s, 'host watchdog')
        self.tx.advance(time)
        self.time = time
        if self.state == 'acquiring' and self.reference and time >= self.lock_at and self.clocks_ready():
            self.session.ready.update(rf=True, wire=True)
            self.session.arm()
            self.state = 'active'
            self.last_host = time
            self.events.append(['active', self.epoch, time])

    def clock_required(self,engine):
        """Concurrent baseline needs both clocks; exclusive compositions override."""
        return True

    def clocks_ready(self):
        return True

    def configure_wire_tx(self,swing,postcursor):
        if self.session.armed:raise ValueError('Wired TX configuration requires disarmed state')
        if swing not in (.25,.5,1.) or postcursor not in (0.,.25,.5):raise ValueError('Unsupported wired TX setting')
        self.wire_swing=swing;self.wire_postcursor=postcursor
        if hasattr(self,'channel'):
            self.channel.swing=swing;self.channel.postcursor=postcursor

    def configure(self, mode, time):
        self.advance(time)
        if self.state != 'reset':
            raise ValueError('Drain acknowledgement required before configuration')
        self.session.configure(mode)
        self.session.host_ready = True
        self.receiver = self.make_host_receiver()
        self.bits = 12 if mode == 0 else 8
        self.channel = WiredChannel(getattr(self,"wire_rate_override",None) or (1.25e9 if mode == 0 else 2.5e9),swing=self.wire_swing,postcursor=self.wire_postcursor)
        if getattr(self,'wire_interface',{}).get('electrical')=='dc_current_sink':
            self.channel=CurrentSwitchChannel(self.channel.rate)
        self.state = 'acquiring'
        self.lock_at = time+self.acquisition_s if self.reference else math.inf
        self.events.append(['configure', mode, self.epoch, time])

    def quiesce(self, time, reason):
        # Internal watchdog calls this before advance reaches its requested time.
        self.tx.reset(time)
        self.session.trip('rf')
        self.session.trip('wire')
        self.state = 'draining'
        self.time = time
        self.events.append(['quiesce', reason, self.epoch, time])

    def set_reference(self, present, time):
        self.advance(time)
        was_present = self.reference
        self.reference = present
        if present and not was_present and self.state == 'acquiring':
            self.lock_at = time+self.acquisition_s
        if not present and self.state in ('active', 'acquiring'):
            self.quiesce(time, 'reference loss')
        # Restoring reference never clears a latched fault or bypasses drain.

    def acknowledge_drain(self, epoch, time):
        self.advance(time)
        if self.state != 'draining' or epoch != self.epoch or self.inflight:
            raise ValueError('Wrong epoch, live transport, or missing quiesce')
        self.session.reset()
        self.decoder = None
        self.epoch += 1
        self.state = 'reset'

    def descriptor(self, count):
        if self.state != 'active' or self.decoder is not None:
            raise ValueError('Descriptor requires active idle RF stream')
        self.decoder = BurstDecoder(2*self.bits, count)

    def feed(self, word, epoch, time):
        self.advance(time)
        if epoch != self.epoch or self.state != 'active':
            self.rejected_stale += 1
            return
        self.last_host = time
        try:
            event = self.receiver.feed(word)
            if event and event[0] == 'wire':
                self.accept_wire(event[1])
            elif event and event[0] == 'iq':
                if self.decoder is None:
                    raise ValueError('RF data without descriptor')
                for value in self.decoder.feed(event[1]):
                    self.tx.accept(decode_iq(value, self.bits))
        except (ValueError, OverflowError) as error:
            self.quiesce(time, str(error))

    def accept_wire(self, value):
        self.wired_output.append(self.channel.word(value))

    def finish_burst(self):
        if self.decoder is None:
            raise ValueError('No descriptor')
        try:
            self.decoder.finish()
        except ValueError as error:
            self.quiesce(self.time, str(error))
            raise
        self.decoder = None


def expect_rejection(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError('Unsafe transition accepted')


def run_case(start_mode, interruption):
    chip = WholeChip()
    chip.configure(start_mode, 0.)
    assert not chip.session.enabled('rf')
    chip.advance(chip.acquisition_s)
    assert chip.state == 'active'
    expect_rejection(lambda: chip.configure(1-start_mode, chip.time))
    observed = []

    def burst(values, wire, sequence=0, interrupt=False):
        chip.descriptor(len(values))
        enc = BurstEncoder(2*chip.bits, len(values))
        words = []
        for value in values:
            words.extend(enc.push(encode_iq(value, chip.bits)))
        words.extend(enc.finish())
        frame = encode(chip.session.mode, wire, words, sequence)
        epoch = chip.epoch
        chip.inflight += 1
        step = 1/(250e6 if chip.session.mode == 0 else 312.5e6)
        begin = chip.time
        for index, word in enumerate(frame):
            chip.feed(word, epoch, begin+(index+1)*step)
            if chip.tx.queue:
                # This lifecycle screen consumes on arrival; full-throughput
                # independent sample pacing is checked by chip_model.py.
                chip.tx.clock(chip.time)
                observed.append(chip.tx.held)
            if interrupt and index == 32:
                if interruption == 'reference':
                    chip.set_reference(False, chip.time)
                else:
                    chip.quiesce(chip.time, 'mode change')
                retained = chip.tx.filtered
                assert abs(retained) > 0 and chip.tx.held == 0
                expect_rejection(lambda: chip.acknowledge_drain(epoch, chip.time))
        chip.inflight -= 1
        if not interrupt:
            chip.finish_burst()

    burst([.5, .25], [913, 17, 801], interrupt=True)
    assert chip.state == 'draining' and chip.rejected_stale > 0
    assert not chip.session.enabled('wire') and not chip.session.enabled('rf')
    old_epoch = chip.epoch
    expect_rejection(lambda: chip.acknowledge_drain(old_epoch+1, chip.time))
    chip.set_reference(True, chip.time)
    assert chip.state == 'draining'
    chip.acknowledge_drain(old_epoch, chip.time)
    chip.configure(1-start_mode, chip.time)
    chip.advance(chip.time+chip.acquisition_s)
    # An old transport event cannot enter the new epoch.
    before = len(chip.wired_output)
    chip.feed(0, old_epoch, chip.time)
    assert len(chip.wired_output) == before
    burst([-.5, -.25], [3, 511, 1000])
    assert chip.wired_output[-3:] == [3, 511, 1000]
    assert observed[-2:] == [-.5, -.25]
    # Back-to-back descriptors include a partial padded word and an empty burst.
    burst([.125], [37], 1)
    burst([], [38], 2)
    assert chip.wired_output[-2:] == [37, 38]
    chip.advance(chip.time+chip.watchdog_s*2)
    assert chip.state == 'draining' and chip.tx.held == 0
    return dict(start_mode=start_mode, interruption=interruption,
                events=chip.events, stale_words_rejected=chip.rejected_stale,
                accounting=chip.tx.accounting())


def main():
    # Reference appearing after configuration starts acquisition at that event.
    startup = WholeChip()
    startup.set_reference(False, 0.)
    startup.configure(0, 0.)
    startup.advance(10e-6)
    assert startup.state == 'acquiring'
    startup.set_reference(True, startup.time)
    startup.advance(startup.time+startup.acquisition_s)
    assert startup.state == 'active'
    # A truncated burst must fault the chip, not just the local decoder.
    startup.descriptor(1)
    expect_rejection(startup.finish_burst)
    assert startup.state == 'draining' and not startup.session.enabled('rf')
    rows = [run_case(mode, cause) for mode in (0, 1)
            for cause in ('reference', 'mode')]
    report = dict(status='passed', cases=rows, complete_architecture=False,
                  physical_qualification=False, assumptions=[
        'Fixed acquisition delay and immediate reference-loss detection are assumed lock behavior.',
        'Drain acknowledgement is a coherent abstract management event; epoch tags exist only in the simulator.',
        'Arrival-paced consumption isolates lifecycle; independent sample clocks are exercised in the other suite scenarios.',
        'Mode changes quiesce both engines; RF analog filter state persists across resets.',
        'No serialized management, CDC metastability, or calibrated silicon parameters are claimed.'])
    (P/'evidence/connected-whole-chip-lifecycle.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Passed four persistent-chip mode-change/reference-loss/recovery scenarios')


if __name__ == '__main__':
    main()
