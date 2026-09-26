"""Independent edge-source lifecycle checks for the candidate PLL observer."""
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model'/'connected'))
from fractional_pulse_screen import CountedAcquisition


class CountedAcquisitionTests(unittest.TestCase):
    def test_reference_rate_preserves_acquisition_observation_duration(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model'/'architecture_fast'))
        from behavioral import RailDrivenPulsePLL
        for reference in (40e6,80e6,120e6):
            observer=RailDrivenPulsePLL(rate_hz=2437e6,reference_hz=reference,
                                       require_acquisition=True).acquisition
            self.assertAlmostEqual(observer.window/reference,500e-6)
            for edge in range(2*observer.window+1):
                time=edge/reference
                observer.reference_edge(time,math.floor(time*2437e6/16))
            self.assertTrue(observer.acquired)
        old=CountedAcquisition(2437e6,reference_hz=120e6)
        for edge in range(40001):
            time=edge/120e6
            old.reference_edge(time,math.floor(time*2437e6/16))
        self.assertFalse(old.acquired)

    def test_persistent_start_step_loss_recovery(self):
        for error_ppm in (-10.,0.,10.):
            for phase in (.1,.9):
                m=CountedAcquisition(2412e6)
                dt=1/(40e6*(1+error_ppm*1e-6))
                time=0.;cycles=phase*16;index=0
                def edges(number,rate=2412e6):
                    nonlocal time,cycles,index
                    for _ in range(number):
                        time+=dt;cycles+=rate*dt;index+=1
                        # Independent bounded endpoint error exercises capture uncertainty.
                        count=math.floor(cycles/16)+(index%3-1)
                        m.reference_edge(time,count)
                edges(40001)
                self.assertTrue(m.acquired)
                self.assertEqual(m.measurements,2)
                edges(20000,2412e6*1.001)
                self.assertFalse(m.acquired)
                edges(40000)
                self.assertTrue(m.acquired)
                before=time
                m.tick(time+101e-9)
                self.assertFalse(m.acquired)
                # Source keeps running through missing references; no phase reset.
                time+=1e-6;cycles+=2412e6*(time-before)
                edges(20001)
                self.assertFalse(m.acquired)
                edges(20000)
                self.assertTrue(m.acquired)

    def test_arbitrary_step_phase_needs_two_window_bound(self):
        delays=[]
        for offset in (0,5000,10000,15000,19000,19999):
            m=CountedAcquisition(2412e6)
            phase=.3;step_edge=40000+offset
            for i in range(step_edge+1):
                m.reference_edge(i/40e6,math.floor((phase+2412e6*i/40e6)/16))
            self.assertTrue(m.acquired)
            initial=phase+2412e6*step_edge/40e6
            for j in range(1,40001):
                cycles=initial+2412e6*1.001*j/40e6
                m.reference_edge((step_edge+j)/40e6,math.floor(cycles/16))
                if not m.acquired:
                    delays.append(j/40e6)
                    break
            else:
                self.fail('Sustained out-of-band step escaped two full windows')
        self.assertGreater(max(delays),500e-6)
        self.assertLessEqual(max(delays),1e-3)

    def test_short_frequency_burst_can_escape_all_acquisition_windows(self):
        m=CountedAcquisition(2412e6)
        cycles=.3
        for i in range(80001):
            if i:
                # A 10 us, +1000 ppm burst after acquisition. Preserve the
                # accumulated phase afterward rather than resetting the source.
                burst=41000<i<=41400
                cycles+=2412e6*(1.001 if burst else 1.)/40e6
            m.reference_edge(i/40e6,math.floor(cycles/16))
            if i>=40000:self.assertTrue(m.acquired)
        self.assertEqual(m.measurements,4)
        self.assertAlmostEqual(cycles-(.3+2412e6*80000/40e6),24.12,places=4)
        # Counterexample, not a correctness claim for payload readiness:
        # no fault notification exists, so an arbitrary holdback delay cannot help.

    def test_short_window_cannot_certify_resolution(self):
        m=CountedAcquisition(2412e6,window_edges=800)
        for i in range(2401):
            m.reference_edge(i/40e6,math.floor(2412e6*i/40e6/16))
        self.assertEqual(m.measurements,3)
        self.assertFalse(m.acquired)

    def test_does_not_certify_phase_quality(self):
        m=CountedAcquisition(2412e6)
        for i in range(40001):
            t=i/40e6
            # Large 0.2-cycle phase modulation cancels over count windows.
            cycles=2412e6*t+.2*math.sin(2*math.pi*1e6*t)
            m.reference_edge(t,math.floor(cycles/16))
        self.assertTrue(m.acquired)  # Deliberately NOT a payload/phase-quality pass.


if __name__=='__main__':
    unittest.main()
