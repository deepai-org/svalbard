"""Assumed linear pump-current rolloff near compliance, without voltage clipping."""
import copy
import math
from charge_pump_filter import ChargePumpFilter


class CompliantPumpFilter(ChargePumpFilter):
    def __init__(self,*args,headroom_v=.1,max_step_s=1e-9,**kwargs):
        super().__init__(*args,**kwargs)
        if not math.isfinite(headroom_v) or not 0<headroom_v<=self.limit or not math.isfinite(max_step_s) or max_step_s<=0:
            raise ValueError('Invalid pump compliance envelope')
        self.headroom=headroom_v;self.max_step=max_step_s
        self.rolloff_time=0.;self.minimum_current_fraction=1.

    def pump_current(self,voltage,command):
        if command==0:return 0.
        sign=1 if command>0 else -1
        return command*min(1.,max(0.,(self.limit-sign*voltage)/self.headroom))

    def rhs(self,state,command):
        v,w=state[:2];current=self.pump_current(v,command);branch=(v-w)/self.r
        return ((current-branch)/self.cf,branch/self.cs,current,current*v,(v-w)*branch,v)

    def rk(self,state,step,command):
        a=self.rhs(state,command)
        b=self.rhs(tuple(y+step*x/2 for y,x in zip(state,a)),command)
        c=self.rhs(tuple(y+step*x/2 for y,x in zip(state,b)),command)
        d=self.rhs(tuple(y+step*x for y,x in zip(state,c)),command)
        return tuple(y+step*(aa+2*bb+2*cc+dd)/6 for y,aa,bb,cc,dd in zip(state,a,b,c,d))

    def affine_rolloff(self,time,command):
        sign=1 if command>0 else -1
        if sign*self.v<self.limit-self.headroom:return False
        dt=time-self.time;conductance=abs(command)/self.headroom
        a=(1/self.r+conductance)/self.cf;b=1/(self.r*self.cf);c=1/(self.r*self.cs)
        fast=-(a+c+math.sqrt((a-c)**2+4*b*c))/2
        slow=(conductance*c/self.cf)/fast
        equilibrium=sign*self.limit;x=self.v-equilibrium;y=self.w-equilibrium
        av=(-a*x+b*y-slow*x)/(fast-slow);bv=x-av
        aw=(c*x-c*y-slow*y)/(fast-slow);bw=y-aw
        def integral(rate):return math.expm1(rate*dt)/rate
        def value(first,second,t):return equilibrium+first*math.exp(fast*t)+second*math.exp(slow*t)
        extrema=[self.v,value(av,bv,dt)]
        if fast*av and -(slow*bv)/(fast*av)>0:
            t=math.log(-(slow*bv)/(fast*av))/(fast-slow)
            if 0<t<dt:extrema.append(value(av,bv,t))
        if min(sign*v for v in extrema)<self.limit-self.headroom:return False
        if max(abs(v) for v in extrema)>self.limit:return False
        terms=av*integral(fast)+bv*integral(slow)
        square=av*av*integral(2*fast)+2*av*bv*integral(fast+slow)+bv*bv*integral(2*slow)
        da,db=av-aw,bv-bw
        self.charge-=conductance*terms
        self.source_work-=conductance*(equilibrium*terms+square)
        self.resistor_loss+=(da*da*integral(2*fast)+2*da*db*integral(fast+slow)+db*db*integral(2*slow))/self.r
        self.voltage_integral+=equilibrium*dt+terms
        self.v=value(av,bv,dt);self.w=value(aw,bw,dt);self.time=time
        self.minimum=min(self.minimum,*extrema);self.maximum=max(self.maximum,*extrema)
        self.rolloff_time+=dt
        self.minimum_current_fraction=min(self.minimum_current_fraction,
            min(abs(self.pump_current(v,command)/command) for v in extrema))
        return True

    def advance(self,time,current):
        if not all(math.isfinite(x) for x in (time,current)) or time<self.time:
            raise ValueError('Invalid pump interval')
        if time==self.time:return
        if current and self.affine_rolloff(time,current):return
        trial=copy.copy(self);trial.minimum=trial.maximum=self.v
        ChargePumpFilter.advance(trial,time,current)
        plateau=(trial.maximum<=self.limit-self.headroom if current>0 else
                 trial.minimum>=-self.limit+self.headroom)
        if current==0 or plateau:
            trial.minimum=min(self.minimum,trial.minimum);trial.maximum=max(self.maximum,trial.maximum)
            self.__dict__.update(trial.__dict__);return
        # Voltages, delivered charge, source work, resistor loss and integral(v)
        # are integrated together. No state is projected onto a voltage rail.
        state=(self.v,self.w,0.,0.,0.,0.)
        while self.time<time:
            self.v,self.w=state[:2]
            trial=copy.copy(self)
            if trial.affine_rolloff(time,current):
                trial.charge+=state[2];trial.source_work+=state[3]
                trial.resistor_loss+=state[4];trial.voltage_integral+=state[5]
                self.__dict__.update(trial.__dict__);return
            h=min(time-self.time,self.max_step,1/(8*self.pole),self.cf*self.headroom/(8*abs(current)))
            while True:
                full=self.rk(state,h,current);half=self.rk(state,h/2,current)
                fine=self.rk(half,h/2,current)
                error=max(abs(full[i]-fine[i]) for i in (0,1))
                inside=max(abs(fine[0]),abs(fine[1]),abs(half[0]),abs(half[1]))<=self.limit
                if error<=1e-10 and abs(full[5]-fine[5])<=1e-19 and inside:break
                h/=2
                if h<1e-17:raise ArithmeticError('Compliance integration did not converge')
            voltages=(state[0],half[0],fine[0])
            self.minimum=min(self.minimum,*voltages);self.maximum=max(self.maximum,*voltages)
            fraction=min(abs(self.pump_current(v,current)/current) for v in voltages)
            if fraction<1:self.rolloff_time+=h
            self.minimum_current_fraction=min(self.minimum_current_fraction,fraction)
            state=fine;self.time=min(time,self.time+h)
        self.v,self.w=state[:2]
        self.charge+=state[2];self.source_work+=state[3]
        self.resistor_loss+=state[4];self.voltage_integral+=state[5]

    def metrics(self):
        result=super().metrics()
        result['voltage_within_envelope']=result.pop('ideal_current_within_compliance')
        result.update(headroom_v=self.headroom,rolloff_time_s=self.rolloff_time,
                      minimum_current_fraction=self.minimum_current_fraction)
        return result
