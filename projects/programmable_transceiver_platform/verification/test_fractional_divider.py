"""Exact arithmetic controls for the experimental divider extension."""
import copy
from fractions import Fraction
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model'/'connected'))
from shaped_fractional_pll import ThirdOrderSequence

class ThirdOrderDividerTests(unittest.TestCase):
    def test_exact_error_identity_and_positive_counts(self):
        for denominator in range(2,81):
            for numerator in range(1,denominator):
                sequence=ThirdOrderSequence(Fraction(60*denominator+numerator,denominator))
                d=sequence.ratio.denominator;history=[0,0,0]
                for _ in range(4*d):
                    count=sequence.step();error=sequence.third
                    self.assertGreaterEqual(count,sequence.low-3)
                    self.assertLessEqual(count,sequence.low+4)
                    self.assertGreater(count,0)
                    self.assertEqual((count-sequence.low)*d-sequence.remainder,
                        -(error-3*history[-1]+3*history[-2]-history[-3]))
                    history.append(error)

    def test_integer_control_and_copy_continuation(self):
        integer=ThirdOrderSequence(Fraction(60))
        self.assertEqual([integer.step() for _ in range(100)],[60]*100)
        sequence=ThirdOrderSequence(Fraction(2437,40))
        for _ in range(137):sequence.step()
        clone=copy.copy(sequence)
        first=[sequence.step() for _ in range(800)]
        self.assertEqual(clone.emitted,137)
        self.assertEqual(first,[clone.step() for _ in range(800)])

if __name__=='__main__':unittest.main()
