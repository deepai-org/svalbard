import unittest
import numpy as np
from run_gpio_transient import crossing, stimulus, N, output_instance

class ExtractorTests(unittest.TestCase):
    def test_exact_threshold_crossings(self):
        t=np.array([0.,1.,2.,3.,4.]);y=np.array([0.,.5,1.,.5,0.])
        np.testing.assert_allclose(crossing(t,y,.5),[1.,3.])

    def test_interpolated_crossings(self):
        np.testing.assert_allclose(crossing(np.array([0.,2.,4.]),np.array([0.,1.,0.]),.25),[.5,3.5])

    def test_no_crossing(self):
        self.assertEqual(len(crossing(np.array([0.,1.]),np.array([0.,0.]),.5)),0)

    def test_stimulus_is_not_constant(self):
        for mode in ['alternating','prbs7']:
            bits, _ = stimulus(mode,3.3)
            self.assertEqual(len(bits),N)
            self.assertEqual(set(bits),{0,1})
        bits,_=stimulus('alternating',3.3)
        self.assertTrue(all(a!=b for a,b in zip(bits,bits[1:])))

class NativePinMappingTests(unittest.TestCase):
    def test_programmable_drive_pins(self):
        formal = 'A CS DVDD DVSS IE OE PAD PD PDRV0 PDRV1 PU SL VDD VSS Y'.split()
        for drive, controls in [(4, ('0','0')), (8, ('VDD','0')),
                                (12, ('0','VDD')), (16, ('VDD','VDD'))]:
            tokens = output_instance('XD','A','D','YD',drive).split()
            self.assertEqual(tokens[-1], 'gf180mcu_fd_io__bi_t')
            self.assertEqual(len(tokens[1:-1]), len(formal))
            pins=dict(zip(formal,tokens[1:-1]))
            self.assertEqual((pins['PDRV0'],pins['PDRV1']),controls)
            self.assertEqual((pins['IE'],pins['OE'],pins['SL']),('0','VDD','0'))
            self.assertEqual((pins['PAD'],pins['Y']),('D','YD'))

    def test_default_and_invalid_drive(self):
        self.assertEqual(output_instance('XD','A','D','YD',24),
                         'XD A 0 DVDD 0 0 VDD D 0 0 0 VDD 0 YD gf180mcu_fd_io__bi_24t')
        with self.assertRaises(ValueError):
            output_instance('XD','A','D','YD',20)

    def test_output_return_can_move_without_core_return(self):
        for drive in (8,24):
            tokens=output_instance('XD','A','D','YD',drive,dvss='DVSS').split()
            self.assertEqual(tokens[4],'DVSS')
            self.assertEqual(tokens[-3],'0')  # Separate ideal core VSS.

if __name__=='__main__':unittest.main()
