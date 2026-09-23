"""Reusable fast chip: explicit configuration, no automatic test preparation."""
import cmath
import math
from tx_services import FastTxServiceChip
from tx_output_stage import output_envelope
from detector_readout_settling import BufferedSharedDetector, sample_shared_detector
from output_loopback import connect

class TransceiverChip(FastTxServiceChip):
    TILE_COMMANDS=FastTxServiceChip.TILE_COMMANDS+('configure_rx_gain',)
    def __init__(self,*,output_parameters=None,readout_tau_s=20e-9,rx_filter=(5,9157407.055691985),**kwargs):
        kwargs.setdefault('adc_latency_s',30e-9)
        super().__init__(**kwargs)
        if output_parameters is not None:
            # Validate a complete, explicit constructor-level physical fixture.
            parameters=dict(output_parameters)
            expected={'gain_imbalance_db','phase_error_deg','lo_feedthrough','cubic'}
            if set(parameters)!=expected:raise ValueError('Require all output-stage parameters')
            output_envelope(0j,1+0j,**parameters)
            self.tx_output_parameters=parameters
        self.tx_adc_samples=0
        detector=BufferedSharedDetector(self._sample_detector,readout_tau_s=readout_tau_s,
            bits=12,latency=self.adc_latency)
        self.tx_detector=detector;self.tx_cal.detector=detector
        # Intended receiver selectivity from mathematical-top-profile.json.
        # Explicit None retains the single-pole diagnostic comparison.
        if rx_filter is not None:self.tx.set_butterworth(*rx_filter)
        connect(self)
    _sample_detector=sample_shared_detector
    def configure_rx_gain(self,gain):
        """Select existing baseband gain without retuning the filter topology."""
        if isinstance(gain,bool) or gain not in (.5,1.,2.):
            raise ValueError('Unsupported receiver gain')
        if (self.session.armed or self.cal.busy or self.tx_cal.busy or
                self.adc_left or self.adc_pending or self.maintenance_pending is not None):
            raise ValueError('Receiver gain requires disarmed unowned ADC')
        self.rx_gain=float(gain)
    def execute_management(self,operation,payload,time):
        if operation=='configure_rx_gain':
            if payload not in (0,1,2):raise ValueError('Reserved receiver gain encoding')
            self.configure_rx_gain((.5,1.,2.)[payload])
            return dict(value=payload)
        if operation=='tx_cal_start' and (self.adc_pending or self.maintenance_pending is not None):
            raise ValueError('Existing ADC conversion pending')
        if operation=='resource_status' and payload==0 and self.tx_cal.busy:
            return dict(value=11|256|1024)
        return super().execute_management(operation,payload,time)
    def capture(self,*args,**kwargs):
        if self.tx_cal.busy:raise ValueError('TX calibration owns shared ADC')
        return super().capture(*args,**kwargs)
    def convert_adc(self,value):
        word=super().convert_adc(value)
        t=self.tx.time
        rotation=cmath.exp(1j*(self.tx.tx_lo_phase+2*math.pi*self.tx.tx_lo_hz*t))
        self.tx_probe[-1]=complex(output_envelope(self.tx.output_value(t),rotation,**self.tx_output_parameters))
        return word
