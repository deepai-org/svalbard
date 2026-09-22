"""Equal-duration managed TX calibration preparation for live waveform checks."""
from tx_calibration_chip import TxCalibrationChip
from host_activation_chip import HostActivationChip
from managed_resources import command

class ManagedTxHostChip(TxCalibrationChip,HostActivationChip):
    def reference_metrics(self):
        r=super().reference_metrics()
        r['tx_calibration']=dict(state=self.tx_cal.state,committed=self.tx_cal.valid,
            probe_powers=self.tx_cal.powers,candidate=self.tx_cal.candidate,
            detector_options=self.tx_detector_options,detector_bits=self.tx_detector.bits,detector_tau_s=1/self.tx_detector.pole,
            output_parameters=self.tx_output_parameters,
            correction_applied=getattr(self.tx.sample_correction,'applied',0))
        return r

def calibration_window(ideal):
    def prepare(c):
        start=c.time;end=start+100e-6
        if not ideal:
            deadline=start+50e-6
            while True:
                status=command(c,'tx_cal_status');assert status['accepted']
                if status['value'] & (1<<10):break
                if c.time>=deadline:raise TimeoutError('RF calibration readiness timeout')
            reply=command(c,'tx_cal_start');assert reply['accepted'],reply
            c.advance(c.time+20e-6)
            assert c.tx_cal.state=='ready',c.tx_cal.state
            reply=command(c,'tx_cal_commit',reply['value']);assert reply['accepted'],reply
        if c.time>end:raise TimeoutError('Calibration preparation exceeded reserved window')
        c.advance(end)
    return prepare

class UncorrectedManagedTxHostChip(ManagedTxHostChip):
    """Diagnostic control: identical probe/command sequence, no data correction."""
    def _commit(self,cal):
        super()._commit(cal)
        self.tx.sample_correction=lambda t,z:z
    def reference_metrics(self):
        r=super().reference_metrics()
        r['tx_calibration']['diagnostic_correction_bypass']=True
        return r
