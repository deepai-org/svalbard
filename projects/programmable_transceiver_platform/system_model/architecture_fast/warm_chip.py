"""Common chip with finite centering and counter-driven warm coarse tuning."""
from coarse_chip import CoarseTransceiverChip
from warm_clock import WarmClock,WarmAcquisition

class WarmTransceiverChip(CoarseTransceiverChip):
    RF_PLL_CLASS=WarmClock
    COARSE_CLASS=WarmAcquisition
    def execute_management(self,operation,payload,time):
        if operation=='rf_coarse_status' and self.coarse.state=='centering':
            if payload:raise ValueError('Reserved coarse status payload')
            return dict(value=9|256|(self.rf_pll.bank_code<<16))
        result=super().execute_management(operation,payload,time)
        if operation=='rf_coarse_start':
            if self.tx_cal.valid:self.tx_cal.cancel(time,'Coarse retuning invalidated TX calibration')
            self.install_segment(self.rf_pll.frequency_hz-self.rf_carrier,check=False)
        return result
