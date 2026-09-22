"""Negative checks for pin, direction and capacity mistakes in the contract."""
import copy
import json
import unittest
from check_contract import CONTRACT, check

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.c = json.loads(CONTRACT.read_text())

    def test_declared_modes(self):
        modes = check(self.c)
        self.assertEqual(modes[0]['used_words_per_direction'], {'d2h': 58, 'h2d': 58})
        self.assertEqual(modes[1]['used_words_per_direction'], {'d2h': 59, 'h2d': 59})

    def test_hidden_terminal(self):
        self.c['pins'].append({'name':'PADDLE','direction':'power','kind':'ground'})
        with self.assertRaisesRegex(ValueError, 'terminal budget'): check(self.c)

    def test_duplicate_terminal(self):
        self.c['pins'][0] = copy.deepcopy(self.c['pins'][1])
        with self.assertRaisesRegex(ValueError, 'duplicate terminal'): check(self.c)

    def test_wrong_bus_direction(self):
        next(p for p in self.c['pins'] if p['name']=='H2D_D[0]')['direction']='out'
        with self.assertRaisesRegex(ValueError, 'H2D bus'): check(self.c)

    def test_max_radio_and_pcie_do_not_fit(self):
        self.c['modes'][1]['sources'][1]['rate_bps'] = 960000000
        with self.assertRaisesRegex(ValueError, 'overcommit'): check(self.c)

    def test_slow_host_cannot_carry_pcie(self):
        self.c['modes'][1]['profile'] = 'ddr125'
        with self.assertRaisesRegex(ValueError, 'overcommit'): check(self.c)

    def test_directions_have_independent_capacity(self):
        mode = self.c['modes'][1]
        mode['sources'] = [{'id':'wire','directions':['d2h'],'rate_bps':2500000000,'sample_bits':10},
                           {'id':'iq','directions':['h2d'],'rate_bps':2500000000,'sample_bits':16}]
        self.assertEqual(check(self.c)[1]['used_words_per_direction'], {'d2h':52,'h2d':52})

    def test_area_overflow(self):
        self.c['area_um2']['reserve'] += 1
        with self.assertRaisesRegex(ValueError, 'area budget'): check(self.c)

    def test_control_slot_collision(self):
        self.c['transport']['scheduling']['control_slots'] = [0, 0]
        with self.assertRaisesRegex(ValueError, 'control slot'): check(self.c)

if __name__ == '__main__': unittest.main()
