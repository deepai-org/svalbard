import copy
import json
import unittest
from check_contract import CONTRACT
from check_power import assess

class PowerTests(unittest.TestCase):
    def setUp(self):
        self.c=json.loads(CONTRACT.read_text())
        self.e=json.loads((CONTRACT.parents[1]/self.c['power']['current_evidence']).read_text())

    def test_partitioned_candidate_has_planning_margin_only(self):
        result=assess(self.c,self.e)
        self.assertTrue(result['all_host_estimates_within_candidate_budget'])
        self.assertIn('CORE',result['unqualified_domains'])
        self.assertAlmostEqual(max(r['with_provisional_allowances_ma'] for r in result['rows']),51.7699716125)

    def test_same_supply_cannot_be_counted_twice(self):
        self.c['power']['host_segments'][1]['supply']='VDD_HOST_0'
        with self.assertRaisesRegex(ValueError,'segment supply'):assess(self.c,self.e)

    def test_output_cannot_be_owned_twice(self):
        self.c['power']['host_segments'][1]['fast_outputs'].append('D2H_D[0]')
        with self.assertRaisesRegex(ValueError,'output ownership'):assess(self.c,self.e)

    def test_unassigned_power_terminal_rejected(self):
        self.c['power']['domains'][0]['supply_pins']=[]
        with self.assertRaisesRegex(ValueError,'supply ownership'):assess(self.c,self.e)

    def test_more_current_does_not_pass_by_construction(self):
        for row in self.e['results']:row['two_pad_dvdd_average_a']*=2
        self.assertFalse(assess(self.c,self.e)['all_host_estimates_within_candidate_budget'])

    def test_old_single_pair_rejected_on_current(self):
        # Reconstruct the old allocation without changing the terminal count.
        for pin in self.c['pins']:
            if pin['name']=='VDD_HOST_1':pin['name']='VDD_CORE_1'
            if pin['name']=='VSS_HOST_1':pin['name']='VSS_CORE_1'
        domains={d['id']:d for d in self.c['power']['domains']}
        for field,rail in [('supply_pins','VDD'),('return_pins','VSS')]:
            domains['HOST'][field].remove(f'{rail}_HOST_1')
            domains['CORE'][field].append(f'{rail}_CORE_1')
        a,b=self.c['power']['host_segments']
        for field in ['fast_outputs','inputs','management']:a[field]+=b[field]
        self.c['power']['host_segments']=[a]
        self.assertFalse(assess(self.c,self.e)['all_host_estimates_within_candidate_budget'])

if __name__=='__main__':unittest.main()
