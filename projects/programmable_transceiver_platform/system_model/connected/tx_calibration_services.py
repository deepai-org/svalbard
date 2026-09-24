"""Shared TX calibration lifecycle; subclasses supply clock and monitor behavior.

The monitor is an assumed independent power ADC. This does not yet reserve the
shared I ADC or model monitor loading. External RF isolation is not qualified.
"""
import math
import numpy as np
from tx_reconstruction import Reconstruction
from tx_power_detector import PowerDetector
from tx_detector_transfer import ImpairedPowerDetector
from tx_output_terms import output_terms
from tx_output_candidate import PARAMETERS
from tx_calibration_sequence import TxCalibrationSequence
from tx_dac_correction import DacCorrection
from tx_iq_calibration import probes

class TxCalibrationServices:
    def __init__(self,tx_detector_options=None,tx_relative_gain=False,**kwargs):
        self.tx_cal=None;self.tx_detector=None
        super().__init__(**kwargs)
        self.tx.set_reconstruction(Reconstruction())
        self.tx_detector_options=dict(tx_detector_options or {})
        self.tx_detector=ImpairedPowerDetector(**self.tx_detector_options) if tx_detector_options is not None else PowerDetector()
        self.tx_cal=TxCalibrationSequence(self.tx_detector,self._probe,self._commit,self._release,relative_gain=tx_relative_gain)
        self.tx_output_parameters=dict(PARAMETERS)
        self.tx.admission_check=self._require_tx_calibrated

    def configure_rf_carrier(self,frequency_hz):
        result=super().configure_rf_carrier(frequency_hz)
        if self.tx_cal is not None and self.tx_cal.valid:
            self.tx_cal.cancel(self.time,'RF carrier retarget invalidated calibration')
        return result

    def _probe(self,time,value):
        dc=float(self.tx.reconstruction.response([0])[0].real)
        self.tx.apply_sample(value/dc,time)

    def _commit(self,cal):
        dc=float(self.tx.reconstruction.response([0])[0].real)
        self.tx.sample_correction=DacCorrection(cal,getattr(self,'bits',12),dc)

    def _release(self,time):
        self.tx.advance(time);self.tx.held=0j

    def _require_target_free(self):
        if self.tx_cal is not None and self.tx_cal.busy:raise ValueError('TX calibration owns analog target')
        return super()._require_target_free()

    def execute_management(self,operation,payload,time):
        s=self.tx_cal
        if operation=='resource_count':
            if payload:raise ValueError('Reserved resource-count payload')
            return dict(value=11)
        if operation=='resource_status' and (payload==10 or s is not None and s.busy and payload in (1,8)):
            busy=s is not None and s.busy
            return dict(value=(11 if busy else 0)|(int(busy)<<8)|(int(busy)<<10))
        if operation.startswith('tx_cal_'):
            if operation=='tx_cal_start':
                if payload:raise ValueError('Reserved payload')
                self._require_target_free()
                if not self.quiet() or self.tx.queue or not self._tx_clock_ready():
                    raise ValueError('Quiet empty TX and qualified locked RF clock required')
                # New search must not apply previously installed correction to probes.
                self.tx.sample_correction=lambda t,z:z
                dc=float(self.tx.reconstruction.response([0])[0].real);z=probes()/dc
                z=(np.round(z.real*2048)+1j*np.round(z.imag*2048))/2048*dc
                return dict(value=s.start(time,epoch=self.epoch,quiet=True,probes=list(z)))
            if operation=='tx_cal_commit':
                s.accept(time,epoch=self.epoch,generation=payload,quiet=self.quiet() and self._tx_clock_ready());return {}
            if payload:raise ValueError('Reserved payload')
            if operation=='tx_cal_abort':
                if self.state=='active':self.quiesce(time,'TX calibration invalidated while active')
                else:s.cancel(time,'management abort')
                return {}
            if operation=='tx_cal_status':
                return dict(value=('idle','settle','convert','ready','done','cancelled').index(s.state)|(int(s.busy)<<8)|(int(s.valid)<<9)|(int(self._tx_clock_ready() and self.quiet() and not self.tx.queue and not s.busy)<<10))
        if s is not None and s.busy and operation not in ('status','stop','resource_count','resource_status'):
            raise ValueError('TX calibration owns maintenance resources')
        result=super().execute_management(operation,payload,time)
        if operation in ('rf_coarse_start','configure_rx','tile_configure') and s.valid:
            s.cancel(time,'analog configuration changed')
        return result

    def _require_tx_calibrated(self):
        if not self.tx_cal.valid or not self._tx_clock_ready() or self.tx_cal.epoch!=self.epoch:
            raise ValueError('RF TX requires current committed calibration and locked clock')

    def complete_dac(self,time):
        if self.dac_pending:
            try:self._require_tx_calibrated()
            except ValueError:
                self.quiesce(time,'TX calibration invalid at DAC completion');return
        return super().complete_dac(time)

    def descriptor(self,*args,**kwargs):
        self._require_tx_calibrated();return super().descriptor(*args,**kwargs)

    def schedule(self,*args,**kwargs):
        self._require_tx_calibrated();return super().schedule(*args,**kwargs)

    def configure(self,mode,time):
        self._require_target_free()
        result=super().configure(mode,time)
        if self.tx_cal.valid:self._commit(self.tx_cal.candidate)
        return result

    def set_reference(self,present,time):
        result=super().set_reference(present,time)
        if not present and self.tx_cal is not None:
            self.tx_cal.cancel(time,'reference loss')
        return result

    def quiesce(self,time,reason):
        if self.tx_cal is not None:self.tx_cal.cancel(time,reason)
        return super().quiesce(time,reason)

    def advance(self,time):
        if self.tx_cal is None:return super().advance(time)
        if not math.isfinite(time) or time<self.time:raise ValueError('Invalid time')
        while self.time<time:
            event=self.tx_cal.next_event if self.tx_cal.next_event is not None else math.inf
            command=self.command_events[0][0] if self.command_events else math.inf
            end=min(time,event,command)
            self._advance_tx_monitor(end)
            super().advance(end)
            self.tx_cal.service(self.time,epoch=self.epoch,quiet=self.quiet() and self._tx_clock_ready())
        super().advance(time)
        self.tx_cal.service(self.time,epoch=self.epoch,quiet=self.quiet() and self._tx_clock_ready())
