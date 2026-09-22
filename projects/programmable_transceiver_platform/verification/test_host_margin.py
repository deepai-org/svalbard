"""Synthetic failures exercise the saved-waveform host threshold measurement."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
from screen_weak_drive import host_margin
from run_gpio_transient import START, UI, N

class HostMarginTests(unittest.TestCase):
    def fixture(self, path, glitch=False, missing_clock=False, clock_glitch=False):
        t=np.arange(0,START+(N+4)*UI,UI/100)
        sample=np.floor((t-START)/UI).astype(int)
        d=np.where(sample>=0,(sample%2)*3.3,0.)
        cs=np.floor((t-START-UI/2)/UI).astype(int)
        k=np.where(cs>=0,((cs+1)%2)*3.3,0.)
        if glitch:
            # Interior of bit 10 aperture, away from center and endpoints.
            center=START+10.5*UI
            d[(t>center+.07e-9)&(t<center+.14e-9)]=3.3
        c=np.zeros_like(k) if missing_clock else k
        if clock_glitch:
            c=c.copy()
            center=START+10.75*UI
            c[(t>center)&(t<center+.15e-9)]=0.
        np.savetxt(path/'wave.txt',np.column_stack((t,d,k,d,c,t*0,t*0)),
                   header='time a k d c ivd ivc',comments='')

    def test_clean_and_interior_glitch(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);self.fixture(path)
            clean=host_margin(path,'alternating')
            self.assertEqual(clean['sampled_bits'],20)
            self.assertEqual(clean['failures'],0)
            self.fixture(path,glitch=True)
            bad=host_margin(path,'alternating')
            self.assertGreater(bad['failures'],0)
            self.assertLess(bad['minimum_margin_v'],0)

    def test_lost_clock_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);self.fixture(path,missing_clock=True)
            with self.assertRaisesRegex(ValueError,'lost clock'):
                host_margin(path,'alternating')

    def test_extra_clock_edges_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);self.fixture(path,clock_glitch=True)
            with self.assertRaisesRegex(ValueError,'clock interval'):
                host_margin(path,'alternating')

if __name__=='__main__':unittest.main()
