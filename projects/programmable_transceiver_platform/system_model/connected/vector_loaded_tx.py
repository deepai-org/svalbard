"""Experimental detector-kernel substitution preserving readout and ownership."""
from types import MethodType
from loaded_tx_chip import LoadedTxChip
from phase_loaded_tx_chip import PhaseLoadedTxChip
from vector_power_detector import VectorPowerDetector

class VectorDetectorMixin:
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        # Preserve the existing detector object, its request/read implementation,
        # analog state, ADC settings and every controller reference to it.
        self.tx_detector.advance=MethodType(VectorPowerDetector.advance,self.tx_detector)

class VectorLoadedTxChip(VectorDetectorMixin,LoadedTxChip):
    pass

class VectorPhaseLoadedTxChip(VectorDetectorMixin,PhaseLoadedTxChip):
    pass
