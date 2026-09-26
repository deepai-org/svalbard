"""Circuit-level checks for independent passive controls; not USB negotiation."""
import math
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/connected'))
from protocol_pad import SharedWiredPad


class SharedPadControlsTests(unittest.TestCase):
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
