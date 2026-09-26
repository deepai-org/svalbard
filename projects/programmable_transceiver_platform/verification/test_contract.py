"""Negative checks for pin, direction and capacity mistakes in the contract."""
import copy
import json
import unittest
from check_contract import CONTRACT, check, resource_ledger

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.c = json.loads(CONTRACT.read_text())

    def test_resource_ledger_does_not_treat_allocations_as_measurements(self):
        r=resource_ledger(self.c)
        self.assertFalse(r['closed'])
        self.assertIsNone(r['area']['implemented_total_um2'])
        self.assertIsNone(r['inactive_domain_current_ma'])
        self.assertIsNone(r['storage']['physical_instance_bits'])
        self.assertEqual(r['area']['allocated_um2'],12920000)
        self.assertEqual(r['area']['unallocated_um2'],0)
        self.assertEqual(r['area']['explicit_reserve_um2'],2920000)
        self.assertEqual(r['total_allocated_current_ma'],350)
        self.assertEqual(r['terminals']['supply_return'],14)
        self.c['power']['domains'][0]['per_connection_budget_ma']=40
        self.assertEqual(resource_ledger(self.c)['total_allocated_current_ma'],342)
        self.c['transport']['usb_short_frame']['host_profile']='ddr125'
        with self.assertRaisesRegex(ValueError,'USB selected faster host clock'):check(self.c)

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

    def profile(self, name):
        return next(p for p in self.c['protocol_profiles'] if p['id'] == name)

    def test_usb_cannot_use_input_only_pad(self):
        next(p for p in self.c['pins'] if p['name']=='WIRE_RX_P')['direction']='in'
        with self.assertRaisesRegex(ValueError, 'USB bidirectional'): check(self.c)

    def test_usb_cannot_use_bulk_latency_contract(self):
        self.profile('usb2')['host_service']='framed'
        with self.assertRaisesRegex(ValueError, 'USB response'): check(self.c)

    def test_dp_cannot_silently_add_lanes(self):
        self.profile('displayport_rbr')['lanes']=2
        with self.assertRaisesRegex(ValueError, 'lane allocation'): check(self.c)

    def test_hbr_is_outside_clock_budget(self):
        self.c['physical_services']['serial_target_rates_bps'].append(2700000000)
        with self.assertRaisesRegex(ValueError, 'rate envelope'): check(self.c)

    def test_wifi_cannot_silently_double_bandwidth(self):
        self.profile('wifi_he20')['channel_bandwidth_max_hz']=40000000
        with self.assertRaisesRegex(ValueError, 'bandwidth'): check(self.c)

    def test_rf_cannot_take_wired_pads(self):
        self.profile('lora_24')['pins'][0]='WIRE_RX_P'
        with self.assertRaisesRegex(ValueError, 'RF pad'): check(self.c)

    def test_architecture_is_not_qualification(self):
        self.profile('sata_gen1')['standards_compliant']=True
        with self.assertRaisesRegex(ValueError, 'qualification'): check(self.c)

    def test_profiles_cannot_enable_simultaneous_engines(self):
        self.c['operating_policy']['rf_wired_simultaneous_permitted']=True
        with self.assertRaisesRegex(ValueError, 'exclusive engine'): check(self.c)

if __name__ == '__main__': unittest.main()
