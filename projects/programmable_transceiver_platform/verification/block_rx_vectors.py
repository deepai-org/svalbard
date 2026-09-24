"""Cycle-accurate receiver vectors for immediate, pipelined and commit variants."""
from stream_codec import Receiver, encode, slots


def receiver_vectors(latency=1):
    """Keep readiness at the consumption cycle, including pending-command faults."""
    if latency not in (0, 1, 2):
        raise ValueError('Receiver latency must be zero, one or two cycles')
    rows = []
    ref = None
    fault = False
    mode = 0
    pending = [None] * latency

    def cycle(words, valid=1, wr=1, qr=1, reset=0, cr=1):
        nonlocal ref, fault, pending
        if reset:
            ref = Receiver(mode)
            fault = False
            pending = [None] * latency
        beat = pending[0] if latency else words if valid else None
        events = []
        if not reset and beat is not None and not fault:
            try:
                for word in beat:
                    event = ref.feed(word)
                    if event:
                        events.append(event)
                if ((any(s == 'wire' for s, v in events) and not wr)
                        or (any(s == 'iq' for s, v in events) and not qr)
                        or (any(s == 'command' for s, v in events) and not cr)):
                    raise ValueError('capacity')
            except ValueError:
                fault = True
                events = []
        if latency:
            pending = (pending[1:] + [list(words) if valid else None]
                       if not reset and not fault else [None] * latency)
        ws = [v for s, v in events if s == 'wire']
        qs = [v for s, v in events if s == 'iq']
        cmd = [v for s, v in events if s == 'command']
        values = [reset, mode, valid, wr, qr, cr,
                  sum(w << (10 * i) for i, w in enumerate(words)),
                  sum(w << (10 * i) for i, w in enumerate(ws)),
                  sum(w << (10 * i) for i, w in enumerate(qs)),
                  len(ws), len(qs), bool(ws), bool(qs), bool(cmd),
                  cmd[0][0] if cmd else 0, cmd[0][1] if cmd else 0, fault]
        rows.append(' '.join(f'{int(v):x}' for v in values) + '\n')

    def reset():
        cycle([0] * 8, reset=1)

    def frame(data, blocked=-1, wr=1, qr=1):
        for b in range(8):
            if b % 3 == 0:
                cycle(data[b * 8:b * 8 + 8], valid=0, wr=0, qr=0)
            cycle(data[b * 8:b * 8 + 8],
                  wr=wr if b == blocked else 1, qr=qr if b == blocked else 1)

    for mode in (0, 1):
        receiver_stimulus(mode, cycle, reset, frame)

    if latency:
        # Readiness can change between arrival and command consumption.
        for mode in (0, 1):
            reset()
            data = encode(mode, [3] * 3, [4] * 3, 0, 2, 1)
            cycle(data[:8], cr=1)
            cycle(data[8:16], cr=0)
            cycle(data[16:24], cr=1)
            reset()
            cycle(data[:8], cr=0)
            cycle(data[8:16], cr=1)
            cycle([0] * 8, valid=0)
        for _ in range(latency):
            cycle([0] * 8, valid=0)

    if latency == 2:
        # Refusing the oldest command must discard both younger beats.
        for mode in (0, 1):
            reset()
            data = encode(mode, [3] * slots(mode).count('wire'),
                          [4] * slots(mode).count('iq'), 0, 2, 1)
            cycle(data[:8], cr=1)
            cycle(data[8:16], cr=1)
            cycle(data[16:24], cr=0)
            for b in range(3, 8):
                cycle(data[b * 8:b * 8 + 8], cr=1)
            cycle([0] * 8, valid=0)
            cycle([0] * 8, valid=0)
            # Reset also discards both occupied stages.
            reset()
            cycle(data[:8])
            cycle(data[8:16])
            reset()
            cycle([0] * 8, valid=0)
            cycle([0] * 8, valid=0)
    return rows


def receiver_stimulus(mode, cycle, reset, frame):
    reset()
    seq = 0
    for wc in range(slots(mode).count('wire') + 1):
        for qc in range(slots(mode).count('iq') + 1):
            data = encode(mode, [i * 17 + wc & 1023 for i in range(wc)], [i * 29 + qc & 1023 for i in range(qc)], seq, 2, 1)
            frame(data)
            seq = (seq + 1) % 64
    for bit in range(50):
        reset()
        data = encode(mode, [1], [2], 0)
        data[bit // 10] ^= 1 << bit % 10
        frame(data)
        frame(encode(mode, [], [], 0))
    for b in range(8):
        for wr, qr in ((0, 1), (1, 0), (0, 0)):
            reset()
            frame(encode(mode, [3] * slots(mode).count('wire'), [4] * slots(mode).count('iq'), 0, 1, 1), b, wr, qr)
            frame(encode(mode, [], [], 1))
    reset()
    frame(encode(mode, [], [], 0), 0, 0, 0)
    reset()
    frame(encode(mode, [], [], 1))
    for op, arg in ((0, 0), (1, 0), (1, 1), (2, 0), (2, 1)):
        for payload in (False, True):
            for readiness in range(8):
                reset()
                data = encode(mode, [3] * 3 if payload else [], [4] * 3 if payload else [], 0, op, arg)
                cycle(data[:8], valid=0, wr=0, qr=0, cr=0)
                cycle(data[:8], wr=bool(readiness & 1), qr=bool(readiness & 2), cr=bool(readiness & 4))
                for b in range(1, 8):
                    cycle(data[b * 8:b * 8 + 8], cr=0)
                frame(encode(mode, [], [], 1))
