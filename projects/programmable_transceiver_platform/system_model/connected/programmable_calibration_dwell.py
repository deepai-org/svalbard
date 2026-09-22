"""Candidate managed dwell register and bounded calibration completion polling."""
from tx_calibration_sequence import TxCalibrationSequence
from buffered_shared_detector import BufferedSharedPhaseChip
from managed_resources import command

class DwellSequence(TxCalibrationSequence):
    def __init__(self,*args,probe_dwell_s=2e-6,**kwargs):
        super().__init__(*args,**kwargs);self.probe_dwell_s=probe_dwell_s
    def start(self,time,*,dwell=None,**kwargs):
        return super().start(time,dwell=self.probe_dwell_s if dwell is None else dwell,**kwargs)

class ProgrammableDwellChip(BufferedSharedPhaseChip):
    TILE_COMMANDS=BufferedSharedPhaseChip.TILE_COMMANDS+('tx_cal_dwell',)
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.tx_cal_dwell_ticks=80
        old=self.tx_cal
        self.tx_cal=DwellSequence(self.tx_detector,self._probe,self._commit,self._release,
            relative_gain=old.relative_gain,probe_dwell_s=80*self.control_period)
    def execute_management(self,operation,payload,time):
        if operation=='tx_cal_dwell':
            if type(payload) is not int or not 80<=payload<=4000:
                raise ValueError('Dwell requires 80..4000 control-clock ticks')
            self._require_target_free()
            if not self.quiet() or self.tx.queue or self.adc_pending or self.maintenance_pending is not None:
                raise ValueError('Dwell configuration requires quiet free converters')
            self.tx_cal_dwell_ticks=payload
            self.tx_cal.probe_dwell_s=payload*self.control_period
            return dict(value=payload)
        return super().execute_management(operation,payload,time)

def calibrate_until_complete(c,timeout_s=1e-3):
    """Use serialized status/commit; never bypass ownership or clock readiness."""
    import math
    if not math.isfinite(timeout_s) or timeout_s<=0:raise ValueError('Invalid timeout')
    deadline=c.time+timeout_s
    started=False
    try:
        while True:
            status=command(c,'tx_cal_status');assert status['accepted'],status
            if c.time>deadline:raise TimeoutError('Calibration readiness timeout')
            if status['value']&(1<<10):break
        reply=command(c,'tx_cal_start');assert reply['accepted'],reply
        started=True
        while True:
            status=command(c,'tx_cal_status');assert status['accepted'],status
            if c.time>deadline:raise TimeoutError('Calibration completion timeout')
            state=status['value']&255
            if state==3:break
            if state==5:raise RuntimeError('Calibration cancelled')
        result=command(c,'tx_cal_commit',reply['value']);assert result['accepted'],result
        if c.time>deadline:raise TimeoutError('Calibration commit exceeded deadline')
        return result
    except TimeoutError:
        # Cleanup is a real serialized transaction and can finish after deadline.
        # Do not abort a calibration we never started while waiting for readiness.
        if started:
            aborted=command(c,'tx_cal_abort')
            if not aborted['accepted']:raise RuntimeError('Calibration timeout cleanup rejected')
        raise
