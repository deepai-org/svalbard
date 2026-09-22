"""Finite RF output isolation candidate, with retained control state and leakage.

This is a complex-envelope transfer assumption, not a qualified GF180 switch.
The internal detector is upstream of this stage. Pad-side calibration, loading,
switch charge injection, additive bypass leakage and supply current are absent.
"""
import math
from tx_calibration_chip import TxCalibrationChip

class OutputIsolation:
    def __init__(self,*,tau_s=20e-9,off_amplitude=1e-3,on_amplitude=1.):
        if not all(math.isfinite(x) for x in (tau_s,off_amplitude,on_amplitude)):
            raise ValueError('Finite isolation parameters required')
        if tau_s<=0 or not 0<off_amplitude<on_amplitude<=1:
            raise ValueError('Positive finite bandwidth, leakage and passive gain required')
        self.tau=tau_s;self.off=off_amplitude;self.on=on_amplitude
        self.time=0.;self.value=off_amplitude;self.enabled=False
    def at(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Nonmonotonic isolation time')
        target=self.on if self.enabled else self.off
        return target+(self.value-target)*math.exp(-(time-self.time)/self.tau)
    def command(self,enabled,time):
        self.value=self.at(time);self.time=time;self.enabled=bool(enabled)

class IsolatedTxCalibrationChip(TxCalibrationChip):
    """Experimental pre-isolation detector; gate opens at first valid DAC update.

Closing happens at managed quiesce. Analog reconstruction and gate charge both
persist. End of a finite burst still holds the last code until an explicit stop.
"""
    def __init__(self,isolation_options=None,**kwargs):
        self.tx_output_isolation=OutputIsolation(**(isolation_options or {}))
        super().__init__(**kwargs)
    def complete_dac(self,time):
        # Parent checks calibration validity and may quiesce instead of updating.
        before=self.dac_pipeline_updates
        result=super().complete_dac(time)
        if self.dac_pipeline_updates>before and not self.tx_output_isolation.enabled:
            first=self.played[-(self.dac_pipeline_updates-before)][0]
            self.tx_output_isolation.command(True,first)
        return result
    def quiesce(self,time,reason):
        self.tx_output_isolation.command(False,time)
        return super().quiesce(time,reason)
    def tx_pad_transfer(self,time):
        return self.tx_output_isolation.at(time)


from managed_tx_quality import ManagedTxHostChip

class IsolatedManagedTxHostChip(IsolatedTxCalibrationChip,ManagedTxHostChip):
    def reference_metrics(self):
        result=super().reference_metrics()
        gate=self.tx_output_isolation
        result['tx_output_isolation']=dict(enabled=gate.enabled,transfer=gate.at(self.time),
            tau_s=gate.tau,off_amplitude=gate.off,on_amplitude=gate.on,
            detector_location='upstream of output isolation')
        return result
