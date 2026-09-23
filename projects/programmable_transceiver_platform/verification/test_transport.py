import json
import unittest
from fractions import Fraction
from check_contract import CONTRACT, check
from transport_model import schedule, max_gap, simulate

class TransportTests(unittest.TestCase):
    def test_exclusive_streaming_150_service_boundary(self):
        host=Fraction(300000000*999900,1000000)
        rate=Fraction(2500000000*1000100,1000000)
        for quota in (53,54):
            slots=schedule({'wire':quota},control_slots=(0,1,2,3,4))
            if quota==53:
                with self.assertRaisesRegex(ValueError,'ingress overflow'):
                    simulate(slots,'wire',rate,10,host,streaming=True)
            else:
                result=simulate(slots,'wire',rate,10,host,streaming=True)
                self.assertGreater(result['consumed_samples'],1000)
                self.assertLessEqual(result['ingress_high_water_bits'],1024)
                self.assertLessEqual(result['egress_high_water_bits'],2048)

    @classmethod
    def setUpClass(cls):
        cls.c = json.loads(CONTRACT.read_text())
        cls.allocations = check(cls.c)

    def test_mode_phase_and_frequency_matrix(self):
        summary = {}
        cfg = self.c['transport']['legacy_v1_scheduling']
        for mode, allocation in zip(self.c['modes'], self.allocations):
            slots = schedule(allocation['reserved_words_per_source'], control_slots=cfg['control_slots'])
            self.assertEqual([i for i,s in enumerate(slots) if s is None], [0,1,2,62,63])
            for source in mode['sources']:
                name = source['id']
                self.assertEqual(slots.count(name), allocation['reserved_words_per_source'][name])
                bits = source['sample_bits']
                p = self.c['transport']['profiles'][mode['profile']]
                for host_ppm, source_ppm in [(-100,100),(0,0),(100,-100)]:
                    host = Fraction(p['clock_hz']*p['edges']*(1000000+host_ppm),1000000)
                    rate = Fraction(source['rate_bps']*(1000000+source_ppm),1000000)
                    for phase in [Fraction(0),Fraction(1,4),Fraction(1,2),Fraction(999,1000)]:
                        with self.subTest(mode=mode['id'], source=name,host_ppm=host_ppm,phase=phase):
                            result = simulate(slots,name,rate,bits,host,phase=phase,
                                              frames=cfg['simulation_frames'], startup_words=cfg['startup_words'],
                                              ingress_bits=cfg['ingress_bits_per_source'], egress_bits=cfg['egress_bits_per_source'])
                            key = mode['id'] + '/' + name
                            peaks = summary.setdefault(key, {})
                            for field in ['ingress_high_water_bits','egress_high_water_bits','staging_high_water_bits','max_service_gap_words']:
                                peaks[field] = max(peaks.get(field,0), result[field])
                            self.assertGreater(result['consumed_samples'],1000)

        print(json.dumps({'legacy_v1_finite_matrix_peaks': summary}, indent=2))

    def test_known_service_gaps(self):
        slots = schedule({'wire':52,'iq':7})
        self.assertEqual(slots.count('iq'),7)
        self.assertLessEqual(max_gap(slots,'iq'),14)

    def test_no_prefill_underflows(self):
        with self.assertRaisesRegex(ValueError,'underflow'):
            simulate(schedule({'wire':52,'iq':7}),'wire',2500000000,10,312500000,startup_words=0)

    def test_too_small_ingress_overflows(self):
        with self.assertRaisesRegex(ValueError,'ingress overflow'):
            simulate(schedule({'wire':52,'iq':7}),'wire',2500000000,10,312500000,ingress_bits=10)

    def test_too_small_egress_overflows(self):
        with self.assertRaisesRegex(ValueError,'egress overflow'):
            simulate(schedule({'wire':52,'iq':7}),'wire',2500000000,10,312500000,egress_bits=10)

    def test_insufficient_service_fails(self):
        with self.assertRaisesRegex(ValueError,'overflow|underflow'):
            simulate(schedule({'wire':4,'iq':26}),'wire',2500000000,10,312500000)

if __name__ == '__main__': unittest.main()
