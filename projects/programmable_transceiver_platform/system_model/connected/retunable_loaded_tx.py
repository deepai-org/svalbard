"""Experimental retargetable loaded network with a fixed reference frame.

The physical LO changes through the existing managed oscillator controls. The
network frame remains2412MHz; input phase contains the frequency difference.
No capacitor state or output voltage is reset when a target is requested.
"""
from phase_loaded_tx_chip import PhaseLoadedTxChip
from tx_calibration_chip import TxCalibrationChip

class RetunableLoadedTxChip(PhaseLoadedTxChip):
    def configure_rf_carrier(self,frequency_hz):
        # Skip only LoadedTxChip's historical fixed-carrier restriction.
        # Preserve managed grid validation, quiet ownership and invalidation.
        return TxCalibrationChip.configure_rf_carrier(self,frequency_hz)
