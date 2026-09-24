"""Detailed TX adapter with coarse-bank qualification and idealized monitor ADC."""
from coarse_retune_lifecycle import CoarseRetuningChip
from tx_calibration_services import TxCalibrationServices
from tx_output_terms import output_terms

class TxCalibrationChip(TxCalibrationServices, CoarseRetuningChip):
    TILE_COMMANDS=CoarseRetuningChip.TILE_COMMANDS+('tx_cal_start','tx_cal_status','tx_cal_abort','tx_cal_commit')

    def _tx_clock_ready(self):
        return self.reference and self.coarse.qualified and self.rf_pll.locked

    def _advance_tx_monitor(self,end):
        # While quiet the held input cannot change before the next command/event.
        if self.tx_cal.busy:
            terms=output_terms(self.tx.transmit_terms(),**self.tx_output_parameters)
            self.tx_detector.advance(end,terms)
        else:
            # Disabled monitor decays; do not imply active RF observation.
            self.tx_detector.advance(end,[(0j,0j)])
