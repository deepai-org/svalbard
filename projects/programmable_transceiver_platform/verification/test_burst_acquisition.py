"""Independent phase-selection and replay fixtures with synthetic bit edges.

Assigned jitter and training test acquisition logic, not physical sampler timing."""
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
from burst_acquisition import select_phase,PhaseHistory


def samples(bits,offset,jitter=0.):
    # Local sampling clock and independent transmitter edge phase. Jitter changes
    # each bit's boundary, not the chosen receiver phase or expected data.
    edges=[i+offset+jitter*math.sin(i*1.7) for i in range(len(bits)+1)]
    result=[]
    for row in range(len(bits)+1):
        values=[]
        for phase in range(8):
            t=row+phase/8
            index=next((i-1 for i,e in enumerate(edges) if e>t),len(bits)-1)
            values.append(bits[index] if index>=0 and t<edges[-1] else 0)
        result.append(values)
    return result


TEST_DESIGN_ROLES = {
    'BurstTests': ('independent_fixture', 'Synthetic phase samples, assigned jitter and bounded-history fault examples.'),
}

class BurstTests(unittest.TestCase):
    def test_short_training_preserves_following_payload_at_all_input_phases(self):
        bits=[i%2 for i in range(12)]+[int(c) for c in '11001000011110101100101011010011']
        for phase in range(64):
            rows=samples(bits,phase/64,jitter=.03)
            history=PhaseHistory()
            for row in rows[:8]:history.append(row)
            choice=history.acquire(0)
            history.acknowledge(choice.seed32)
            out=[]
            for row in rows[8:]:
                out+=history.replay()
                history.append(row)
            while history.read_index<history.write_index:out+=history.replay()
            self.assertEqual([i for i,v in out],list(range(len(rows))))
            decoded=[v for i,v in out]
            # Unknown prefix can be one partial bit; all payload must be intact.
            self.assertTrue(decoded[12:len(bits)]==bits[12:] or decoded[13:len(bits)+1]==bits[12:],phase)
            self.assertGreaterEqual(choice.margin_ui,.25)

    def test_delayed_seed_ack_preserves_short_burst_and_bounded_tail(self):
        bits=[i%2 for i in range(12)]+[int(c) for c in '1100100001111010']
        for phase in range(64):
            rows=samples(bits,phase/64,jitter=.03);h=PhaseHistory()
            for row in rows[:16]:h.append(row)
            choice=h.acquire(0)
            with self.assertRaises(ValueError):h.replay()
            with self.assertRaises(ValueError):h.acknowledge((choice.seed32+4)%32)
            h.acknowledge(choice.seed32);out=[]
            for row in rows[16:]:
                out+=h.replay();h.append(row)
            tail=0
            while h.read_index<h.write_index:out+=h.replay();tail+=1
            self.assertLessEqual(tail+2,8)
            self.assertEqual([i for i,b in out],list(range(len(rows))))
            decoded=[b for i,b in out]
            self.assertTrue(decoded[12:len(bits)]==bits[12:] or decoded[13:len(bits)+1]==bits[12:])
            with self.assertRaises(ValueError):h.handoff(h.write_index-1)
            h.handoff(h.write_index)
            self.assertEqual(h.live(len(rows),1),(len(rows),1))
            with self.assertRaises(ValueError):h.live(len(rows),1)

    def test_insufficient_or_distributed_edges_never_manufacture_lock(self):
        with self.assertRaises(ValueError):select_phase([[0]*8]*8)
        with self.assertRaises(ValueError):select_phase([[i%2 for i in range(8)]]*8)

    def test_history_overflow_and_missing_prefix_are_reported(self):
        h=PhaseHistory();rows=samples([i%2 for i in range(64)],.2)
        for row in rows[:8]:h.append(row)
        choice=h.acquire(0)
        h.acknowledge(choice.seed32)
        for row in rows[8:32]:h.append(row)
        with self.assertRaises(BufferError):h.append(rows[32])
        h=PhaseHistory()
        for row in rows:h.append(row)
        with self.assertRaises(ValueError):h.acquire(0)


if __name__=='__main__':unittest.main()
