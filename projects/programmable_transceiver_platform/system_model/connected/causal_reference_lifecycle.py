"""Assumed finite-charge reference, driven causally by actual ADC conversions."""
import json,math
from chip_model import P,encode_iq
from loop_driven_edges import PhasedChip
from sustained_lifecycle import run

class Reference:
    def __init__(self,resistance=1000,capacitance=100e-12,load_capacitance=1e-12):
        if not all(math.isfinite(v) for v in (resistance,capacitance,load_capacitance)) or resistance<=0 or capacitance<=0 or not 0<=load_capacitance<capacitance:
            raise ValueError('Invalid reference parameters')
        self.r=resistance;self.c=capacitance;self.load=load_capacitance
        self.voltage=1.;self.time=0.;self.minimum=1.;self.charge=0.;self.samples=0;self.dac_updates=0;self.dac_charge=0.;self.last_dac=0j
    def advance(self,time):
        if time<self.time:raise ValueError('Nonmonotonic reference time')
        self.voltage=1+(self.voltage-1)*math.exp(-(time-self.time)/(self.r*self.c))
        self.time=time
    def dac_update(self,time,value,load):
        if not math.isfinite(load) or not 0<=load<self.c:raise ValueError('Invalid DAC reference load')
        self.advance(time);span=self.voltage
        if span<=.1:raise ValueError('Reference outside modeled operating range')
        activity=min(1.,(abs(value.real-self.last_dac.real)+abs(value.imag-self.last_dac.imag))/4)
        q=load*span*(.25+.75*activity)
        self.voltage-=q/self.c;self.charge+=q;self.dac_charge+=q;self.dac_updates+=1
        self.minimum=min(self.minimum,self.voltage);self.last_dac=value
        return value*span

    def sample(self,time,value):
        if not math.isfinite(value.real) or not math.isfinite(value.imag):raise ValueError('Nonfinite reference input')
        self.advance(time)
        span=self.voltage
        if span<=.1:raise ValueError('Reference outside modeled operating range')
        normalized=value/span
        # One aggregate conversion impulse after sampling. Not SAR bit timing.
        activity=min(1.,abs(value.real)+abs(value.imag))
        q=self.load*span*(.25+.75*activity)
        self.voltage-=q/self.c;self.charge+=q;self.samples+=1
        self.minimum=min(self.minimum,self.voltage)
        return normalized

class ReferenceChip(PhasedChip):
    def __init__(self,resistance=1000,capacitance=100e-12,load_capacitance=1e-12,dac_reference_load_capacitance=None,shared_dac_reference=True,**kwargs):
        super().__init__(**kwargs)
        self.adc_reference=Reference(resistance,capacitance,load_capacitance)
        self.dac_reference_load=dac_reference_load_capacitance
        if dac_reference_load_capacitance is not None and (not math.isfinite(dac_reference_load_capacitance) or not 0<=dac_reference_load_capacitance<capacitance):
            raise ValueError('Invalid DAC reference loading')
        self.shared_dac_reference=shared_dac_reference
        self.dac_reference=self.adc_reference if shared_dac_reference else Reference(resistance,capacitance,0)
        self.tx.dac_transfer=self.reference_dac
    def reference_dac(self,time,value):
        if self.dac_reference_load is None:return value
        return self.dac_reference.dac_update(time,value,self.dac_reference_load)
    def convert_adc(self,value):
        return super().convert_adc(self.adc_reference.sample(self.tx.time,value))
    def reference_metrics(self):
        r=self.adc_reference
        return dict(adc_quantization=dict(self.adc_diagnostics),dac_reference=dict(enabled=self.dac_reference_load is not None,shared=self.shared_dac_reference,
                    minimum_span_v=self.dac_reference.minimum,updates=self.dac_reference.dac_updates,
                    charge_c=self.dac_reference.dac_charge,load_capacitance_f=self.dac_reference_load),
                    minimum_span_v=r.minimum,total_load_charge_c=r.charge,conversions=r.samples,
                    resistance_ohm=r.r,capacitance_f=r.c,load_capacitance_f=r.load)


def controls():
    r=Reference();z=.4+.2j
    assert r.sample(0,z)==z
    q=1e-12*(.25+.75*.6)
    assert abs(r.voltage-(1-q/100e-12))<1e-15
    expected=1-q/100e-12*math.exp(-25e-9/(1000*100e-12))
    assert abs(r.sample(25e-9,z)-z/expected)<1e-14
    a=Reference();b=Reference();a.sample(0,z);b.sample(0,z)
    a.advance(100e-9)
    for i in range(1,101):b.advance(i*1e-9)
    assert abs(a.voltage-b.voltage)<1e-14
    # Zero loading remains exactly ideal, irrespective of sample history.
    c=Reference(load_capacitance=0)
    assert all(c.sample(i*25e-9,z)==z for i in range(100))


def main():
    controls();rows=[]
    for mode in (0,1):
        for resistance,capacitance,load in [(1000,100e-12,0),(100,200e-12,1e-12),(5000,50e-12,1e-12)]:
            factory=lambda **kw:ReferenceChip(resistance,capacitance,load,**kw)
            row=run(mode,100,chip_factory=factory,disturbance_sign=1)
            # Compare zero loading to the same clock intervention, not a different waveform.
            if load==0:
                baseline=run(mode,100,chip_factory=PhasedChip,disturbance_sign=1)
                assert row['adc_checksum']==baseline['adc_checksum']
            else:
                assert row['reference_metrics']['minimum_span_v']<1
                if resistance==5000:assert row['adc_checksum']!=baseline['adc_checksum']
            assert row['reference_metrics']['conversions']==row['rf_samples_each_direction']
            rows.append(row)
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Assumed aggregate charge law, not validated SAR switching or reference-buffer dynamics.',
        'Current conversion uses pre-impulse span; intra-conversion reference settling is omitted.',
        'Resistance/capacitance endpoints are sensitivity examples, not process/package worst-case bounds.',
        'RF reference state persists across reset via elapsed-time recovery; shared DAC/PLL supply coupling remains absent.'])
    (P/'evidence/connected-causal-reference-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six sustained causal-reference cases, zero-load equivalence and analytic controls')

if __name__=='__main__':main()
