"""Host switching charge drives an assumed RC rail and receiver gain sensitivity."""
import json,math
from chip_model import P
from receiver_impairments import ImpairedChip
from sustained_lifecycle import run

class Supply:
    def __init__(self,resistance=100,capacitance=100e-12):
        if not all(math.isfinite(x) and x>0 for x in (resistance,capacitance)):
            raise ValueError('Invalid supply impedance')
        self.r=resistance;self.c=capacitance;self.delta=0.;self.time=0.
        self.minimum=0.;self.charge=0.
    def advance(self,time):
        if time<self.time:raise ValueError('Nonmonotonic supply time')
        self.delta*=math.exp(-(time-self.time)/(self.r*self.c));self.time=time
    def draw(self,time,charge):
        if charge<0 or not math.isfinite(charge):raise ValueError('Invalid switching charge')
        self.advance(time);self.delta-=charge/self.c
        self.minimum=min(self.minimum,self.delta);self.charge+=charge

class CoupledChip(ImpairedChip):
    def __init__(self,coupling_per_v=0,charge_per_transition=100e-15,return_charge_per_transition=0,dac_coupling_per_v=0,**kwargs):
        super().__init__(**kwargs)
        if not math.isfinite(coupling_per_v) or not math.isfinite(charge_per_transition) or charge_per_transition<0:
            raise ValueError('Invalid coupling')
        if not math.isfinite(return_charge_per_transition) or return_charge_per_transition<0:raise ValueError('Invalid return switching charge')
        self.return_q=return_charge_per_transition;self.previous_return_word=0;self.return_transitions=0;self.return_charge=0.
        self.supply=Supply();self.coupling=coupling_per_v;self.q=charge_per_transition
        if not math.isfinite(dac_coupling_per_v):raise ValueError('Invalid DAC coupling')
        self.dac_coupling=dac_coupling_per_v;self.dac_gain_min=self.dac_gain_max=1.;self.dac_updates=0
        self.tx.dac_gain=self.supply_dac_gain
        self.previous_host_word=0;self.transitions=0;self.gain_min=self.gain_max=1.
    def supply_dac_gain(self,time):
        self.supply.advance(time)
        gain=1+self.dac_coupling*self.supply.delta
        if gain<=0:raise ValueError('DAC supply outside linear model')
        self.dac_updates+=1
        self.dac_gain_min=min(self.dac_gain_min,gain);self.dac_gain_max=max(self.dac_gain_max,gain)
        return gain

    def supply_impulse(self,time,delta_v):
        pass

    def feed(self,word,epoch,time):
        # Existing edge ordering completes ADC events at this time first.
        super().feed(word,epoch,time)
        changes=(word^self.previous_host_word).bit_count()+1 # Include host clock edge.
        self.supply.draw(time,changes*self.q)
        self.supply_impulse(time,-changes*self.q/self.supply.c)
        self.previous_host_word=word;self.transitions+=changes
    def emitted_return_word(self,word,time):
        changes=(word^self.previous_return_word).bit_count()+1
        charge=changes*self.return_q
        self.supply.draw(time,charge)
        self.supply_impulse(time,-charge/self.supply.c)
        self.previous_return_word=word;self.return_transitions+=changes;self.return_charge+=charge

    def convert_adc(self,value):
        self.supply.advance(self.tx.time)
        gain=1+self.coupling*self.supply.delta
        if gain<=0:raise ValueError('Supply/gain excursion outside linear model')
        self.gain_min=min(self.gain_min,gain);self.gain_max=max(self.gain_max,gain)
        return super().convert_adc(value*gain)
    def reference_metrics(self):
        r=super().reference_metrics()
        r['dac_supply']=dict(coupling_per_v=self.dac_coupling,updates=self.dac_updates,gain_min=self.dac_gain_min,gain_max=self.dac_gain_max)
        r['supply']=dict(minimum_delta_v=self.supply.minimum,total_charge_c=self.supply.charge,
            transitions=self.transitions,return_transitions=self.return_transitions,return_charge_c=self.return_charge,coupling_per_v=self.coupling,gain_min=self.gain_min,gain_max=self.gain_max)
        return r


def controls():
    a=Supply();b=Supply();a.draw(0,1e-12);b.draw(0,1e-12)
    assert abs(a.delta+.01)<1e-16
    a.advance(10e-9)
    for i in range(1,101):b.advance(i*1e-10)
    assert abs(a.delta+.01/math.e)<1e-16 and abs(a.delta-b.delta)<1e-15
    a.draw(10e-9,0);assert abs(a.delta-b.delta)<1e-15


def main():
    controls();rows=[]
    for mode in (0,1):
        baseline=run(mode,100,chip_factory=ImpairedChip,disturbance_sign=1)
        for coupling in (0,-2,2):
            factory=lambda **kw:CoupledChip(coupling_per_v=coupling,**kw)
            row=run(mode,100,chip_factory=factory,disturbance_sign=1)
            m=row['reference_metrics']['supply']
            assert m['minimum_delta_v']<0 and m['total_charge_c']>0
            if coupling==0:assert row['adc_sha256']==baseline['adc_sha256']
            else:
                assert row['adc_sha256']!=baseline['adc_sha256']
                assert m['gain_min']<1 if coupling>0 else m['gain_max']>1
            rows.append(row)
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Assumed lumped RC and charge per host transition, not extracted package/substrate impedance.',
        'Coupling currently changes sampled receiver gain only, not PLL frequency, DAC amplitude or digital thresholds.',
        'Input host bus only; return bus and internal switching current remain absent.',
        'Signed sensitivities are illustrative endpoints, not a proven worst-case uncertainty range.'])
    (P/'evidence/connected-shared-supply-lifecycle.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed six sustained shared-supply cases and analytic RC controls')

if __name__=='__main__':main()
