"""Experimental composition: shared ADC, physical LO, loaded pad and host PHY."""
from vector_loaded_tx import VectorDetectorMixin
from shared_tx_detector import SharedAdcLoadedTxChip
from retunable_loaded_tx import RetunableLoadedTxChip
from host_activation_chip import HostActivationChip

class SharedPhaseLoadedTxChip(VectorDetectorMixin,SharedAdcLoadedTxChip,
                             RetunableLoadedTxChip,HostActivationChip):
    """ADC kernel vectorization leaves shared request/read callbacks intact."""
    pass
