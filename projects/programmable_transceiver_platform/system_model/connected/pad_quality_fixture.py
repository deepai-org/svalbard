"""Common carrier reference and calibration capture for pad-quality fixtures."""
from loaded_pad_quality import IdealLoadedChip
from managed_tx_quality import calibration_window

class IdealCarrierChip(IdealLoadedChip):
    def __init__(self,network_carrier_hz=2412000000,**kwargs):
        super().__init__(**kwargs)
        self.loaded_tx.network.reframe(network_carrier_hz,0.)

def before_traffic(ideal):
    def prepare(c):
        calibration_window(ideal)(c)
        # ADC conversion logs include maintenance reads. Keep them separately;
        # only subsequent receive conversions belong to the RX waveform record.
        c.tx_maintenance_observations=list(zip(c.sample_times,c.analog_samples))
        c.sample_times=[];c.analog_samples=[]
    return prepare

