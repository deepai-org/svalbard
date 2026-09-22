"""Opt-in repeated calibration observation in the coupled three-cap model."""
from statistical_calibration_lifecycle import StatisticalCalibrationMixin
from three_cap_managed_chip import ThreeCapManagedChip

class StatisticalThreeCapChip(StatisticalCalibrationMixin,ThreeCapManagedChip):
    pass
