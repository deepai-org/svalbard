"""Integrated candidate: pulse clocks, fractional RF tuning and shared I/Q calibration.

Accuracy validity requires an explicit independent-observer error bound. Neither
that bound nor the modeled trim actuator is physically qualified.
"""
from calibration_adc_lifecycle import AutomaticCalibrationChip
from fractional_rf_chip import FractionalRFChip

class CalibratedFractionalChip(AutomaticCalibrationChip, FractionalRFChip):
    pass
