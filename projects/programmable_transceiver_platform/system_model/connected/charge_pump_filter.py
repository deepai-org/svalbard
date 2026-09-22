"""Exact passive two-capacitor charge-pump filter between current transitions.

Pump/VCO node v has shunt Cf. A resistor connects v to node w with shunt Cs.
Current is an ideal imposed pulse; compliance violations are reported, not hidden
by clipping capacitor voltage or assuming a predictive transistor current law.
"""
import math


class ChargePumpFilter:
    def __init__(self,resistance,fast_capacitance,slow_capacitance,voltage=0.,limit_v=1.):
        if not all(math.isfinite(x) and x>0 for x in (resistance,fast_capacitance,slow_capacitance,limit_v)) or not math.isfinite(voltage):
            raise ValueError('Invalid pump-filter parameters')
        self.r=resistance;self.cf=fast_capacitance;self.cs=slow_capacitance
        self.total=self.cf+self.cs;self.pole=self.total/(self.r*self.cf*self.cs)
        self.v=self.w=voltage;self.time=0.;self.limit=limit_v
        self.minimum=self.maximum=voltage
        self.charge=0.;self.source_work=0.;self.resistor_loss=0.;self.voltage_integral=0.
        self.initial_energy=self.energy

    @property
    def energy(self):return .5*(self.cf*self.v*self.v+self.cs*self.w*self.w)

    @property
    def compliant(self):return -self.limit<=self.minimum and self.maximum<=self.limit

    @classmethod
    def from_gains(cls,kp,ki,pump_current,fast_fraction,**kwargs):
        if not all(math.isfinite(x) and x>0 for x in (kp,ki,pump_current)) or not 0<fast_fraction<1:
            raise ValueError('Invalid PI-to-filter mapping')
        # Preserve low-frequency integral gain and the constant term of impedance.
        total=pump_current/ki;slow=(1-fast_fraction)*total
        resistance=kp/(pump_current*(1-fast_fraction)**2)
        return cls(resistance,fast_fraction*total,slow,**kwargs)

    def advance(self,time,current):
        if not all(math.isfinite(x) for x in (time,current)) or time<self.time:
            raise ValueError('Invalid pump pulse interval')
        dt=time-self.time
        if dt==0:return
        q0=self.cf*self.v+self.cs*self.w;d0=self.v-self.w
        equilibrium=current/(self.cf*self.pole);difference=d0-equilibrium
        response=-math.expm1(-self.pole*dt)/self.pole
        decay=math.exp(-self.pole*dt)
        integral_d=equilibrium*dt+difference*response
        integral_v=(q0*dt+current*dt*dt/2+self.cs*integral_d)/self.total
        loss=(equilibrium**2*dt+2*equilibrium*difference*response+
              difference**2*(-math.expm1(-2*self.pole*dt))/(2*self.pole))/self.r
        q1=q0+current*dt;d1=equilibrium+difference*decay
        v1=(q1+self.cs*d1)/self.total;w1=(q1-self.cf*d1)/self.total
        extrema=[self.v,v1]
        # dv/dt=(I-d/R)/Cf can have one interior extremum. Check it exactly.
        if difference:
            ratio=(current*self.r-equilibrium)/difference
            if decay<ratio<1:
                t=-math.log(ratio)/self.pole
                extrema.append((q0+current*t+self.cs*current*self.r)/self.total)
        self.minimum=min(self.minimum,*extrema);self.maximum=max(self.maximum,*extrema)
        self.charge+=current*dt;self.source_work+=current*integral_v
        self.resistor_loss+=loss;self.voltage_integral+=integral_v
        self.v,self.w,self.time=v1,w1,time

    def metrics(self):
        return dict(resistance_ohm=self.r,fast_capacitance_f=self.cf,slow_capacitance_f=self.cs,
            extra_pole_hz=self.pole/(2*math.pi),minimum_v=self.minimum,maximum_v=self.maximum,
            compliance_limit_v=self.limit,ideal_current_within_compliance=self.compliant,
            energy_residual_j=self.energy-self.initial_energy-self.source_work+self.resistor_loss)
