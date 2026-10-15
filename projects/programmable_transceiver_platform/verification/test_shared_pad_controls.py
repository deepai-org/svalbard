"""Circuit-level checks for independent passive controls; not USB negotiation."""
import math
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/connected'))
from protocol_pad import SharedWiredPad
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
from design_definition import load_design

TEST_DESIGN_ROLES = {
    'SharedPadControlsTests': ('independent_fixture', 'Assigned passive networks, sources, clamps and stored charge checked against independent circuit/energy equations.'),
    'SharedPadControlsTests.test_architecture_loading_preserves_network_and_rejects_double_counting': ('shared_design', 'Architecture adapter checked against independent nodal capacitance; inconsistent copies are explicit rejection controls.'),
    'SharedPadControlsTests.test_shared_usb_parameters_reach_local_circuit_without_changing_peer': ('shared_design', 'Declared USB circuit alternatives reach local pad equations while the independent remote peer remains fixed.'),
    'SharedPadControlsTests.test_shared_driver_law_and_leakage_are_explicit_assumptions': ('shared_design', 'Reasoned driver/leakage snapshot and missing-parameter guards.'),
    'SharedPadControlsTests.test_shared_single_ended_sensing_and_explicit_override': ('shared_design', 'Reasoned sensing snapshot plus explicit threshold probes.'),
    'SharedPadControlsTests.test_construction_context_distinguishes_primitive_and_shared_probes': ('shared_design', 'Shared pad identity and mutation guards alongside independent primitive controls.'),
    'IndependentDriveTests': ('independent_fixture', 'Assigned local/remote drives and invalid primitive controls; no current-chip allocation claim.'),
}


class SharedPadControlsTests(unittest.TestCase):
    def test_architecture_loading_preserves_network_and_rejects_double_counting(self):
        import copy
        arch=load_design().architecture
        network=arch['pad_behavioral_contract']['shared_wired_network']
        pad=SharedWiredPad.from_architecture(arch)
        # Independent nodal capacitor law; primitive defaults are not a second
        # specification of the intended chip.
        shunt=network['base_shunt_cap_f_per_leg']+network['inactive_branch_cap_f_per_leg']
        mutual=network['mutual_cap_f']
        expected=np.array([[shunt+mutual,-mutual],[-mutual,shunt+mutual]])
        np.testing.assert_allclose(pad.C,expected,rtol=1e-14,atol=0.)
        self.assertAlmostEqual((pad.C@np.array([1.,-1.]))[0],shunt+2*mutual,places=24)
        changed=copy.deepcopy(arch)
        changed['pad_behavioral_contract']['shared_wired_network']['mutual_cap_f']*=2
        with self.assertRaisesRegex(ValueError,'capacitance'):
            SharedWiredPad.from_architecture(changed)
        with self.assertRaisesRegex(ValueError,'double counted'):
            SharedWiredPad.from_architecture(arch,off_cap_f=.3e-12)
        changed['blocks']['wirepad']['parameters']['capacitance_f_per_leg']=shunt+4*mutual
        self.assertGreater(SharedWiredPad.from_architecture(changed).C[0,0],pad.C[0,0])
        protected=SharedWiredPad.from_architecture(arch,divider_clamp_cap_f=30e-15)
        self.assertAlmostEqual(protected.divider_cap_f,network['divider_cap_f_per_leg']+30e-15,places=24)

    def test_shared_usb_parameters_reach_local_circuit_without_changing_peer(self):
        import copy
        baseline=load_design()
        design=baseline.hypothetical(reason='USB local driver and passive propagation',changes={
            'blocks.usbhs.parameters.drive_current_a':.020,
            'blocks.usbhs.parameters.termination_ohm_per_leg':60.,
            'blocks.usbfs.parameters.pullup_ohm':1800.,
            'blocks.usbfs.parameters.pulldown_ohm':20000.,
            'blocks.usbfs.parameters.effective_output_r_ohm':60.})
        architecture=design.architecture
        pad=SharedWiredPad.from_architecture(architecture)
        pad.configure('usb',speed='hs',attached=True);pad.local='J'
        pad.advance_network(20e-9)
        # Local 60-ohm and independent peer 45-ohm terminations in parallel.
        self.assertAlmostEqual(pad.voltage[0],.020/(1/60.+1/45.),places=7)
        self.assertAlmostEqual(pad.peer_hs_current,.4/22.5)
        pad=SharedWiredPad.from_architecture(architecture)
        pad.configure('usb',role='host',speed='fs');pad.local='J'
        pad.advance_network(20e-9)
        # Include the primitive's 1 Gohm leakage and isolated divider branch.
        conductance=1/60.+1/20000.+1/1e9+1/(1e9+2000.)
        self.assertAlmostEqual(pad.voltage[0],(3.3/60.)/conductance,places=7)
        self.assertEqual(pad.pullup_ohm,1800.)
        sensed=baseline.hypothetical(reason='Changed squelch threshold',changes={
            'blocks.usbhs.parameters.squelch_v':.2})
        sensor=SharedWiredPad.from_architecture(sensed.architecture)
        sensor.voltage[:]=(.15,0.)
        self.assertTrue(sensor.observe()['squelch'])
        self.assertTrue(sensor.sense()['squelch'])
        self.assertFalse(sensor.sense(squelch_v=.1)['squelch'])

        pad.set_local_drive('current')
        self.assertEqual(pad.local_drive['current_a'],.020)
        pad.set_local_drive('voltage')
        self.assertEqual(pad.local_drive['resistance_ohm'],60.)
        for block,key in (('usbhs','drive_current_a'),('usbhs','termination_ohm_per_leg'),
                          ('usbfs','pullup_ohm'),('usbfs','pulldown_ohm'),
                          ('usbfs','effective_output_r_ohm')):
            missing=copy.deepcopy(architecture);del missing['blocks'][block]['parameters'][key]
            with self.assertRaises(KeyError):SharedWiredPad.from_architecture(missing)
            invalid=copy.deepcopy(architecture);invalid['blocks'][block]['parameters'][key]=True
            with self.assertRaises(ValueError):SharedWiredPad.from_architecture(invalid)

    def test_shared_driver_law_and_leakage_are_explicit_assumptions(self):
        from design_definition import DesignDefinition
        design=load_design().hypothetical(reason='Finite driver and leakage circuit experiment',changes={
            'model_assumptions.wired_pad_driver.parameters.output_conductance_s':.001,
            'model_assumptions.wired_pad_driver.parameters.supply_fraction_per_v':.2,
            'model_assumptions.wired_pad_driver.parameters.compliance_headroom_v':.5,
            'model_assumptions.wired_pad_driver.parameters.shunt_leakage_ohm':10000.})
        pad=SharedWiredPad.from_architecture(design.architecture)
        expected=(.02*(1+.2*(3.-3.3))-(2.8-.4)*.001)*(.2/.5)
        self.assertAlmostEqual(pad.local_current(.02,2.8,3.),expected,places=14)
        pad.set_external_sources(((1.,100.),(1.,100.)))
        pad.advance_network(20e-9)
        expected=(1/100.)/(1/100.+1/10000.+1/(1e9+2000.))
        np.testing.assert_allclose(pad.voltage,expected,rtol=1e-9,atol=1e-10)
        probe=SharedWiredPad.from_architecture(design.architecture,current_source={'trim':1.2})
        self.assertEqual(probe.current_source['supply_fraction_per_v'],.2)
        self.assertEqual(probe.current_source['output_resistance_ohm'],1000.)
        for key in design.architecture['model_assumptions']['wired_pad_driver']['parameters']:
            missing=design.architecture
            del missing['model_assumptions']['wired_pad_driver']['parameters'][key]
            with self.assertRaises(ValueError):DesignDefinition.from_documents(design.contract,missing)
            with self.assertRaises(ValueError):SharedWiredPad.from_architecture(missing)

    def test_shared_single_ended_sensing_and_explicit_override(self):
        from design_definition import DesignDefinition
        design=load_design().hypothetical(reason='Sensing threshold propagation',changes={
            'model_assumptions.wired_pad_sensing.parameters.single_ended_low_v':.4,
            'model_assumptions.wired_pad_sensing.parameters.single_ended_high_v':.9})
        pad=SharedWiredPad.from_architecture(design.architecture)
        pad.voltage[:]=(.35,.85)
        self.assertEqual(pad.sense()['single_ended_low'],(True,False))
        self.assertEqual(pad.sense()['single_ended_high'],(False,False))
        self.assertEqual(pad.sense(high_v=.8)['single_ended_high'],(False,True))
        pad.voltage[:]=(.35,.35)
        self.assertTrue(pad.observe()['se0'])
        self.assertFalse(pad.sense(low_v=.3)['single_ended_low'][0])
        for value in ({},{'single_ended_low_v':.9,'single_ended_high_v':.4}):
            architecture=design.architecture
            architecture['model_assumptions']['wired_pad_sensing']['parameters']=value
            with self.assertRaises(ValueError):DesignDefinition.from_documents(design.contract,architecture)
            with self.assertRaises(ValueError):SharedWiredPad.from_architecture(architecture)

    def test_construction_context_distinguishes_primitive_and_shared_probes(self):
        self.assertEqual(SharedWiredPad().construction_context()['result_role'],'independent_pad_fixture')
        design=load_design();law={'trim':1.1}
        pad=SharedWiredPad.from_architecture(design.architecture,current_source=law)
        law['trim']=.8
        context=pad.construction_context()
        self.assertEqual(context['architecture_sha256'],
            design.provenance()['documents']['spec/analog-architecture.json'])
        self.assertEqual(context['probe_overrides']['current_source']['trim'],1.1)
        context['probe_overrides'].clear()
        self.assertEqual(pad.construction_context()['probe_overrides']['current_source']['trim'],1.1)
        self.assertEqual(context['circuit_parameters']['hs_current'],
                         design.architecture['blocks']['usbhs']['parameters']['drive_current_a'])
        context['circuit_parameters']['current_source']['trim']=9.
        self.assertEqual(pad.construction_context()['circuit_parameters']['current_source']['trim'],1.1)
        for mutate in (lambda p:setattr(p,'hs_current',p.hs_current*1.1),
                       lambda p:p.current_source.update(trim=1.2),
                       lambda p:p.C.__setitem__((0,0),p.C[0,0]*2)):
            changed=SharedWiredPad.from_architecture(design.architecture)
            mutate(changed)
            for operation in (changed.construction_context,
                              lambda:changed.advance(1e-9),
                              lambda:changed.advance_network(1e-9),
                              lambda:changed.small_signal_transfer(1e9,3.3)):
                with self.assertRaisesRegex(ValueError,'circuit parameters changed'):operation()
            self.assertEqual(changed.time,0.)
            np.testing.assert_array_equal(changed.voltage,[0.,0.])

    def test_unpowered_rail_backfeed_charge_is_visible_at_zero_supply_work(self):
        pad=SharedWiredPad(rail_clamp=(.4,20.))
        pad.set_external_sources(((3.3,50.),(3.3,50.)))
        pad.advance_network(30e-9,0.)
        previous=pad.supply_backfeed_charge_c
        result=pad.advance_network(40e-9,0.)
        expected=2*(3.3-.4)/(50.+20.)
        self.assertAlmostEqual(result['sampled_peak_backfeed_a'],expected,places=7)
        self.assertAlmostEqual(result['supply_backfeed_charge_c'],expected*10e-9,delta=1e-15)
        self.assertAlmostEqual(pad.supply_backfeed_charge_c-previous,result['supply_backfeed_charge_c'],delta=1e-22)
        self.assertEqual(pad.source_energy_j,0.)
        self.assertGreater(pad.supply_backfeed_charge_c,0.)

    def test_internal_clamp_has_finite_drop_current_and_energy(self):
        pad=SharedWiredPad(divider_ground_clamp=(.4,20.),divider_clamp_cap_f=10e-15)
        pad.divider_off_ohm=1e15
        pad.advance_network(2e-9,0.,injected_current_a=[0.,0.,-.002,0.],max_step_s=10e-12)
        expected=-(.4/20+.002)/(1/20+1/pad.divider_bottom_ohm)
        self.assertAlmostEqual(pad.divider_voltage[0],expected,places=7)
        self.assertLess(pad.divider_voltage[0],-.4)
        self.assertGreater(pad.divider_clamp_charge_c[0],0.)
        self.assertAlmostEqual(pad.source_energy_j,0.,places=20)
        self.assertAlmostEqual(pad.network_energy(),pad.source_energy_j+pad.external_energy_j+
            pad.injection_energy_j-pad.dissipated_j,delta=1e-20)
        with self.assertRaises(ValueError):SharedWiredPad(divider_clamp_cap_f=-1e-15)

    def test_internal_clamp_capacitance_is_present_in_signal_transfer(self):
        gains=[]
        for added in (0.,20e-15):
            pad=SharedWiredPad(divider_ground_clamp=(.4,20.),divider_clamp_cap_f=added)
            pad.configure('tmds');pad.set_external_sources(((3.3,50.),(3.3,50.)))
            pad.advance_network(20e-9)
            self.assertTrue(np.all(pad.internal_clamp_current(pad.divider_voltage)==0.))
            gains.append(abs(pad.small_signal_transfer(742.5e6,3.3)['divider_differential']))
        self.assertLess(gains[1],gains[0])

    def test_finite_charge_pulse_matches_rc_response_and_energy(self):
        pad=SharedWiredPad();pad.divider_off_ohm=1e15
        duration=50e-12;charge=.1e-12
        pulse=pad.advance_network(duration,0.,injected_current_a=[0.,0.,charge/duration,0.],
                                  max_step_s=duration/16)
        expected=charge/duration*pad.divider_bottom_ohm*(1-math.exp(
            -duration/(pad.divider_bottom_ohm*pad.divider_cap_f)))
        self.assertAlmostEqual(pad.divider_voltage[0],expected,places=8)
        self.assertAlmostEqual(pulse['injected_charge_c'][2],charge,places=24)
        self.assertAlmostEqual(pad.network_energy(),pad.source_energy_j+pad.external_energy_j+
            pad.injection_energy_j-pad.dissipated_j,delta=1e-20)
        pad.advance_network(2e-9,0.)
        self.assertAlmostEqual(pad.network_energy(),pad.source_energy_j+pad.external_energy_j+
            pad.injection_energy_j-pad.dissipated_j,delta=1e-20)

    def test_transition_charge_packets_keep_external_drive_and_account_work(self):
        pad=SharedWiredPad();pad.set_external_sources(((3.3,50.),(2.9,50.)))
        pad.configure('tmds');pad.advance_network(20e-9)
        sources=pad.external_sources
        packets=[[0.,0.,.165e-12,-.165e-12],[.165e-12,-.165e-12,0.,0.]]
        result=pad.transition_mode('serial',command_delay_s=2e-9,dead_time_s=3e-9,
            edge_charge_c=packets,injection_duration_s=50e-12)
        self.assertEqual(pad.external_sources,sources)
        self.assertEqual(result['charge_packets_c'],packets)
        self.assertAlmostEqual(result['make_time_s'],25e-9,places=18)
        self.assertAlmostEqual(pad.time,25.05e-9,places=18)
        self.assertAlmostEqual(pad.network_energy(),pad.source_energy_j+pad.external_energy_j+
            pad.injection_energy_j-pad.dissipated_j,delta=1e-18)
        before=(pad.time,pad.mode,pad.voltage.copy(),pad.divider_voltage.copy())
        with self.assertRaises(ValueError):
            pad.transition_mode('usb',command_delay_s=0.,dead_time_s=1e-9,
                edge_charge_c=[[0]*4,[0]*4],injection_duration_s=2e-9)
        self.assertEqual((pad.time,pad.mode),before[:2])
        np.testing.assert_array_equal(pad.voltage,before[2])
        np.testing.assert_array_equal(pad.divider_voltage,before[3])

    def test_finite_current_source_supply_law_matches_loaded_equilibrium(self):
        law=dict(output_resistance_ohm=1000.,supply_fraction_per_v=.5,trim=1.2)
        for rail in (2.8,3.,3.3):
            pad=SharedWiredPad(current_source=law);pad.configure('usb',speed='hs')
            pad.set_local_passives(termination_ohm=(45.,45.))
            pad.set_peer_passives(termination_ohm=(45.,45.))
            pad.drive(local='J');pad.advance_network(20e-9,rail)
            conductance=2/45+1e-9+1/(pad.divider_off_ohm+pad.divider_bottom_ohm)
            expected=(pad.hs_current*1.2*(1+.5*(rail-3.3))+.4/1000)/(conductance+1/1000)
            self.assertAlmostEqual(pad.voltage[0],expected,places=7)
            self.assertAlmostEqual(pad.network_energy(),pad.source_energy_j+
                pad.external_energy_j-pad.dissipated_j,delta=1e-18)
            # The remote source remains independent of the chip's current trim.
            pad.drive(peer='J');pad.advance_network(40e-9,rail)
            self.assertAlmostEqual(pad.voltage[0],.4,places=6)
        with self.assertRaises(ValueError):SharedWiredPad(current_source={'output_resistance_ohm':0.})

    def test_dynamic_supply_integrates_source_energy_and_retains_state(self):
        rail=lambda t:2.9+.1*math.sin(2*math.pi*10e6*t)
        pads=[]
        for split in (False,True):
            pad=SharedWiredPad();pad.configure('usb',speed='fs')
            pad.set_local_passives(pull_up_ohm=(1500.,None))
            pad.set_peer_passives(pull_down_ohm=(15000.,15000.))
            if split:pad.advance_network(50e-9,rail,max_step_s=1e-9)
            pad.advance_network(100e-9,rail,max_step_s=1e-9)
            self.assertAlmostEqual(pad.network_energy(),pad.source_energy_j+
                pad.external_energy_j-pad.dissipated_j,delta=1e-18)
            pads.append(pad)
        np.testing.assert_allclose(pads[0].voltage,pads[1].voltage,atol=1e-8,rtol=0.)
        with self.assertRaisesRegex(ValueError,'step bound'):
            pads[0].advance_network(110e-9,rail)

    def test_finite_mode_transition_retains_external_drive_and_charge(self):
        pad=SharedWiredPad()
        board=((3.3,50.),(2.9,50.))
        pad.set_external_sources(board);pad.configure('tmds')
        pad.advance_network(20e-9)
        initial=pad.voltage.copy()
        result=pad.transition_mode('serial',command_delay_s=2e-9,dead_time_s=3e-9)
        self.assertAlmostEqual(result['break_state']['time_s'],22e-9)
        self.assertAlmostEqual(result['make_state']['time_s'],25e-9)
        np.testing.assert_allclose(result['break_state']['voltage_v'],initial,atol=1e-8)
        # The isolated interval releases local loading, but the remote driver stays.
        np.testing.assert_allclose(result['make_state']['voltage_v'],[3.3,2.9],atol=1e-6)
        self.assertEqual(pad.external_sources,board)
        self.assertLess(max(pad.divider_voltage),1e-5)
        self.assertEqual(pad.local,'Z');self.assertIsNone(pad.local_drive)
        pad.advance_network(30e-9)
        self.assertAlmostEqual(pad.voltage[0]-pad.voltage[1],.2,places=6)
        self.assertAlmostEqual(pad.network_energy(),pad.source_energy_j+
            pad.external_energy_j-pad.dissipated_j,delta=1e-18)
        before=(pad.time,pad.mode,pad.voltage.copy())
        with self.assertRaises(ValueError):
            pad.transition_mode('usb',command_delay_s=1e-9,dead_time_s=0.)
        self.assertEqual((pad.time,pad.mode),before[:2])
        np.testing.assert_array_equal(pad.voltage,before[2])

    def test_ground_referenced_positive_clamp_retains_finite_overvoltage(self):
        pad=SharedWiredPad(positive_ground_clamp=(3.6,20.))
        pad.set_external_sources(((3.3,50.),(3.3,50.)))
        pad.advance_network(20e-9,0.)
        np.testing.assert_allclose(pad.voltage,[3.3,3.3],rtol=1e-6)
        _,supply,_,_=pad.electrical_network(np.r_[pad.voltage,pad.divider_voltage],0.)
        self.assertEqual(supply,0.)
        pad.set_external_sources(((4.5,50.),(4.5,50.)))
        pad.advance_network(40e-9,0.)
        expected=(4.5/50+3.6/20)/(1/50+1/20+1e-9+1/(1e9+2000))
        np.testing.assert_allclose(pad.voltage,[expected,expected],rtol=1e-6)
        self.assertGreater(min(pad.voltage),3.6)
        dv,supply,external,loss=pad.electrical_network(np.r_[pad.voltage,pad.divider_voltage],0.)
        self.assertEqual(supply,0.)
        self.assertGreater(loss,0.)
        self.assertAlmostEqual(pad.network_energy(),
            pad.source_energy_j+pad.external_energy_j-pad.dissipated_j,delta=1e-18)
        # This topology does not make any parallel rail diode disappear.
        pad.rail_clamp=(.4,20.)
        pad.advance_network(60e-9,0.)
        _,supply,_,_=pad.electrical_network(np.r_[pad.voltage,pad.divider_voltage],0.)
        self.assertLess(supply,-.1)
        with self.assertRaisesRegex(ValueError,'nonlinear solver'):pad.advance(70e-9)

    def test_serial_loading_and_disabled_divider_are_in_same_transfer(self):
        pad=SharedWiredPad();pad.set_external_sources(((.8,50.),(.8,50.)))
        pad.configure('serial');pad.advance_network(20e-9)
        dc=pad.small_signal_transfer(0.,3.3)
        self.assertAlmostEqual(abs(dc['pad_differential']),.5,places=6)
        at_nyquist=pad.small_signal_transfer(1.25e9,3.3)
        expected=.5/abs(1+2j*math.pi*1.25e9*25*2.7e-12)
        self.assertAlmostEqual(abs(at_nyquist['pad_differential']),expected,places=6)
        self.assertLess(abs(at_nyquist['divider_differential']),1e-5)

    def test_connected_divider_conserves_energy_and_survives_mode_changes(self):
        pad=SharedWiredPad()
        pad.set_external_sources(((3.3,50.),(2.9,50.)))
        pad.configure('tmds')
        state=np.array([3.,2.8,1.4,1.2])
        dv,supply,external,loss=pad.electrical_network(state,3.3)
        stored=float(state[:2]@pad.C@dv[:2])+pad.divider_cap_f*float(state[2:]@dv[2:])
        self.assertAlmostEqual(stored,3.3*supply+external-loss,places=12)
        pad.advance_network(20e-9)
        np.testing.assert_allclose(pad.voltage,[3.3*4000/4050,2.9*4000/4050],rtol=1e-6)
        np.testing.assert_allclose(pad.divider_voltage,pad.voltage/2,rtol=1e-6)
        self.assertAlmostEqual(pad.network_energy(),
            pad.source_energy_j+pad.external_energy_j-pad.dissipated_j,delta=1e-18)
        before=np.r_[pad.voltage,pad.divider_voltage]
        pad.configure('isolated')
        np.testing.assert_array_equal(np.r_[pad.voltage,pad.divider_voltage],before)
        pad.advance_network(40e-9,rail=0.)
        np.testing.assert_allclose(pad.voltage,[3.3,2.9],rtol=1e-6)
        self.assertLess(max(pad.divider_voltage),1e-5)
        self.assertAlmostEqual(pad.network_energy(),
            pad.source_energy_j+pad.external_energy_j-pad.dissipated_j,delta=1e-18)

    def test_external_load_survives_isolation_and_exposes_backfeed(self):
        pad=SharedWiredPad(rail_clamp=(.4,20.))
        pad.set_peer_passives(pull_up_ohm=(50.,50.))
        pad.configure('isolated')
        pad.advance_network(20e-9,rail=0.)
        expected=(3.3/50+.4/20)/(1/50+1/20+1e-9+1/(1e9+2000))
        np.testing.assert_allclose(pad.voltage,[expected,expected],rtol=1e-6)
        _,supply,_,_=pad.electrical_network(np.r_[pad.voltage,pad.divider_voltage],0.)
        self.assertLess(supply,-.08)
        self.assertLess(max(pad.voltage),1.3)  # External pullup is clamped, not disconnected.

    def test_disabled_branch_does_not_hide_unpowered_rail_backfeed(self):
        pad=SharedWiredPad(rail_clamp=(.4,20.),ground_clamp=(.4,20.))
        # Explicit diagnostic parameters, not a GF180 protection extraction.
        for rail,voltage in ((0.,[3.3,0.]),(3.3,[3.3,-.8]),(3.3,[3.3,0.])):
            v=np.array(voltage)
            dv,supply,external,loss=pad.electrical(v,rail)
            self.assertAlmostEqual(float(v@pad.C@dv),rail*supply+external-loss)
            self.assertGreaterEqual(loss,0.)
            if rail==0:
                self.assertAlmostEqual(supply,-.145)
            else:
                self.assertEqual(supply,0.)
        self.assertEqual(pad.mode,'isolated')
        with self.assertRaisesRegex(ValueError,'nonlinear solver'):
            pad.advance(1e-9)
        self.assertEqual(pad.time,0.)

    def test_branch_inventory_replaces_aggregate_and_preserves_mismatch(self):
        aggregate=SharedWiredPad(off_cap_f=.3e-12)
        explicit=SharedWiredPad(off_branches_f={
            'usb':(.1e-12,.1e-12),'tmds':(.2e-12,.2e-12)})
        np.testing.assert_allclose(aggregate.C,explicit.C,rtol=1e-14,atol=0)
        mismatched=SharedWiredPad(off_branches_f={
            'usb':(.1e-12,.2e-12),'tmds':(.2e-12,.4e-12)})
        self.assertAlmostEqual((mismatched.C[1,1]-mismatched.C[0,0])/1e-12,.3)
        for pad in (aggregate,mismatched):
            pad.configure('usb','device','hs',True)
            pad.drive(peer='J')
            voltage=np.array([.2,.1])
            dv,current,external,loss=pad.electrical(voltage,3.3)
            self.assertAlmostEqual(float(voltage@pad.C@dv),
                                   3.3*current+external-loss,places=12)

    def test_remote_reset_remains_active_during_local_pull_change(self):
        pad=SharedWiredPad();pad.configure('usb','device','fs',True)
        pad.drive(peer='SE0');pad.advance(100e-9)
        self.assertGreater(pad.voltage[0],.05)
        before=pad.voltage.copy()
        pad.set_local_passives()
        np.testing.assert_array_equal(pad.voltage,before)
        self.assertEqual(pad.peer,'SE0')
        pad.advance(200e-9)
        self.assertLess(max(abs(pad.voltage)),1e-6)

    def test_local_termination_does_not_remove_remote_termination(self):
        pad=SharedWiredPad();pad.configure('usb','device','hs',True)
        pad.drive(peer='J');pad.advance(100e-9)
        self.assertAlmostEqual(pad.voltage[0],.4,places=6)
        pad.set_local_passives()  # Remote 45 ohms still present.
        pad.advance(200e-9)
        self.assertAlmostEqual(pad.voltage[0],.8,places=6)
        pad.set_local_passives(termination_ohm=(45.,45.))
        pad.advance(300e-9)
        self.assertAlmostEqual(pad.voltage[0],.4,places=6)

    def test_power_balance_and_rejected_update(self):
        pad=SharedWiredPad();pad.configure('usb','host','fs',True)
        pad.set_local_passives(pull_up_ohm=(2000.,None),pull_down_ohm=(15000.,15000.),
                               termination_ohm=(None,45.))
        old=pad.local_passives.copy()
        with self.assertRaises(ValueError):pad.set_local_passives(termination_ohm=(45.,math.nan))
        self.assertEqual(pad.local_passives,old)
        for voltage in (np.array([.2,.1]),np.array([2.9,.4])):
            dv,current,external,loss=pad.electrical(voltage,3.3)
            stored_rate=float(voltage@pad.C@dv)
            self.assertAlmostEqual(3.3*current+external,loss+stored_rate,places=12)

    def test_explicit_default_passives_preserve_legacy_electrical_behavior(self):
        for role in ('host','device'):
            for speed in ('fs','ls','hs'):
                a,b=SharedWiredPad(),SharedWiredPad()
                for pad in (a,b):pad.configure('usb',role,speed,True)
                if speed=='hs':b.set_local_passives(termination_ohm=(45.,45.))
                elif role=='host':b.set_local_passives(pull_down_ohm=(15000.,15000.))
                else:b.set_local_passives(pull_up_ohm=(None,1500.) if speed=='ls' else (1500.,None))
                for voltage in ([0.,0.],[.4,.1],[2.8,.2]):
                    aa=a.electrical(voltage,3.3);bb=b.electrical(voltage,3.3)
                    np.testing.assert_allclose(aa[0],bb[0],rtol=1e-12)
                    np.testing.assert_allclose(aa[1:],bb[1:],rtol=1e-12,atol=1e-15)


class IndependentDriveTests(unittest.TestCase):
    def test_current_drive_against_remote_reset_without_speed_change(self):
        pad=SharedWiredPad();pad.configure('usb','device','fs',True)
        pad.drive(peer='SE0');pad.advance(100e-9)
        pad.set_local_passives()
        pad.set_local_drive('current',node=1,current_a=.018)
        pad.advance(200e-9)
        expected=.018/(1/30+1/15000+1/1e9)
        self.assertAlmostEqual(pad.voltage[1],expected,places=9)
        self.assertEqual((pad.speed,pad.peer),('fs','SE0'))
        self.assertEqual(pad.sense(high_v=.4)['single_ended_high'],(False,True))
        v=pad.voltage
        dv,current,external,loss=pad.electrical(v,3.3)
        self.assertAlmostEqual(3.3*current+external,loss+float(v@pad.C@dv),places=12)
        pad.set_local_drive('off');pad.advance(300e-9)
        self.assertTrue(all(pad.sense()['single_ended_low']))
        self.assertEqual(pad.peer,'SE0')

    def test_unloaded_current_requires_nonlinear_solver(self):
        pad=SharedWiredPad();pad.configure('usb','device','fs',True)
        pad.set_local_passives();pad.set_local_drive('current',node=1)
        before=pad.voltage.copy()
        with self.assertRaises(ValueError):pad.advance(1e-6)
        np.testing.assert_array_equal(pad.voltage,before)
        self.assertEqual(pad.time,0.)

    def test_conflicting_drive_and_invalid_thresholds_preserve_state(self):
        pad=SharedWiredPad();pad.configure('usb','device','fs',True)
        pad.drive(peer='SE0');pad.set_local_drive('off')
        old=pad.local_drive.copy()
        with self.assertRaises(ValueError):pad.set_local_drive('voltage',levels=(1,0))
        self.assertEqual(pad.local_drive,old)
        with self.assertRaises(ValueError):pad.sense(low_v=.8,high_v=.3)
        self.assertEqual(pad.peer,'SE0')


if __name__=='__main__':unittest.main()
