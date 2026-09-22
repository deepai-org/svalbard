"""Calibrated TX output-stage observation during simultaneous four-path traffic."""
import cmath
import hashlib
import json
import math
import time
from pathlib import Path
import service_traffic as scenario
from tx_services import FastTxServiceChip
from tx_output_stage import output_envelope
from managed_resources import command
from rf_quality_screen import quality
Original=scenario.ServiceChip

class OutputChip(FastTxServiceChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        if kwargs.get('load_capacitance')==0:
            self.tx_output_parameters=dict(gain_imbalance_db=0.,phase_error_deg=0.,lo_feedthrough=0j,cubic=0.)
        self.tx_calibration_record=None
    def external_source(self,values,start,period,offset_hz=0.):
        reply=command(self,'tx_cal_start');assert reply['accepted'],reply
        self.advance(self.time+25e-6)
        assert self.tx_cal.state=='ready'
        assert command(self,'tx_cal_commit',reply['value'])['accepted']
        self.tx_calibration_record=dict(probes=len(self.tx_cal.powers),fit=self.tx_cal.candidate)
        self.tx_probe.clear();self.probe_times.clear()
        return super().external_source(values,self.time,period,offset_hz)
    def convert_adc(self,value):
        word=super().convert_adc(value)
        t=self.tx.time
        rotation=cmath.exp(1j*(self.tx.tx_lo_phase+2*math.pi*self.tx.tx_lo_hz*t))
        self.tx_probe[-1]=complex(output_envelope(self.tx.output_value(t),rotation,**self.tx_output_parameters))
        return word


def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    start=time.monotonic();p=scenario.architecture.P
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Independent calibration detector ADC, not shared ADC/loading.',
                     'Output-stage distortion reaches independent TX probe; nonlinear internal loopback is not tested.',
                     'Finite memoryless cubic output model, no loaded-pad network or emission mask.',
                     'Assumed parameters; external frozen-gain quality screen remains provisional.'])
    output=p/'evidence/fast-tx-traffic.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save();chips=[]
    class RecordedChip(OutputChip):
        def __init__(self,**kwargs):super().__init__(**kwargs);chips.append(self)
    scenario.ServiceChip=RecordedChip
    try:
        for mode in (0,1):
            rx0,tx0,t0,_=scenario.simulate(mode,False)
            rx,tx,t,result=scenario.simulate(mode,True)
            assert t==t0
            rq=quality(rx0,rx);tq=quality(tx0,tx)
            result.update(mode=mode,rx_quality=rq,tx_quality=tq,tx_calibration=chips[-1].tx_calibration_record)
            report['cases'].append(result);save()
            print(mode,rq['corrected_relative_rms'],tq['corrected_relative_rms'],flush=True)
            assert rq['screen_pass'] and tq['screen_pass']
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:scenario.ServiceChip=Original;save()

if __name__=='__main__':main()
