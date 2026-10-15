"""Shared control permissions/guards with prescribed timing and readiness.

The altered cold-start guard is an independent invariance fixture. These tests
check planner arithmetic, not observed analog settling or serialized latency.
"""
import json
import sys
import unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'system_model/architecture_fast'))
from live_control import plan_wire_trim, plan_rf_direction


from design_definition import load_design


TEST_DESIGN_ROLES = {
    'LiveControlTests': ('shared_design', 'Shared architecture supplies live permissions and guards; prescribed readiness and altered cold-start guard isolate planner behavior.'),
}

class LiveControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arch=load_design().architecture

    def test_training_continues_with_atomic_boundary_apply_and_ack(self):
        active={'current_code':100,'postcursor_code':20}
        result=plan_wire_trim(self.arch,active,{'current_code':150},
            requested_ui=103,now_ui=100,epoch=7,active_epoch=7,training_window=True)
        self.assertEqual((result.apply_word,result.settled_word),(11,13))
        self.assertEqual((result.current_code,result.postcursor_code,result.epoch),(150,20,7))
        self.assertEqual(active,{'current_code':100,'postcursor_code':20})

    def test_live_permissions_do_not_expose_termination_or_stale_commands(self):
        base=dict(requested_ui=100,now_ui=90,epoch=7,active_epoch=7,training_window=True)
        for change in ({'source_termination_enable':0},{'current_code':256}):
            with self.assertRaises(ValueError):plan_wire_trim(self.arch,{'current_code':100,'postcursor_code':20},change,**base)
        for override in ({'training_window':False},{'epoch':6},{'now_ui':101},{'fault':True}):
            with self.assertRaises(ValueError):plan_wire_trim(self.arch,{'current_code':100,'postcursor_code':20},{'current_code':150},**(base|override))

    def test_warm_direction_guard_independent_of_cold_start(self):
        args=dict(direction='rx_to_tx',gate_tick=100,launch_tick=140,now_tick=90,
                  epoch=3,active_epoch=3,startup_ready=True,clocks_alive=True,payload_ready=True)
        action=plan_rf_direction(self.arch,**args)
        self.assertEqual((action.ready_tick,action.launch_tick,action.epoch),(132,140,3))
        other=json.loads(json.dumps(self.arch))
        other['control_fields']['monitor.config']['fields']['qualification_ticks']['default']=60000
        self.assertEqual(plan_rf_direction(other,**args),action)
        with self.assertRaises(ValueError):plan_rf_direction(self.arch,**(args|{'startup_ready':False}))

    def test_late_settling_and_missing_prefill_never_silently_delay_launch(self):
        args=dict(direction='rx_to_tx',gate_tick=100,launch_tick=140,now_tick=90,
                  epoch=3,active_epoch=3,startup_ready=True,clocks_alive=True,payload_ready=True)
        for override in ({'additional_settling_ticks':9},{'payload_ready':False},{'clocks_alive':False},{'fault':True},{'epoch':2}):
            with self.assertRaises(ValueError):plan_rf_direction(self.arch,**(args|override))
        rx=plan_rf_direction(self.arch,**(args|{'direction':'tx_to_rx','guard_ticks':40}))
        self.assertEqual(rx.ready_tick,140)


if __name__=='__main__':unittest.main()
