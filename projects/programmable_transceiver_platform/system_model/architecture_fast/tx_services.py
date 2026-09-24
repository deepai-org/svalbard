"""Fast TX adapter with sampled-clock readiness and an idealized monitor ADC."""
import run as architecture  # Install the connected-model import path.
from services import ServiceChip
from tx_calibration_services import TxCalibrationServices
from tx_output_terms import output_terms

class FastTxServiceChip(TxCalibrationServices, ServiceChip):
    TILE_COMMANDS=ServiceChip.TILE_COMMANDS+('tx_cal_start','tx_cal_status','tx_cal_abort','tx_cal_commit')

    def _tx_clock_ready(self):
        return self.reference and self.rf_pll.locked

    def _advance_tx_monitor(self,end):
        # While quiet the held input cannot change before the next command/event.
        if self.tx_cal.busy:
            terms=output_terms(self.tx.transmit_terms(),**self.tx_output_parameters)
            self.tx_detector.advance(end,terms or [(0j,0j)])
        else:
            # Disabled monitor decays; do not imply active RF observation.
            self.tx_detector.advance(end,[(0j,0j)])
