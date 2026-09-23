"""Ideal, error-free frame transport model; no RTL/CDC/electrical qualification."""
from collections import deque
from fractions import Fraction


def schedule(quotas, frame_words=64, control_slots=(0, 1, 2, 62, 63)):
    """Smooth weighted round robin, deterministic alphabetical tie breaking."""
    if sum(quotas.values()) > frame_words-len(control_slots):
        raise ValueError('quotas exceed the payload schedule')
    quotas = dict(quotas)
    spare = frame_words-len(control_slots)-sum(quotas.values())
    if spare:
        quotas['__idle__'] = spare
    if len(set(control_slots)) != len(control_slots) or any(s < 0 or s >= frame_words for s in control_slots):
        raise ValueError('invalid control slots')
    if any(n <= 0 for n in quotas.values()):
        raise ValueError('invalid quota')
    weight = dict.fromkeys(quotas, 0)
    total = sum(quotas.values())
    result = []
    for slot in range(frame_words):
        if slot in control_slots:
            result.append(None)
            continue
        for source in weight:
            weight[source] += quotas[source]
        selected = max(sorted(weight), key=lambda source: weight[source])
        weight[selected] -= total
        result.append(selected)
    return result


def max_gap(slots, source):
    positions = [i for i, owner in enumerate(slots) if owner == source]
    if not positions:
        raise ValueError('source has no service')
    return max(b-a for a,b in zip(positions, positions[1:]+[positions[0]+len(slots)]))


def sample_value(index, bits):
    return ((index * 0x9e3779b1) ^ (index >> 3) ^ 0x5a3c) & ((1 << bits)-1)


def simulate(slots, source, rate_bps, sample_bits, host_words_hz, *,
             phase=Fraction(0), frames=512, startup_words=256,
             ingress_bits=1024, egress_bits=2048, streaming=False):
    """Same-rate producer/consumer, arbitrary source phase, integer bit packing.

    One producer burst is sample_bits (a raw line symbol or an I/Q pair).
    Whole 10-bit words are removed at frame boundaries; partial words persist.
    A snapshot is emitted in the *following* frame, requiring two staging banks.
    Receiver consumes the source cadence delayed startup_words host ticks.
    Missing/extra symbols, clock drift, errors and host stalls are not masked.
    streaming=True releases words immediately after ideal header acceptance;
    it does not model header decoding, CDC or management commands.
    """
    period = Fraction(sample_bits * host_words_hz, rate_bps)
    if not 0 <= phase < 1 or sample_bits <= 0 or rate_bps <= 0:
        raise ValueError('invalid source')
    next_arrival = phase * period
    next_consume = next_arrival + startup_words
    ingress, egress = deque(), deque()
    prepared, active = deque(), deque()
    received_frame = deque()
    quota = slots.count(source)
    produced = consumed = transferred = 0
    high_in = high_out = high_stage = 0
    quota_hits = 0
    for tick in range(frames * len(slots)):
        while next_arrival <= tick:
            value = sample_value(produced, sample_bits)
            ingress.extend((value >> i) & 1 for i in range(sample_bits))
            produced += 1
            next_arrival += period
        high_in = max(high_in, len(ingress))
        if len(ingress) > ingress_bits:
            raise ValueError('ingress overflow')
        while next_consume <= tick:
            if len(egress) < sample_bits:
                raise ValueError('egress underflow')
            value = sum(egress.popleft() << i for i in range(sample_bits))
            if value != sample_value(consumed, sample_bits):
                raise ValueError('data/order corruption')
            consumed += 1
            next_consume += period
        slot = tick % len(slots)
        if slot == 0:
            if active:
                raise ValueError('unfinished frame')
            active, prepared = prepared, deque()
            count = min(quota, len(ingress)//10)
            quota_hits += count == quota
            for _ in range(count):
                prepared.append(tuple(ingress.popleft() for _ in range(10)))
            high_stage = max(high_stage, 10*(len(active)+len(prepared)))
        if slots[slot] == source and active:
            # Emit valid words in the first count assigned source slots.
            # Remaining assigned slots are ignored using the frame descriptor.
            (egress if streaming else received_frame).extend(active.popleft())
            transferred += 10
        if slot == len(slots)-1:
            # Ideal CRC acceptance at frame end; fault behavior is tested by codec.
            egress.extend(received_frame)
            received_frame.clear()
        high_out = max(high_out, len(egress))
        if len(egress) > egress_bits:
            raise ValueError('egress overflow')
    remaining = len(ingress)+len(egress)+len(received_frame)+10*(len(active)+len(prepared))
    if produced*sample_bits != consumed*sample_bits+remaining:
        raise ValueError('bit conservation')
    return {'produced_samples': produced, 'consumed_samples': consumed,
            'ingress_high_water_bits': high_in, 'egress_high_water_bits': high_out,
            'staging_high_water_bits': high_stage, 'full_quota_frames': quota_hits,
            'transferred_bits': transferred, 'max_service_gap_words': max_gap(slots, source)}
