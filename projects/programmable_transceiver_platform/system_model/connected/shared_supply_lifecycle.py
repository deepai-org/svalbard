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


class DomainSupply:
    """Passive RC domain feeds with a common resistive return.

    Mandatory parameters are hypotheses until extracted/characterized. This
    primitive supplies equations for the analog owner; it does not include
    inductance, regulator dynamics, domain currents or continuous voltage guards.
    """
    def __init__(self,names,nominal_v,feed_r,capacitance_f,common_return_r):
        import numpy as np
        self.names=tuple(names);n=len(self.names)
        if not n or len(set(self.names))!=n:raise ValueError('Unique nonempty supply names required')
        def vector(values):
            a=np.asarray(values,float)
            if a.shape!=(n,) or not np.all(np.isfinite(a)) or np.any(a<=0):raise ValueError('Positive finite supply vectors required')
            return a.copy()
        self.nominal=vector(nominal_v);self.feed_r=vector(feed_r);self.c=vector(capacitance_f)
        if not math.isfinite(common_return_r) or common_return_r<0:raise ValueError('Invalid common return resistance')
        self.common_return_r=common_return_r
        self.resistance=np.diag(self.feed_r)+common_return_r*np.ones((n,n))
        self.conductance=np.linalg.inv(self.resistance)
        self.matrix=-self.conductance/self.c[:,None]
        self.voltage=self.nominal.copy();self.time=0.
        self.source_energy_j=0.;self.feed_loss_j=0.;self.load_energy_j=0.;self.impulse_energy_j=0.

    def currents(self,values):
        import numpy as np
        current=np.asarray(values,float)
        if current.shape!=self.voltage.shape or not np.all(np.isfinite(current)) or np.any(current<0):
            raise ValueError('Finite nonnegative current per supply required')
        return current

    def derivative(self,voltage,load_current):
        import numpy as np
        v=np.asarray(voltage,float)
        if v.shape!=self.voltage.shape or not np.all(np.isfinite(v)):raise ValueError('Invalid rail state')
        return (self.conductance@(self.nominal-v)-self.currents(load_current))/self.c

    def steady(self,load_current):
        return self.nominal-self.resistance@self.currents(load_current)

    def advance(self,time,load_current):
        """Exact held-current interval; the chip owner must split all load events."""
        import numpy as np
        from scipy.linalg import expm
        if not math.isfinite(time) or time<self.time:raise ValueError('Invalid domain supply time')
        current=self.currents(load_current);dt=time-self.time
        if dt==0:return self.voltage.copy()
        equilibrium=self.steady(current);before=self.voltage
        delta=before-equilibrium;after_delta=expm(self.matrix*dt)@delta
        after=equilibrium+after_delta
        integral=np.linalg.solve(self.matrix,after_delta-delta)
        source=float(self.nominal@(current*dt-self.conductance@integral))
        load=float(current@(equilibrium*dt+integral))
        loss=float(current@self.resistance@current*dt-2*current@integral+
            .5*np.sum(self.c*(delta*delta-after_delta*after_delta)))
        if not np.all(np.isfinite(after)) or not all(math.isfinite(v) for v in (source,load,loss)):
            raise ValueError('Nonfinite domain supply solution')
        self.voltage=after;self.time=time
        self.source_energy_j+=source;self.load_energy_j+=load;self.feed_loss_j+=loss
        return after.copy()

    def draw(self,time,charges):
        """Apply an impulse only at an already serviced owner boundary."""
        import numpy as np
        if time!=self.time:raise ValueError('Domain rail must advance through its owner before an impulse')
        q=self.currents(charges);after=self.voltage-q/self.c
        if np.any(after<=0):raise ValueError('Charge exceeds positive rail envelope')
        self.impulse_energy_j+=float(.5*np.sum(self.c*(self.voltage**2-after**2)))
        self.voltage=after


def domain_controls():
    import numpy as np
    from scipy.integrate import solve_ivp
    names=('CORE','HOST_A','HOST_B','WIRE_A','WIRE_B','RF','PLL')
    r=DomainSupply(names,[3.3]*7,[2.]*7,[100e-12]*7,.1)
    current=np.arange(1,8)*.001
    independent=solve_ivp(lambda t,v:(np.linalg.solve(np.diag([2.]*7)+.1*np.ones((7,7)),3.3-v)-current)/1e-10,
        (0,2e-9),[3.3]*7,rtol=1e-11,atol=1e-13,max_step=1e-11)
    assert independent.success
    r.advance(2e-9,current)
    error=float(np.max(abs(r.voltage-independent.y[:,-1])))
    assert error<1e-9
    expected=3.3-2*current-.1*sum(current)
    assert np.max(abs(r.steady(current)-expected))<1e-14
    q=np.zeros(7);q[1]=1e-12;r.draw(r.time,q)
    r.advance(4e-9,current)
    stored=float(.5*np.sum(r.c*(r.voltage**2-r.nominal**2)))
    residual=r.source_energy_j-r.feed_loss_j-r.load_energy_j-r.impulse_energy_j-stored
    assert abs(residual)<1e-20 and r.feed_loss_j>0
    isolated=DomainSupply(names,[3.3]*7,[2.]*7,[100e-12]*7,0.)
    host=np.zeros(7);host[1]=.02
    coupled=DomainSupply(names,[3.3]*7,[2.]*7,[100e-12]*7,.1)
    isolated.advance(2e-9,host);coupled.advance(2e-9,host)
    assert isolated.voltage[6]==3.3 and coupled.voltage[6]<3.3
    assert r.source_energy_j>0 and r.impulse_energy_j>0
    split=DomainSupply(names,[3.3]*7,[2.]*7,[100e-12]*7,.1)
    whole=DomainSupply(names,[3.3]*7,[2.]*7,[100e-12]*7,.1)
    whole.advance(2e-9,current)
    for t in np.linspace(0,2e-9,41)[1:]:split.advance(float(t),current)
    subdivision=float(np.max(abs(split.voltage-whole.voltage)))
    assert subdivision<1e-12 and abs(split.source_energy_j-whole.source_energy_j)<1e-21
    before=r.voltage.copy();time=r.time;energy=r.source_energy_j
    for operation in (lambda:r.advance(r.time+1e-9,[-1.]*7),lambda:r.draw(r.time+1e-9,q)):
        try:operation()
        except ValueError:pass
        else:raise AssertionError('Invalid rail event accepted')
        assert np.array_equal(r.voltage,before) and r.time==time and r.source_energy_j==energy
    return dict(subdivision_error_v=subdivision,invalid_event_preserves_state=True,domains=len(names),maximum_ode_error_v=error,energy_residual_j=residual,
        shared_return_couples_host_to_pll=True,full_chip_connected=False,physical_qualification=False)

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

if __name__=='__main__':
    import sys
    if '--domain-controls' in sys.argv:print(domain_controls())
    else:main()
