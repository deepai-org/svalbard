"""Experimental managed loaded TX at a fixed nominal carrier.

Network integrates before every TX analog advance, including every DAC update.
Detector is always connected; ADC sampling is still owned by calibration.
LO phase modulation across the passive network is not yet included.
"""
from tx_calibration_chip import TxCalibrationChip
from rf_loaded_detector import LoadedDetector
from tx_output_terms import output_terms

class LoadedTxChip(TxCalibrationChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.loaded_tx=LoadedDetector(detector=self.tx_detector)
        advance=self.tx.advance
        def connected_advance(time):
            if time>self.tx.time:
                assert self.loaded_tx.network.time==self.tx.time
                terms=output_terms(self.tx.transmit_terms(),**self.tx_output_parameters) or [(0j,0j)]
                self._drive_loaded_network(time,terms)
            advance(time)
        self.tx.advance=connected_advance
    def _drive_loaded_network(self,time,terms):
        self.loaded_tx.advance(time,terms)
    def configure_rf_carrier(self,frequency_hz):
        if frequency_hz!=2412000000:
            raise ValueError('Loaded TX network currently supports only2412MHz')
        return super().configure_rf_carrier(frequency_hz)
    def _advance_tx_monitor(self,end):
        # Parent loop may span many DAC deadlines. The TX hook integrates each
        # interval before its held input changes, never ahead of those events.
        pass
    def complete_dac(self,time):
        before=self.dac_pipeline_updates
        result=super().complete_dac(time)
        if self.dac_pipeline_updates>before:
            assert self.loaded_tx.network.time==time
            self.loaded_tx.network.configure(True,False)
        return result
    def quiesce(self,time,reason):
        self.tx.advance(time)
        self.loaded_tx.network.configure(False,True)
        return super().quiesce(time,reason)
    def pad_envelope(self):
        assert self.loaded_tx.network.time==self.time
        return complex(self.loaded_tx.network.voltage[1])
