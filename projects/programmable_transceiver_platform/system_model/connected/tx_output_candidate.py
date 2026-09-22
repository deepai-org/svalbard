"""Live DAC/output integration with separate, explicit calibration fixture.

Not the managed calibration candidate. Power-only probe measurements here are
instantaneous and noiseless; coefficients are finite precision and DAC codes are
quantized in the actual sample path. Output distortion does not load the supply.
"""
import numpy as np
from tx_iq_calibration import probes,fit
from tx_output_stage import output_envelope
from tx_dac_correction import DacCorrection

PARAMETERS=dict(gain_imbalance_db=.25,phase_error_deg=2.,lo_feedthrough=.0025,cubic=.06)

def output_candidate(base):
 class OutputCandidate(base):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.tx_output_parameters=dict(PARAMETERS)
        p=probes()
        self.tx_output_calibration=fit(p,abs(output_envelope(p,np.ones(len(p)),**PARAMETERS))**2)
    def configure(self,mode,time):
        result=super().configure(mode,time)
        if self.tx.reconstruction is None:raise ValueError('Output candidate requires reconstruction')
        dc=float(self.tx.reconstruction.response([0])[0].real)
        self.tx.sample_correction=DacCorrection(self.tx_output_calibration,self.bits,dc)
        return result
    def reference_metrics(self):
        r=super().reference_metrics()
        r['tx_output_stage']=dict(parameters=self.tx_output_parameters,calibration=self.tx_output_calibration,
            fixture='Independent instantaneous noiseless probes; managed calibration not integrated',
            correction_applied=getattr(self.tx.sample_correction,'applied',0))
        return r
 return OutputCandidate
