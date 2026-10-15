"""Selected differential REF_IN model and explicit single-ended controls.

Run --check for independent passive-network validation, or without flags for
matched assigned-ENOB RF controls. Add --causal to test SAR/load feedback at
the current package target, including both mismatch and supply-delay signs.
These are conditional circuit requirements, not protocol qualification.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import numpy as np
import baseline_envelope as b
from oscillator_noise import loaded_clock_input_phase
from selected_rf import wideband_receive,reference_supply_transfer,clock_supply_delay_pole,clock_supply_sensitivity,reference_acceptance_parameters
from converter_dynamics import coupled_reference_load_transfer
from design_definition import load_design, Scenario

p=Path(__file__).resolve().parents[1]

def reference_capacitance(environment):
    parameters=environment.get('reference_pad_parameters')
    if parameters is None:
        if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
            raise ValueError('Design-bound reference requires pad parameters')
        return 3e-12
    value=parameters['capacitance_f_per_leg']
    if isinstance(value,bool) or not np.isfinite(value) or value<=0:
        raise ValueError('Positive finite reference capacitance required')
    return value


def reference_passive_parameters(environment):
    parameters=environment.get('reference_package_parameters')
    if parameters is None:
        if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
            raise ValueError('Design-bound reference requires package parameters')
        parameters=dict(bond_l_h=2e-9,source_r_ohm=50.2,mutual_l_h=.4e-9)
    if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
        required={'bond_l_h','source_r_ohm','mutual_l_h'}
        if not isinstance(parameters,dict) or set(parameters)!=required:
            raise ValueError('Design-bound reference requires complete package parameters')
    return dict(cap_f=reference_capacitance(environment),**parameters)


def validate_reference_passives(cap_f,bond_l_h,source_r_ohm,mutual_l_h,mismatch):
    values=(cap_f,bond_l_h,source_r_ohm,mutual_l_h,mismatch)
    if any(isinstance(x,bool) or not isinstance(x,(int,float,np.number)) or not np.isfinite(x) for x in values):
        raise ValueError('Finite reference passive parameters required')
    if cap_f<=0 or bond_l_h<=0 or source_r_ohm<=0 or mutual_l_h<0 or abs(mismatch)>=1:
        raise ValueError('Positive passive reference components required')
    if mutual_l_h>=bond_l_h*np.sqrt(1-mismatch*mismatch):
        raise ValueError('Reference bond matrix must be positive definite after mismatch')


def port(f,candidate,injection,*,source_diff=0.,mismatch=0.,opposed=False,cm_gain=.1,cap_f=3e-12,bond_l_h=2e-9,source_r_ohm=50.2,mutual_l_h=.4e-9,source_skew_s=None):
    validate_reference_passives(cap_f,bond_l_h,source_r_ohm,mutual_l_h,mismatch)
    if source_skew_s is not None and (isinstance(source_skew_s,bool) or not np.isfinite(source_skew_s)):
        raise ValueError('Finite signed reference source leg skew required')
    w=2*np.pi*f;delta=np.array([1.,-1.])*mismatch
    cap=cap_f*(1+delta);inductance=bond_l_h*(1+(-delta if opposed else delta));resistance=source_r_ohm*(1+delta/2)
    mutual=mutual_l_h
    zc=1/(1j*w*cap)
    z=np.diag(resistance+1j*w*inductance+zc)+1j*w*mutual*np.array([[0.,1.],[1.,0.]])
    y=np.linalg.inv(z);one=np.ones(2)
    # One differential source with a 5 ps leg-skew probe when mismatched.
    skew=(5e-12 if mismatch else 0.) if source_skew_s is None else source_skew_s
    sources=source_diff/2*np.array([(1+mismatch/2)*np.exp(.5j*w*skew),-(1-mismatch/2)*np.exp(-.5j*w*skew)])
    drive=np.array(injection,complex,copy=True);load=one@y@one;drive[3]+=one@y@sources
    result=b.partitioned_return_solution(f,candidate,drive,link_r_ohm=1e-5,quiet_load_s=load)
    v=result['voltage'];currents=y@(sources-v[3]*one);local=zc*currents
    effective=local[0]-local[1]+cm_gain*np.mean(local)
    supplied=float(np.real(np.vdot(currents,sources))/2)
    host_power=float(np.real(np.vdot(v,injection))/2)
    network_power=float(np.real(np.vdot(v,drive))/2)-abs(v[3])**2*load.real/2
    input_loss=float(np.sum(resistance*abs(currents)**2)/2)
    return dict(network=v,local=local,effective=effective,return_current=sum(currents),source_power=supplied,
        power_residual=supplied+host_power-network_power-input_loss,kcl=result['kcl_residual_a'])


def full(f,candidate,injection,source_diff,mismatch,opposed,*,cap_f=3e-12,bond_l_h=2e-9,source_r_ohm=50.2,mutual_l_h=.4e-9,source_skew_s=None):
    validate_reference_passives(cap_f,bond_l_h,source_r_ohm,mutual_l_h,mismatch)
    if source_skew_s is not None and (isinstance(source_skew_s,bool) or not np.isfinite(source_skew_s)):
        raise ValueError('Finite signed reference source leg skew required')
    w=2*np.pi*f;n=candidate['network'];m=np.zeros((7,7),complex);source=np.r_[np.asarray(injection,complex),0j,0j]
    def branch(a,b,y):
        m[a,a]+=y
        if b is not None:m[b,b]+=y;m[a,b]-=y;m[b,a]-=y
    def capacitor(c,r,l):return 1j*w*c/(1+1j*w*c*r-w*w*c*l)
    branch(0,None,1/(n['feed_r']+1j*w*n['feed_l']))
    branch(0,1,1/(n['package_r']+1j*w*n['package_l']))
    branch(0,None,capacitor(n['board_c'],n['board_esr'],n['board_esl']))
    z=candidate['return_r_ohm']+1j*w*candidate['return_l_h']
    branch(2,4,.5/(.9*z));branch(3,4,.5/(.9*z));branch(4,None,1/(.1*z))
    branch(2,3,1e5+1j*w*20e-12)
    branch(1,3,capacitor(n['die_c'],n['die_esr'],n['die_esl']))
    d=np.array([1.,-1.])*mismatch;c=cap_f*(1+d);l=bond_l_h*(1+(-d if opposed else d));r=source_r_ohm*(1+d/2)
    zs=np.diag(r+1j*w*l)+1j*w*mutual_l_h*np.array([[0.,1.],[1.,0.]])
    ys=np.linalg.inv(zs);skew=(5e-12 if mismatch else 0.) if source_skew_s is None else source_skew_s
    vs=source_diff/2*np.array([(1+mismatch/2)*np.exp(.5j*w*skew),-(1-mismatch/2)*np.exp(-.5j*w*skew)])
    m[5:,5:]+=ys;source[5:]+=ys@vs
    branch(5,3,1j*w*c[0]);branch(6,3,1j*w*c[1])
    v=np.linalg.solve(m,source)
    return v,ys@(vs-v[5:]),float(max(abs(m@v-source)))


def package_descriptor(candidate, *, mismatch=0., opposed=False,cap_f=3e-12,bond_l_h=2e-9,source_r_ohm=50.2,mutual_l_h=.4e-9):
    """Physical MNA system E*x' + G*x = F*u for the full passive network.

    First seven variables are the nodes of full(); then nine branch currents
    and board/die series-capacitor voltages. Inputs are five node injections
    and two independently driven reference source voltages. Source amplitude,
    skew and common-mode observation belong to callers, not passive dynamics.
    E is singular: this is a DAE, not an ODE obtained by inverting E.
    """
    validate_reference_passives(cap_f,bond_l_h,source_r_ohm,mutual_l_h,mismatch)
    n=candidate['network'];size=18
    E=np.zeros((size,size));G=np.zeros_like(E);F=np.zeros((size,7));F[:5,:5]=np.eye(5)
    def incidence(a,b):
        v=np.zeros(7);v[a]=1.
        if b is not None:v[b]-=1.
        return v
    def shunt(a,b,*,conductance=0.,capacitance=0.):
        vv=np.outer(incidence(a,b),incidence(a,b))
        G[:7,:7]+=conductance*vv;E[:7,:7]+=capacitance*vv
    def branch(k,a,b,r,l,cap=None,cap_index=None,source_index=None):
        i=7+k;v=incidence(a,b)
        G[:7,i]+=v;G[i,:7]-=v;G[i,i]=r;E[i,i]=l
        if cap is not None:
            E[cap_index,cap_index]=cap;G[i,cap_index]=1.;G[cap_index,i]=-1.
        if source_index is not None:F[i,source_index]=-1.
    branch(0,0,None,n['feed_r'],n['feed_l'])
    branch(1,0,1,n['package_r'],n['package_l'])
    branch(2,0,None,n['board_esr'],n['board_esl'],n['board_c'],16)
    rr,ll=candidate['return_r_ohm'],candidate['return_l_h']
    branch(3,2,4,1.8*rr,1.8*ll);branch(4,3,4,1.8*rr,1.8*ll)
    branch(5,4,None,.1*rr,.1*ll)
    branch(6,1,3,n['die_esr'],n['die_esl'],n['die_c'],17)
    shunt(2,3,conductance=1e5,capacitance=20e-12)
    d=np.array([1.,-1.])*mismatch
    caps=cap_f*(1+d);ind=bond_l_h*(1+(-d if opposed else d));res=source_r_ohm*(1+d/2)
    if np.any(caps<=0) or np.any(res<=0) or np.min(np.linalg.eigvalsh([[ind[0],mutual_l_h],[mutual_l_h,ind[1]]]))<=0:
        raise ValueError('Passive positive reference components required')
    for leg in range(2):
        branch(7+leg,5+leg,None,res[leg],ind[leg],source_index=5+leg)
        shunt(5+leg,3,capacitance=caps[leg])
    E[14,15]=E[15,14]=mutual_l_h
    return E,G,F


class PackageTransient:
    """Trapezoidal DAE stepping; caller supplies a consistent initial state.

    Input interpolation is linear between endpoints. Voltage/current sources
    must have finite slew; ideal jumps can demand impulses in this network.
    Capacitor/inductor state is retained across every input update.
    """
    def __init__(self, matrices, state, inputs, *, time=0.):
        self.E,self.G,self.F=matrices
        self.state=np.asarray(state,float).copy();self.inputs=np.asarray(inputs,float).copy()
        if self.state.shape!=(len(self.E),) or self.inputs.shape!=(self.F.shape[1],):
            raise ValueError('Descriptor state/input dimensions do not match')
        if not np.all(np.isfinite(self.state)) or not np.all(np.isfinite(self.inputs)) or not np.isfinite(time) or time<0:
            raise ValueError('Finite initial state, inputs and time required')
        self.time=float(time);self._cache={}

    def advance(self,time,inputs):
        from scipy.linalg import lu_factor,lu_solve
        inputs=np.asarray(inputs,float);dt=time-self.time
        if not np.isfinite(time) or dt<=0 or inputs.shape!=self.inputs.shape or not np.all(np.isfinite(inputs)):
            raise ValueError('Positive timestep and finite matching inputs required')
        if dt not in self._cache:
            self._cache[dt]=(lu_factor(self.E/dt+self.G/2),self.E/dt-self.G/2)
            if len(self._cache)>128:self._cache={dt:self._cache[dt]}
        lu,right=self._cache[dt]
        self.state=lu_solve(lu,right@self.state+self.F@((inputs+self.inputs)/2))
        self.inputs=inputs.copy();self.time=float(time)
        return self.state.copy()


def ramped_tones(tones,*,start_s,duration_s,rising,interval_time_s):
    """Exact sidebands of real tones times a clamped half-cosine gate.

    The caller splits time at gate endpoints; this representation is valid
    only on the interval containing interval_time_s. Negative sidebands fold
    to positive frequency by conjugation; DC is represented once as real.
    """
    if not all(np.isfinite(v) for v in (start_s,duration_s,interval_time_s)) or duration_s<=0 or type(rising) is not bool:
        raise ValueError('Finite gate times, positive duration and boolean direction required')
    if interval_time_s<=start_s:scale=0. if rising else 1.
    elif interval_time_s>=start_s+duration_s:scale=1. if rising else 0.
    else:scale=None
    if scale is not None:return {f:scale*np.asarray(v,complex) for f,v in tones.items()} if scale else {}
    shift=1/(2*duration_s);amplitude=-.5 if rising else .5;result={}
    def add(f,value):
        if f<0:f=-f;value=np.conj(value)
        if f==0:value=np.real(value)
        result[f]=result.get(f,0.)+value
    for frequency,value in tones.items():
        value=np.asarray(value,complex)
        if frequency==0:value=value.real
        add(frequency,.5*value)
        add(frequency+shift,amplitude/2*value*np.exp(-2j*np.pi*shift*start_s))
        add(frequency-shift,amplitude/2*value*np.exp(2j*np.pi*shift*start_s))
    return result


def linear_source_filter(values,*,step_s,pole_hz,initial_output):
    """One-pole response to linearly interpolated values, retaining y(0)."""
    from scipy.signal import lfilter
    values=np.asarray(values,float)
    if values.ndim!=1 or not len(values) or not np.all(np.isfinite(values)):
        raise ValueError('Finite nonempty scalar source samples required')
    if not np.isfinite(step_s) or not np.isfinite(pole_hz) or min(step_s,pole_hz)<=0 or not np.isfinite(initial_output):
        raise ValueError('Positive finite step/pole and finite initial filter state required')
    z=2*np.pi*pole_hz*step_s;alpha=np.exp(-z);q=-np.expm1(-z)
    b1=1-q/z;b0=q-b1
    return lfilter([b1,b0],[1,-alpha],values,zi=[initial_output-b1*values[0]])[0]


class PeriodicPackageContinuation:
    """Analytic continuation of this fixed passive network under known tones.

    Retains finite natural modes; rejects incompatible stored charge/flux
    instead of resetting to steady state. Algebraic nodes are reconstructed
    for the analytic source derivatives. No source switch or nonlinear load
    can occur inside the requested interval. Tones use absolute time/phase.
    """
    def __init__(self,matrices,state,tones,*,time=0.,consistency_tolerance=1e-7):
        from scipy.linalg import eig
        self.E,self.G,self.F=matrices;self.time=float(time)
        if not np.isfinite(consistency_tolerance) or consistency_tolerance<=0:
            raise ValueError('Positive finite stored-state tolerance required')
        if not np.isfinite(time) or time<0:raise ValueError('Finite nonnegative origin required')
        poles,vectors=eig(-self.G,self.E/1e-9,homogeneous_eigvals=True)
        # This network has ten finite modes. Algebraic modes can appear as
        # huge finite roots numerically; the nearest physical pole is 5e15/s,
        # separated from the spurious algebraic roots by >four decades.
        finite=abs(poles[1])>1e-10*np.maximum(abs(poles[0]),abs(poles[1]))
        self.poles=poles[0,finite]/poles[1,finite]/1e-9
        self.vectors=vectors[:,finite]
        if len(self.poles)!=10 or np.any(self.poles.real>=0):
            raise ValueError('Unresolved finite/algebraic mode separation for package')
        self.tones=[]
        for frequency,drive in tones.items():
            drive=np.asarray(drive,complex)
            if not np.isfinite(frequency) or frequency<0 or drive.shape!=(self.F.shape[1],) or not np.all(np.isfinite(drive)):
                raise ValueError('Finite nonnegative tones with matching inputs required')
            self.tones.append((frequency,np.linalg.solve(2j*np.pi*frequency*self.E+self.G,self.F@drive)))
        state=np.asarray(state,float)
        if state.shape!=(len(self.E),) or not np.all(np.isfinite(state)):
            raise ValueError('Finite descriptor state required')
        residual=state-self.particular(np.array([time]))[0]
        # E*x is the stored-charge/flux state. Algebraic voltages may change
        # when the preceding piecewise-linear source changes to exact tones;
        # those adjustments must not reset any capacitor voltage or current.
        scale=np.max(abs(self.E),axis=1)
        physical=self.E/np.where(scale>0,scale,1.)[:,None]
        self.weights=np.linalg.lstsq(physical@self.vectors,physical@residual,rcond=None)[0]
        adjustment=self.vectors@self.weights-residual
        self.initial_residual=float(np.max(abs(physical@adjustment)))
        self.algebraic_node_adjustment_v=float(np.max(abs(adjustment[:7])))
        if self.initial_residual>consistency_tolerance:
            raise ValueError('Initial state violates continued-source constraints')

    def observer(self,weights,*,pole_hz=None,initial_output=None):
        """Scalar linear observation, optionally through a retained one-pole filter."""
        weights=np.asarray(weights,float)
        if weights.shape!=(len(self.E),) or not np.all(np.isfinite(weights)):
            raise ValueError('Finite matching observation weights required')
        rates=np.r_[[2j*np.pi*f for f,state in self.tones],self.poles]
        coefficients=np.r_[[weights@state*np.exp(2j*np.pi*f*self.time) for f,state in self.tones],
                           (weights@self.vectors)*self.weights]
        if pole_hz is not None:
            if not np.isfinite(pole_hz) or pole_hz<=0 or initial_output is None or not np.isfinite(initial_output):
                raise ValueError('Positive filter pole and finite retained output required')
            pole=2*np.pi*pole_hz
            if np.any(abs(rates+pole)<1e-8*pole):raise ValueError('Coincident filter/natural pole requires confluent solution')
            coefficients=coefficients*pole/(rates+pole)
            coefficients=np.r_[coefficients,initial_output-np.sum(coefficients).real]
            rates=np.r_[rates,-pole]
        def observe(times):
            times=np.asarray(times,float)
            if not np.all(np.isfinite(times)) or np.any(times<self.time):
                raise ValueError('Observation precedes continuation')
            flat=times.ravel();result=np.zeros(len(flat))
            # Bounded-memory batches for long converter acquisition schedules.
            for start in range(0,len(flat),2048):
                dt=flat[start:start+2048]-self.time
                result[start:start+2048]=np.real(np.exp(dt[:,None]*rates)@coefficients)
            return result.reshape(times.shape)
        return observe

    def particular(self,times):
        result=np.zeros((len(times),len(self.E)))
        for frequency,state in self.tones:
            result+=np.real(np.exp(2j*np.pi*frequency*times)[:,None]*state)
        return result

    def evaluate(self,times):
        times=np.atleast_1d(np.asarray(times,float))
        if times.ndim!=1 or not np.all(np.isfinite(times)) or np.any(times<self.time):
            raise ValueError('Finite observation times after continuation origin required')
        natural=(np.exp((times-self.time)[:,None]*self.poles)*self.weights)@self.vectors.T
        if np.max(abs(natural.imag),initial=0.)>1e-7:raise ValueError('Unresolved conjugate modal cancellation')
        return self.particular(times)+natural.real


def package_check_environment(design, mode, return_l, die_esl):
    settings=(dict(engine='rf',direction='rx',reference_hz=2.426e9,sample_divider=64,
                   pga_gain_db=max(design.architecture['blocks']['pga_i']['parameters']['gain_db']))
              if mode=='rf' else dict(engine='wire',direction='tx',reference_hz=2.5e9,host_divider=8))
    config=design.configure(**settings)
    scenario=Scenario().override(reason='Passive numerical-validation package comparison',
        package_return_inductance_h=return_l,die_decoupling_esl_h=die_esl)
    return b.configured_environment(config,scenario),dict(
        design_provenance=design.provenance(),resolved_configuration=config.record(),
        scenario_overrides=scenario.record(),
        reference_capacitance_f_per_leg=design.architecture['blocks']['refpad']['parameters']['capacitance_f_per_leg'],
        reference_package_parameters=design.architecture['model_assumptions']['reference_input_package']['parameters'],
        scope='Shared package parameters with independent forcing, input fixtures and numerical identities; not a full-chip operating case')


def check_package_continuation(*,design=None):
    design=load_design() if design is None else design
    # Independent real-waveform identity covers DC, negative sidebands and
    # a carrier equal to the gate sideband frequency at a long time offset.
    start=21.98537727747e-6;duration=20e-9
    tones={0:np.array([.2]),10e6:np.array([.3+.1j]),25e6:np.array([.4-.2j]),2.484e9:np.array([1+.3j])}
    def waveform(components,times):
        return sum(np.real(np.exp(2j*np.pi*f*times)[:,None]*v) for f,v in components.items())
    ramp_error=0.
    for rising in (False,True):
        for offset in (-duration,duration/2,2*duration):
            times=start+offset+np.linspace(-duration/4,duration/4,101)
            gate=(1-np.cos(np.pi*np.clip((times-start)/duration,0,1)))/2
            if not rising:gate=1-gate
            expanded=ramped_tones(tones,start_s=start,duration_s=duration,rising=rising,interval_time_s=start+offset)
            actual=waveform(expanded,times) if expanded else np.zeros((len(times),1))
            ramp_error=max(ramp_error,float(np.max(abs(actual-waveform(tones,times)*gate[:,None]))))
    assert ramp_error<1e-9
    rows=[]
    for label,ret,esl in b.network_cases(design):
        env,context=package_check_environment(design,'rf',ret,esl)
        matrices=package_descriptor(env['network'],mismatch=.2,**reference_passive_parameters(env));E,G,F=matrices
        tones={1e6:np.array([.002,-.003,.001,.002,0.,0.,0.],complex),
               2.426e9:np.array([0.,0.,0.,0.,0.,.5,-.4],complex)*np.exp(.31j)}
        steady=sum(np.linalg.solve(2j*np.pi*f*E+G,F@u).real for f,u in tones.items())
        base=PeriodicPackageContinuation(matrices,steady,tones)
        slow=int(np.argmax(base.poles.real));perturbation=.02*base.vectors[:,slow].real
        perturbation/=max(abs(base.vectors[:7,slow].real))
        initial=steady+perturbation
        model=PeriodicPackageContinuation(matrices,initial,tones)
        errors=[]
        def forcing(t):return sum((u*np.exp(2j*np.pi*f*t)).real for f,u in tones.items())
        for dt in (12.5e-12,6.25e-12):
            times=np.arange(round(4e-9/dt)+1)*dt
            explicit=PackageTransient(matrices,initial,forcing(0.));observed=[initial]
            for t in times[1:]:observed.append(explicit.advance(float(t),forcing(t)))
            errors.append(float(np.max(abs(np.asarray(observed)[:,:7]-model.evaluate(times)[:,:7]))))
        assert errors[1]<.4*errors[0]
        checkpoint=13.7e-9
        continued=PeriodicPackageContinuation(matrices,model.evaluate([checkpoint])[0],tones,time=checkpoint)
        times=np.array([checkpoint,1e-6,20e-6,21e-6])
        split_error=float(np.max(abs(continued.evaluate(times)-model.evaluate(times))))
        assert split_error<1e-7
        weights=np.zeros(18);weights[1]=1.;weights[3]=-1.
        observer=model.observer(weights)
        np.testing.assert_allclose(observer(times),model.evaluate(times)@weights,rtol=1e-10,atol=1e-10)
        from scipy.integrate import quad
        pole=2*np.pi*10e6;initial_output=.03;end=4e-9
        filtered=model.observer(weights,pole_hz=10e6,initial_output=initial_output)
        integral=quad(lambda q:np.exp(-pole*(end-q))*pole*float(model.evaluate([q])[0]@weights),0.,end,epsabs=1e-10)[0]
        expected=initial_output*np.exp(-pole*end)+integral
        filter_error=abs(float(filtered(end))-expected)
        assert abs(float(filtered(0.))-initial_output)<1e-10 and filter_error<1e-8
        linear_filter_errors=[]
        for step in (12.5e-12,6.25e-12):
            grid=np.arange(round(end/step)+1)*step
            observed=linear_source_filter(observer(grid),step_s=step,pole_hz=10e6,initial_output=initial_output)
            assert observed[0]==initial_output
            linear_filter_errors.append(float(np.max(abs(observed-filtered(grid)))))
        assert linear_filter_errors[1]<.4*linear_filter_errors[0]+1e-12
        # An incompatible stored branch current must never silently disappear.
        inconsistent=initial.copy();inconsistent[7]+=.1
        try:PeriodicPackageContinuation(matrices,inconsistent,tones)
        except ValueError:pass
        else:raise AssertionError('Inconsistent continuation state accepted')
        rows.append(dict(context,network_case=label,finite_modes=len(model.poles),
            initial_state_residual=model.initial_residual,linear_filter_grid_error_v=linear_filter_errors,filtered_observer_quadrature_error_v=filter_error,coarse_fine_node_error_v=errors,
            split_continuation_state_error=split_error,last_observation_s=float(times[-1])))
    return dict(ramp_sideband_identity_error=ramp_error,cases=rows,scope='Fixed-source passive-network continuation with retained natural-mode energy, compared with two trapezoidal grids and split propagation through 21 us. Exact periodic forcing plus numerical finite-mode decomposition. Not a cold-start, source-transition, nonlinear converter feedback or physical package validation.')


def check_package_transient(*,design=None):
    design=load_design() if design is None else design
    rows=[]
    for label,ret,esl in b.network_cases(design):
        env,context=package_check_environment(design,'rf',ret,esl)
        matrices=package_descriptor(env['network'],mismatch=.2,**reference_passive_parameters(env))
        E,G,F=matrices
        for frequency in (1e6,2.426e9):
            omega=2*np.pi*frequency
            inputs=np.array([.002,-.003,.001,.002,0.,.5,-.4],complex)*np.exp(.31j)
            state=np.linalg.solve(1j*omega*E+G,F@inputs)
            errors=[]
            for samples in (128,256):
                model=PackageTransient(matrices,state.real,inputs.real)
                maximum=0.
                for index in range(1,4*samples+1):
                    time=index/(frequency*samples);phase=np.exp(1j*omega*time)
                    observed=model.advance(time,(inputs*phase).real)
                    maximum=max(maximum,float(max(abs(observed[:7]-(state*phase).real[:7]))))
                errors.append(maximum)
            if not errors[1]<.4*errors[0]+1e-9:raise AssertionError('Descriptor time refinement failed')
            rows.append(dict(context,network_case=label,frequency_hz=frequency,node_error_v=errors))
    return dict(cases=rows,scope='Four cycles from exact steady sinusoidal state; 128/256 steps per cycle. Checks numerical time propagation against independent algebraic frequency solutions, not mode switching or physical validity.')


def check_network(*,design=None):
    design=load_design() if design is None else design
    descriptor_error=0.;descriptor_points=0;contexts=[]
    rng=np.random.default_rng(813);maximum=0.;residual=0.;power=0.;count=0;load_error=0.;load_count=0
    for label,ret,esl in b.network_cases(design):
        e,context=package_check_environment(design,'wire',ret,esl)
        passive=reference_passive_parameters(e)
        contexts.append(dict(context,network_case=label))
        for mismatch,opposed in ((0.,False),(.1,True),(.2,False)):
            E,G,F=package_descriptor(e['network'],mismatch=mismatch,opposed=opposed,**passive)
            for f in np.geomspace(1e3,1e10,51):
                injection=.001*(rng.normal(size=5)+1j*rng.normal(size=5));drive=.7*np.exp(.2j)
                reduced=port(f,e['network'],injection,source_diff=drive,mismatch=mismatch,opposed=opposed,cm_gain=.1,**passive)
                nodes,currents,kcl=full(f,e['network'],injection,drive,mismatch,opposed,**passive)
                skew=5e-12 if mismatch else 0.;w=2*np.pi*f
                vs=drive/2*np.array([(1+mismatch/2)*np.exp(.5j*w*skew),-(1-mismatch/2)*np.exp(-.5j*w*skew)])
                state=np.linalg.solve(1j*w*E+G,F@np.r_[injection,vs])
                np.testing.assert_allclose(state[:7],nodes,rtol=1e-7,atol=1e-9)
                np.testing.assert_allclose(-state[14:16],currents,rtol=1e-7,atol=1e-9)
                descriptor_error=max(descriptor_error,float(max(abs(state[:7]-nodes))));descriptor_points+=1
                np.testing.assert_allclose(reduced['network'],nodes[:5],rtol=1e-7,atol=1e-10)
                np.testing.assert_allclose(reduced['local'],nodes[5:]-nodes[3],rtol=1e-7,atol=1e-10)
                np.testing.assert_allclose(reduced['return_current'],sum(currents),rtol=1e-7,atol=1e-10)
                maximum=max(maximum,float(max(abs(reduced['local']-(nodes[5:]-nodes[3])))))
                residual=max(residual,kcl);power=max(power,abs(reduced['power_residual']));count+=1
            frequencies=np.r_[0.,np.geomspace(1e3,1e10,51)]
            for cm_gain in (-.1,0.,.1):
                coupled=coupled_reference_load_transfer(frequencies,e['network'],
                    **{k:v for k,v in passive.items() if k!='mutual_l_h'},
                    differential=dict(mismatch=mismatch,opposed=opposed,cm_gain=cm_gain,mutual_l_h=passive['mutual_l_h']))
                for i,f in enumerate(frequencies):
                    nodes,_,_=full(f,e['network'],[0,-1,0,1,0],0.,mismatch,opposed,**passive)
                    legs=nodes[5:]-nodes[3]
                    expected=dict(rail_v_per_a=nodes[1]-nodes[3],return_v_per_a=nodes[3],
                        input_v_per_a=legs[0]-legs[1]+cm_gain*np.mean(legs),input_leg_v_per_a=legs)
                    for key,value in expected.items():
                        np.testing.assert_allclose(coupled[key][i],value,rtol=1e-7,atol=1e-9)
                        load_error=max(load_error,float(np.max(abs(coupled[key][i]-value))))
                    load_count+=1
    return dict(design_provenance=design.provenance(),
        result_role='independent_passive_solver_comparison_on_shared_package',
        diagnostic_assumptions=dict(random_seed=813,source_peak_v=.7,source_phase_rad=.2,
            matched_source_leg_skew_s=0.,mismatched_source_leg_skew_s=5e-12,
            mismatch_opposed_cases=[[0.,False],[.1,True],[.2,False]],
            source_scope='Independent numerical stimuli; shared source amplitude/skew are not exercised here'),
        package_cases=contexts,descriptor_compared_points=descriptor_points,descriptor_maximum_node_difference_v=descriptor_error,compared_points=count,maximum_input_voltage_difference_v=maximum,maximum_kcl_residual_a=residual,maximum_power_residual_w=power,
        load_transfer_points=load_count,maximum_load_transfer_difference_ohm=load_error)

def reference_source_skew(environment,mismatch):
    config=environment.get('clock_input_configuration')
    if config is not None:
        value=config['source_leg_skew_s']
    elif any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
        raise ValueError('Shared reference requires source leg skew')
    else:
        value=5e-12 if mismatch else 0.
    if isinstance(value,bool) or not isinstance(value,(int,float,np.number)) or not np.isfinite(value):
        raise ValueError('Finite signed reference source leg skew required')
    return float(value)


def environment_port(frequency,environment,injection,*,source_diff=0.,**input_options):
    """Resolve shared signal loading and source skew before the passive solver."""
    return port(frequency,environment['network'],injection,source_diff=source_diff,
        source_skew_s=reference_source_skew(environment,input_options.get('mismatch',0.)),
        **reference_passive_parameters(environment),**input_options)


def reference_result_context(environment):
    """Snapshot identity and conditions, without binding independent fixtures."""
    return {key:deepcopy(environment[key]) for key in (
        'design_provenance','resolved_configuration','scenario_overrides',
        'scenario_assumptions','operating_conditions') if key in environment}


def differential_source_peak(environment, requested=None):
    """Resolve shared source amplitude; explicit values are stimulus overrides."""
    config=environment.get('clock_input_configuration')
    bound=any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration'))
    if bound and (not isinstance(config,dict) or 'source_differential_peak_v' not in config):
        raise ValueError('Shared differential input requires source amplitude configuration')
    value=requested
    if value is None:
        value=config['source_differential_peak_v'] if config is not None else 1.
    if (isinstance(value,bool) or not isinstance(value,(int,float,np.number))
            or not np.isfinite(value) or value<=0):
        raise ValueError('Positive finite differential source peak required')
    return float(value)


def paired_input_envelope(original,opts,*,source_peak_v=None,samples_per_period=64):
    """Fixed-phase per-leg excursion, separate from arbitrary-phase bounds."""
    source_peak_v=differential_source_peak(original,source_peak_v)
    acceptance=reference_acceptance_parameters(original)
    wanted=environment_port(original['carrier_hz'],original,np.zeros(5),source_diff=source_peak_v,**opts)
    tones=[[(original['carrier_hz'],value)] for value in wanted['local']]
    for frequency,injection in b.partitioned_host_sources(original).items():
        response=environment_port(frequency,original,injection,**opts)
        for leg in range(2):tones[leg].append((frequency,response['local'][leg]))
    result=[]
    for leg in tones:
        trace=b.rail_excursion([dict(frequency_hz=f,clock_rail_voltage_peak_v=float(abs(v)),
            voltage_phase_rad=float(np.angle(v))) for f,v in leg],dc_v=0.,samples_per_fastest_period=samples_per_period)
        observed=max(abs(v) for v in trace['sampled_interval_v'])
        enclosed=max(abs(v) for v in trace['enclosed_interval_v'])
        result.append(dict(sampled_interval_v=trace['sampled_interval_v'],
            enclosed_interval_v=trace['enclosed_interval_v'],samples=trace['samples'],period_s=trace['period_s'],
            assigned_leg_peak_limit_v=acceptance['leg_peak_limit_v'],
            observed_outside_assigned_envelope=observed>acceptance['leg_peak_limit_v'],
            proven_inside_assigned_envelope=enclosed<=acceptance['leg_peak_limit_v']))
    modal={}
    for name,weights in (('common_mode',(.5,.5)),('differential',(1.,-1.))):
        combined=[]
        for (f,a),(other,bv) in zip(*tones):
            assert f==other
            value=weights[0]*a+weights[1]*bv
            combined.append(dict(frequency_hz=f,clock_rail_voltage_peak_v=float(abs(value)),
                                 voltage_phase_rad=float(np.angle(value))))
        for label,values in (('total',combined),('switching_only',combined[1:])):
            trace=b.rail_excursion(values,dc_v=0.,samples_per_fastest_period=samples_per_period)
            modal[name+'_'+label]=dict(sampled_interval_v=trace['sampled_interval_v'],
                enclosed_interval_v=trace['enclosed_interval_v'])
    return dict(**reference_result_context(original),source_differential_peak_v=source_peak_v,source_leg_skew_s=reference_source_skew(original,opts.get('mismatch',0.)),legs=result,modal=modal,scope='Fixed assigned source phases and finite tones. Modal voltages are local to die return; switching_only excludes the externally driven carrier. No common-mode or differential acceptance mask is inferred from the per-leg guard. Sampled exceedance proves excursion in this waveform, not physical device overstress. Enclosure is a sufficient in-model guard only; input bias, unmodeled currents and noise remain unqualified.')


def paired_environment(original,opts,*,sign=1.,sensitivity_ps_per_mv=None,ledger=None,source_peak_v=None):
    """Reusable paired input for either engine; DC bias is included once in the selected mode ledger."""
    source_peak_v=differential_source_peak(original,source_peak_v)
    acceptance=reference_acceptance_parameters(original)
    edge_options=dict(threshold_v=acceptance['threshold_v'],peak_limit_v=acceptance['effective_peak_limit_v'])
    bound=any(key in original for key in ('design_provenance','inventory_current_report','resolved_configuration'))
    noise_parameters=original.get('clock_input_noise_parameters')
    if noise_parameters is None:
        if bound:
            raise ValueError('Inventory environment missing per-leg clock noise parameters')
        noise_parameters=dict(receiver_noise_v=75e-6,downstream_stage_rms_s=15e-15)
    required={'receiver_noise_v','downstream_stage_rms_s'}
    if not isinstance(noise_parameters,dict) or set(noise_parameters)!=required:
        raise ValueError('Complete per-leg clock noise parameters required')
    if any(isinstance(value,bool) or not isinstance(value,(int,float,np.number))
           or not np.isfinite(value) or value<0 for value in noise_parameters.values()):
        raise ValueError('Finite nonnegative per-leg clock noise parameters required')
    if not np.isfinite(source_peak_v) or source_peak_v<=0:raise ValueError('Positive finite differential source peak required')
    if sensitivity_ps_per_mv is None:
        sensitivity_ps_per_mv=(clock_supply_sensitivity(original) if 'clock_input_configuration' in original or any(key in original for key in ('design_provenance','inventory_current_report','resolved_configuration')) else .025)
    carrier=original['carrier_hz'];gain=b.supply_delay_gain(sensitivity_ps_per_mv,sign)
    if ledger is None:
        _,base=b.single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False)
        ledger=base['ledger']
    wanted=environment_port(carrier,original,np.zeros(5),source_diff=source_peak_v,**opts)
    tones=[];rails=[];delays=[];bound=abs(wanted['local']).copy()
    for frequency,injection in b.partitioned_host_sources(original).items():
        r=environment_port(frequency,original,injection,**opts)
        tones.append((frequency,r['effective']));bound+=abs(r['local'])
        v=r['network'][1]-r['network'][3]
        rails.append(dict(frequency_hz=frequency,clock_rail_voltage_peak_v=float(abs(v)),voltage_phase_rad=float(np.angle(v))))
        delays.append((frequency,v*gain/(1+1j*frequency/clock_supply_delay_pole(original))))
    v=wanted['network'][1]-wanted['network'][3]
    rails.append(dict(frequency_hz=carrier,clock_rail_voltage_peak_v=float(abs(v)),voltage_phase_rad=float(np.angle(v))))
    delays.append((carrier,v*gain/(1+1j*carrier/clock_supply_delay_pole(original))))
    capture={}
    resolved=b.reference_edge_screen(carrier,wanted['effective'],tones,**edge_options,downstream_delay_tones=delays,substeps=64,capture=capture)
    coarse=b.reference_edge_screen(carrier,wanted['effective'],tones,**edge_options,downstream_delay_tones=delays,substeps=32)
    stable=all(resolved[k]==coarse[k] for k in ('missing_rising_edge_windows','multiple_rising_edge_windows'))
    checks=dict(complete_ordered_edge_capture=bool(capture['complete']),
        crossing_count_grid_agreement=bool(stable),
        effective_input_envelope=bool(resolved['incremental_envelope_met']),
        individual_leg_envelope=bool(max(bound)<=acceptance['leg_peak_limit_v']))
    accepted=all(checks.values())
    row=dict(**reference_result_context(original),carrier_hz=carrier,source_differential_peak_v=source_peak_v,source_leg_skew_s=reference_source_skew(original,opts.get('mismatch',0.)),**opts,reference_acceptance_parameters=dict(acceptance),supply_sign=sign,sensitivity_ps_per_mv=sensitivity_ps_per_mv,
        supply_delay_pole_hz=clock_supply_delay_pole(original),
        capacitance_f_per_leg=reference_capacitance(original),
        reference_package_parameters=reference_passive_parameters(original),
        accepted=accepted,acceptance_checks=checks,
        rejected_checks=[name for name,passed in checks.items() if not passed],
        envelope_scope='Assigned shared incremental input envelopes. Conservative peak bounds exceeding it do not prove actual overvoltage, physical damage or loss of clock edges.',
        per_leg_bound_v=bound.tolist(),current_a=ledger['total_chip_supply_current_a'],clock=resolved)
    if not accepted:return None,row
    equivalent=original['external_clock_input']['source_peak_v']*abs(wanted['effective'])/original['external_clock_input']['receiver_peak_v']
    noise,input_report=loaded_clock_input_phase(carrier,
        receiver_noise_v=np.sqrt(2)*noise_parameters['receiver_noise_v'],
        downstream_stage_rms_s=noise_parameters['downstream_stage_rms_s'],source_peak_v=equivalent,**edge_options)
    reference=[]
    for t in rails:
        h=reference_supply_transfer(original,t['frequency_hz'])
        reference.append((t['frequency_hz'],t['clock_rail_voltage_peak_v']*abs(h),t['voltage_phase_rad']+np.angle(h)))
    e=dict(original,ledger=ledger,host_spectrum=dict(original['host_spectrum'],tones=rails),reference_fraction_tones=reference,
        rail_maximum_offset_hz=max(t['frequency_hz'] for t in rails),crossing_delay_tones=[],
        periodic_clock=dict(carrier_hz=carrier,period_s=capture['period_s'],edges_s=capture['output_edges_s']),
        delivered_phase_tones=tuple(original['phase_components']['source'])+tuple(noise.tones),
        reference_return_options=dict(link_r_ohm=1e-5),local_supply_delay_sign=sign,local_supply_sensitivity_ps_per_mv=sensitivity_ps_per_mv,
        reference_load_parameters=dict(differential=opts,
            **{key:value for key,value in reference_passive_parameters(original).items() if key!='mutual_l_h'}),
        external_clock_input=dict(input_report,topology='differential',physical_source_peak_v=source_peak_v,
            source_peak_interpretation='source_peak_v is gain-equivalent; physical_source_peak_v is differential Thevenin peak'),
        phase_components=dict(source=original['phase_components']['source'],input=noise.tones,supply=()),
        reference_threshold=dict(carrier_v=wanted['effective'],input_tones=tones,
            downstream_delay_tones=delays,threshold_v=acceptance['threshold_v'],input_edges_s=capture['input_edges_s'],period_s=capture['period_s']))
    return e,row


def gain_requirement_environment(design, carrier, return_l, die_esl):
    """Historical 54 dB requirement experiment, never a baseline setting."""
    gain=54.
    changes={}
    for block in ('pga_i','pga_q'):
        values=design.architecture['blocks'][block]['parameters']['gain_db']
        if gain not in values:changes[f'blocks.{block}.parameters.gain_db']=sorted(values+[gain])
    variant=(design.hypothetical(reason='54 dB gain-requirement experiment; no added power/noise/linearity cost modeled',
                                changes=changes) if changes else design)
    config=variant.configure(engine='rf',direction='rx',reference_hz=carrier,
                             sample_divider=64,pga_gain_db=gain)
    scenario=Scenario(wanted_dbm=-85.,blocker_dbm=-30.).override(
        reason='Explicit package comparison for gain-requirement experiment',
        package_return_inductance_h=return_l,die_decoupling_esl_h=die_esl)
    environment=b.configured_environment(config,scenario)
    context=dict(design_provenance=variant.provenance(),resolved_configuration=config.record(),
        scenario_overrides=scenario.record(),scenario_stimuli=scenario.stimulus_record(),
        probe_assumptions=dict(gain_scope='Hypothetical 54 dB; unchanged current/noise/linearity assumptions, not implemented hardware',
            input_model='Passive clock-input comparison fixture; single-ended topology is a diagnostic substitution',
            internal_switching='No assigned core/timing pulse spectrum'))
    return environment,context


def paired_rf(causal=False,*,design=None):
    design=load_design() if design is None else design
    rows=[]
    for label,return_l,die_esl in b.network_cases(design)[:2]:
        for carrier in (2.4e9,2.484e9):
            original,context=gain_requirement_environment(design,carrier,return_l,die_esl)
            for mismatch,opposed,cm_gain in ((.1,True,.1),(.2,False,-.1)):
                for sign in (1.,-1.):
                    e,row=paired_environment(original,dict(mismatch=mismatch,opposed=opposed,cm_gain=cm_gain),sign=sign)
                    row.update(context)
                    row['network_case']=label
                    if e is not None:
                        row['rf']=wideband_receive(e,oversample=max(256,b.minimum_envelope_oversample(e)),wanted_dbm=-85.,gain_settings_db=(54.,),gain_hypothesis_reason='Requirement-search control above the selected PGA range')
                        if causal and label==b.BASELINE_PACKAGE_CASE:
                            row['causal']=b.coupled_wideband_feedback(e,wanted_dbm=-85.,gain_db=54.,gain_hypothesis_reason='Requirement-search control above the selected PGA range')
                            loads=[step['load'] for step in row['causal']['iterations']]
                            row['causal_input_leg_bounds_v']=(np.array(row['per_leg_bound_v'])+np.max([x['input_leg_voltage_abs_peak_v'] for x in loads],axis=0)).tolist()
                            row['causal_input_leg_envelope_met']=max(row['causal_input_leg_bounds_v'])<=reference_acceptance_parameters(e)['leg_peak_limit_v']
                    rows.append(row)
                    print(label,carrier,mismatch,sign,row['accepted'],[g['observation']['bpsk_errors'] for g in row.get('rf',{}).get('gain_cases',[])],flush=True)
    return rows

def single_rf(causal=False,*,design=None):
    design=load_design() if design is None else design
    rows=[]
    for label,return_l,die_esl in b.network_cases(design)[:2]:
     for carrier in (2.4e9,2.484e9):
      original,context=gain_requirement_environment(design,carrier,return_l,die_esl)
      for peak in (.5,.75,1.):
       for sign in (1.,-1.):
        e,report=b.single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False,source_peak_v=peak,supply_sign=sign)
        row=dict(context,network_case=label,carrier_hz=carrier,source_peak_v=peak,supply_sign=sign,clock=report)
        if e is not None:
         row['rf']=wideband_receive(e,oversample=max(256,b.minimum_envelope_oversample(e)),wanted_dbm=-85.,gain_settings_db=(54.,),gain_hypothesis_reason='Requirement-search control above the selected PGA range')
         if causal and label==b.BASELINE_PACKAGE_CASE and peak==1.:
          row['causal']=b.coupled_wideband_feedback(e,wanted_dbm=-85.,gain_db=54.,gain_hypothesis_reason='Requirement-search control above the selected PGA range')

        rows.append(row)
        print(label,carrier,peak,sign,[x['observation']['bpsk_errors'] for x in row.get('rf',{}).get('gain_cases',[])],flush=True)
    return rows


def configured_probe_environment(design, mode, carrier, *, transmit=False):
    """Resolve intended-chip ownership before applying explicit clock probes."""
    settings=dict(engine=mode,direction='tx' if transmit or mode=='wire' else 'rx',reference_hz=carrier)
    if mode=='rf':
        settings['sample_divider']=64
        if not transmit:settings['pga_gain_db']=max(design.architecture['blocks']['pga_i']['parameters']['gain_db'])
    else:settings['host_divider']=8
    config=design.configure(**settings)
    scenario=Scenario()
    environment=b.configured_environment(config,scenario)
    loads=[dict(owner='timing',mean_a=.010,event_hz=carrier/16,tau_s=.2e-9,harmonics=64),
        dict(owner='core',mean_a=.020,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)]
    environment['internal_switching_loads']=loads
    context=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
        scenario_overrides=scenario.record(),probe_assumptions=dict(
            internal_switching_loads=loads,
            differential_source_peak_v=differential_source_peak(environment),single_ended_source_peak_v=1.,
            differential_capacitance_f_per_leg=reference_capacitance(environment),
            reference_package_parameters=reference_passive_parameters(environment),
            source_leg_skew_s=reference_source_skew(environment,0.),
            input_model='Shared differential pad, source skew and assigned reference signal package',
            single_ended_capacitance_f_per_leg=3e-12,
            single_ended_control='Diagnostic topology substitution; not a selectable chip setting',
            current_scope='Both topology controls retain the shared inventory; no additional bias allocation'))
    environment['probe_context']=context
    return environment,context


def shared_internal_campaign(*,single=False,design=None):
    """Costed paired clocks and wired readiness under internal switching."""
    from wired_lock_probe import peer_for_environment,resolved_case
    design=load_design() if design is None else design
    rows=[]
    for mode,carrier,word in (('rf',2.4e9,150e6),('rf',2.484e9,155.25e6),('wire',2.5e9,312.5e6)):
        original,context=configured_probe_environment(design,mode,carrier)
        base=None
        if not single:_,base=b.single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False)
        for mismatch,opposed,cm_gain in (((0.,False,0.),) if single else ((.1,True,.1),(.2,False,-.1))):
            for sensitivity in (.1,.025):
                for sign in (1.,-1.):
                    if single:
                        e,report=b.single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False,source_peak_v=1.,supply_sign=sign,sensitivity_ps_per_mv=sensitivity)
                        row=dict(carrier_hz=carrier,supply_sign=sign,sensitivity_ps_per_mv=sensitivity,
                            accepted=e is not None,current_a=report['ledger']['total_chip_supply_current_a'],clock=report['resolved_crossings'])
                    else:
                        e,row=paired_environment(original,dict(mismatch=mismatch,opposed=opposed,cm_gain=cm_gain),sign=sign,sensitivity_ps_per_mv=sensitivity,ledger=base['ledger'])
                    row.update(context)
                    row['input_fixture_options']=dict(mismatch=mismatch,opposed=opposed,cm_gain=cm_gain)
                    row['frontend']='single' if single else 'paired'
                    row['mode']=mode;row['wired']=[]
                    if mode=='wire' and e is not None:
                        for offset in (0,4,8,12):
                            peer,edges,_=peer_for_environment(e,offset)
                            for phase in (-.35,.35):
                                for ppm in (-100.,100.):
                                    row['wired'].append(dict(launch_offset_ui=offset,result=resolved_case(peer,edges,phase,ppm,4,True)))
                    rows.append(row)
                    print('Shared input',mode,carrier,mismatch,sensitivity,sign,flush=True)
    return dict(design_provenance=design.provenance(),cases=rows,frontend='single' if single else 'paired',scope='Single-ended 1 V source control or differential 1 V total source fallback, plus full internal switching; 500 pF/current package target. Paired input needs one extra signal. Both controls retain the current architecture allocation; no additional input-bias current is silently added. Both mismatch cases and sensitivity signs; 0.1/0.025 ps/mV downstream coefficients. Assigned downstream sensitivity is not demonstrated by the input bias allocation. RF clock screens only; wired uses unchanged CTLE/CDR, four launch phases and four receiver corners. Nominal coherent internal pulse phase; no RF payload, physical CMRR/bias, asynchronous phase, BER or protocol qualification.')


def probe_source_hashes():
    hashes=b.baseline_source_hashes()
    for name in ('verification/reference_input_probe.py','verification/wired_lock_probe.py','verification/wideband_packet.py'):
        hashes[name]=hashlib.sha256((p/name).read_bytes()).hexdigest()
    return dict(sorted(hashes.items()))


def verify_probe_sources(hashes):
    if probe_source_hashes()!=hashes:
        raise RuntimeError('Sources changed during reference-input computation')


def shared_rf_campaign(carrier,output,*,acquisition=False,transmit=False,design=None):
    """Matched causal RF payloads with internal currents and reduced sensitivity."""
    design=load_design() if design is None else design
    hashes=probe_source_hashes()
    report=dict(cases=[],campaign_complete=False,expected_cases=3 if acquisition else 6,sources_sha256=hashes,
        scope='Matched 1 V nominal source amplitude with the current RF receive allocation. Differential input still consumes one extra signal. Full internal pulse loads, 500 pF, current package target, shared-contract downstream sensitivity and both signs. Two mismatch cases for paired input; no CMRR mismatch model for single-ended control. Causal SAR/reference-load feedback at 20.48 GHz numerical rate, -85 dBm wanted, -30 dBm blocker at +12 MHz, resolved legal PGA gain and known DATA training. No real preamble, AGC, FEC/PER, TX, full phase/variation or physical input/sensitivity qualification. Source power, delivered voltage and pad loading differ between topologies.')
    if acquisition:
        report['scope']='Matched single-ended and 20% aligned-mismatch paired input under full internal switching and causal SAR feedback. Current RF receive allocation, 500 pF, current package target, 1 V source, negative shared-contract sensitivity. Preselected seed 431, unknown arrival 137 samples and -120 kHz CFO; paired no-wanted control. Real legacy preamble plus diagnostic coded HE20 DATA, not a valid HE packet: known DATA training, fixed gain, no HE fields/AGC/sample-rate ppm or PER qualification. Three cases per frequency; not all seeds, signs or mismatch corners.'
    if transmit:
        report['scope']='Matched single/paired clock input with full internal switching, current RF transmit allocation, 500 pF, current package target, 1 V source, 0.025 ps/mV and both signs/mismatches. Native DAC, third-order reconstruction, upconversion and resistive output port at 20.48 GHz numerical rate. Warm driver with fixed current budget; no causal signal-dependent DAC/driver current, physical glitches, external filter, real framing, FIFO or standard emission-mask qualification. Broad band powers and diagnostic peer decoding only.'
    original,context=configured_probe_environment(design,'rf',carrier,transmit=transmit)
    report.update(context)
    _,base=b.single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False)
    variants=([(None,True),(dict(mismatch=.2,opposed=False,cm_gain=-.1),True),(dict(mismatch=.2,opposed=False,cm_gain=-.1),False)] if acquisition else
        [(opts,True) for opts in (None,dict(mismatch=.1,opposed=True,cm_gain=.1),dict(mismatch=.2,opposed=False,cm_gain=-.1))])
    for opts,wanted_present in variants:
        for sign in ((-1.,) if acquisition else (1.,-1.)):
            if opts is None:
                e,clock=b.single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False,source_peak_v=1.,supply_sign=sign,sensitivity_ps_per_mv=clock_supply_sensitivity(original))
            else:
                e,clock=paired_environment(original,opts,sign=sign,sensitivity_ps_per_mv=clock_supply_sensitivity(original),ledger=base['ledger'])
            row=dict(context,carrier_hz=carrier,frontend='single' if opts is None else 'paired',input_parameters=opts,supply_sign=sign,clock=clock,receiver=None)
            if e is not None:
                if transmit:
                    row['transmitter']=b.wideband_transmit(e,oversample=1024)
                elif acquisition:
                    from wideband_packet import run_acquisition_case
                    packet=run_acquisition_case(e,431,start_sample=137,carrier_offset_hz=-120e3,transmit=wanted_present,oversample=1024)
                    row['receiver']=packet.pop('analog');row['acquisition']=packet
                else:
                    row['receiver']=b.coupled_wideband_feedback(e,wanted_dbm=-85.,gain_db=context['resolved_configuration']['pga_gain_db'],oversample=1024)
                if opts is not None and not transmit:
                    loads=[step['load'] for step in row['receiver']['iterations']]
                    row['causal_input_leg_bounds_v']=(np.array(clock['per_leg_bound_v'])+np.max([x['input_leg_voltage_abs_peak_v'] for x in loads],axis=0)).tolist()
                    row['causal_input_leg_envelope_met']=max(row['causal_input_leg_bounds_v'])<=reference_acceptance_parameters(e)['leg_peak_limit_v']
            report['cases'].append(row)
            write_report(output,report)
            print('Shared RF',carrier,opts,sign,'complete',flush=True)
    if any(hashlib.sha256((p/name).read_bytes()).hexdigest()!=h for name,h in hashes.items()):raise RuntimeError('Sources changed during campaign')
    report['campaign_complete']=len(report['cases'])==report['expected_cases']
    write_report(output,report)
    return report


def shared_wake_campaign(carrier,output,*,design=None):
    design=load_design() if design is None else design
    hashes=probe_source_hashes()
    report=dict(cases=[],campaign_complete=False,expected_cases=6,sources_sha256=hashes,
        scope='Current RF transmit allocation, full internal pulses, 500 pF/current package target, 1 V source, negative shared-contract sensitivity. Single-ended and 20% aligned-mismatch paired input. Driver starts warm or ramps from 0 to its shared-design driver bias at nominal source start, in 20 ns or 1 us. Coupled rail/input/reference/delay and available tail-current limit are applied. Early waveform is compared with matched warm output without fitting away phase/amplitude. No physical bias-readiness, RF switch, preamble, TX mask, signal-dependent DAC/driver current or protocol turnaround qualification.')
    original,context=configured_probe_environment(design,'rf',carrier,transmit=True)
    report.update(context)
    driver_bias=design.architecture['blocks']['rfdriver']['parameters']['bias_current_a']
    _,base=b.single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False)
    for opts in (None,dict(mismatch=.2,opposed=False,cm_gain=-.1)):
        if opts is None:
            e,clock=b.single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False,source_peak_v=1.,supply_sign=-1.,sensitivity_ps_per_mv=clock_supply_sensitivity(original))
        else:e,clock=paired_environment(original,opts,sign=-1.,sensitivity_ps_per_mv=clock_supply_sensitivity(original),ledger=base['ledger'])
        if e is None:
            for ramp in (None,20e-9,1e-6):
                report['cases'].append(dict(context,frontend='single' if opts is None else 'paired',
                    input_parameters=opts,ramp_s=ramp,status='clock_rejected',clock=clock))
            write_report(output,report)
            continue
        warm={}
        for ramp in (None,20e-9,1e-6):
            trial=e;load=None;captured={}
            if ramp is not None:
                response,load=b.driver_wake_response(e,released_current_a=driver_bias,wake_start_s=2e-6,ramp_s=ramp,grid_s=.25e-9,reference_input=e.get('reference_load_parameters',{}))
                trial=dict(e,local_load_response=response)
            tx=b.wideband_transmit(trial,oversample=1024,onset_capture=captured)
            if ramp is None:warm=captured
            np.testing.assert_array_equal(captured['times_s'],warm['times_s'])
            mask=(captured['times_s']>=2e-6)&(captured['times_s']<3e-6)
            relative=float(np.sqrt(np.sum(abs(captured['emitted_v'][mask]-warm['emitted_v'][mask])**2)/np.sum(abs(warm['emitted_v'][mask])**2)))
            row=dict(context,carrier_hz=carrier,input_parameters=opts,released_current_a=driver_bias,frontend='single' if opts is None else 'paired',ramp_s=ramp,clock=clock,load=load,transmitter=tx,first_us_relative_waveform_error=relative)
            if opts is not None and load is not None:
                bound=np.array(clock['per_leg_bound_v'])+load['input_leg_voltage_abs_peak_v']
                row.update(input_leg_bound_v=bound.tolist(),input_leg_envelope_met=bool(max(bound)<=reference_acceptance_parameters(e)['leg_peak_limit_v']))
            report['cases'].append(row);write_report(output,report)
            print('Shared wake',carrier,opts,ramp,relative,flush=True)
    if any(hashlib.sha256((p/name).read_bytes()).hexdigest()!=h for name,h in hashes.items()):raise RuntimeError('Sources changed during campaign')
    report['campaign_complete']=len(report['cases'])==6;write_report(output,report)


def write_report(path,report):
    normalized=json.loads(json.dumps(report,allow_nan=False,default=lambda value:value.item()))
    b.write_evidence(path,normalized)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--causal',action='store_true',help='Join SAR feedback at current package target; single-ended control uses 1 V peak')
    parser.add_argument('--output',type=Path,default=p/'evidence/reference-input-probe.json')
    parser.add_argument('--shared-internal',action='store_true')
    parser.add_argument('--shared-single',action='store_true')
    parser.add_argument('--shared-rf-mhz',type=int,choices=(2400,2484))
    parser.add_argument('--shared-acquisition-mhz',type=int,choices=(2400,2484))
    parser.add_argument('--shared-tx-mhz',type=int,choices=(2400,2484))
    parser.add_argument('--shared-wake-mhz',type=int,choices=(2400,2484))
    args=parser.parse_args()
    design=load_design()
    if args.shared_wake_mhz is not None:
        shared_wake_campaign(args.shared_wake_mhz*1e6,p/f'evidence/shared-input-wake-{args.shared_wake_mhz}.json',design=design)
        return
    if args.shared_tx_mhz is not None:
        shared_rf_campaign(args.shared_tx_mhz*1e6,p/f'evidence/shared-input-tx-{args.shared_tx_mhz}.json',transmit=True,design=design)
        return
    if args.shared_acquisition_mhz is not None:
        shared_rf_campaign(args.shared_acquisition_mhz*1e6,p/f'evidence/shared-input-acquisition-{args.shared_acquisition_mhz}.json',acquisition=True,design=design)
        return
    if args.shared_rf_mhz is not None:
        shared_rf_campaign(args.shared_rf_mhz*1e6,p/f'evidence/shared-input-rf-{args.shared_rf_mhz}.json',design=design)
        return
    hashes=probe_source_hashes()
    validation=check_network(design=design)
    if args.check:
        validation['transient']=check_package_transient(design=design)
        validation['periodic_continuation']=check_package_continuation(design=design)
        verify_probe_sources(hashes)
        validation['sources_sha256']=hashes
        print(json.dumps(validation,indent=2)); return
    if args.shared_internal or args.shared_single:
        report=shared_internal_campaign(single=args.shared_single,design=design);report['validation']=validation
        verify_probe_sources(hashes)
        report['sources_sha256']=hashes
        write_report(p/('evidence/shared-single-internal.json' if args.shared_single else 'evidence/shared-input-internal.json'),report)
        return
    paired=paired_rf(args.causal,design=design)
    controls=single_rf(args.causal,design=design)
    report=dict(validation=validation,paired=paired,single=controls,causal_requested=args.causal,
        scope='Differential clock-input mismatch sensitivity and explicit single-ended comparison. Both retain the current architecture allocation; differential Thevenin amplitude, leg skew and paired pad/package values come from the shared design; single-ended capacitance remains an explicit 3 pF control. Opposed 10% or aligned 20% C/L mismatch, half that source resistance/amplitude mismatch and signed 20 dB common-mode rejection. The rf field is assigned ENOB. When requested, causal fields add SAR reference-load feedback at the 0.25 nH target for both differential probes and the 1 V single-ended control. No physical receiver bias/headroom, measured CMRR, direct pad crosstalk or protocol qualification. Two RF frequencies, two package cases, two supply-delay signs; not a continuous uncertainty bound.',
        sources_sha256=hashes)
    verify_probe_sources(hashes)
    args.output.write_text(json.dumps(report,indent=2,default=lambda v:v.item())+'\n')



class ConfiguredReferenceEdges:
    """Finite edge windows from the shared paired input; no coherent-period fiction.

    Same phasor network, pad envelope and threshold rule as paired_environment.
    Source/host spectra are prescribed stationary stimuli. Grid agreement is
    diagnostic, not a proof against arbitrarily narrow extra crossings.
    """
    def __init__(self,environment,*,source_peak_v=None,window_edges=32):
        import math
        if type(window_edges) is not int or window_edges<1:
            raise ValueError('Positive finite edge window size required')
        self.environment=deepcopy(environment);e=self.environment
        self.carrier=e['carrier_hz'];self.window_edges=window_edges;self.windows={}
        self.parameters=reference_acceptance_parameters(e)
        peak=differential_source_peak(e,source_peak_v)
        opts=e['clock_input_configuration']['input_model']
        wanted=environment_port(self.carrier,e,np.zeros(5),source_diff=peak,**opts)
        self.carrier_v=wanted['effective'];self.tones=[];self.delays=[]
        bound=abs(wanted['local']).copy()
        gain=b.supply_delay_gain(e['clock_input_configuration']['supply_sensitivity_ps_per_mv'],1.)
        for frequency,injection in b.partitioned_host_sources(e).items():
            r=environment_port(frequency,e,injection,**opts)
            self.tones.append((frequency,r['effective']));bound+=abs(r['local'])
            rail=r['network'][1]-r['network'][3]
            self.delays.append((frequency,rail*gain/(1+1j*frequency/clock_supply_delay_pole(e))))
        rail=wanted['network'][1]-wanted['network'][3]
        self.delays.append((self.carrier,rail*gain/(1+1j*self.carrier/clock_supply_delay_pole(e))))
        self.threshold=self.parameters['threshold_v']
        if abs(self.carrier_v)<=abs(self.threshold):raise ValueError('Reference lacks threshold crossing')
        effective=abs(self.carrier_v)+sum(abs(v) for _,v in self.tones)
        if effective>self.parameters['effective_peak_limit_v'] or max(bound)>self.parameters['leg_peak_limit_v']:
            raise ValueError('Reference input envelope rejected')
        self.offset=((np.arcsin(self.threshold/abs(self.carrier_v))-
                      np.angle(self.carrier_v)-np.pi/2)%(2*np.pi))/(2*np.pi)
        noise=e['clock_input_noise_parameters']
        equivalent=e['external_clock_input']['source_peak_v']*abs(self.carrier_v)/e['external_clock_input']['receiver_peak_v']
        added,_=loaded_clock_input_phase(self.carrier,receiver_noise_v=np.sqrt(2)*noise['receiver_noise_v'],
            downstream_stage_rms_s=noise['downstream_stage_rms_s'],source_peak_v=equivalent,
            threshold_v=self.threshold,peak_limit_v=self.parameters['effective_peak_limit_v'])
        self.phase_tones=tuple(e['phase_components']['source'])+tuple(added.tones)
        self.report=dict(design_provenance=e['design_provenance'],resolved_configuration=e['resolved_configuration'],
            input_reference_hz=self.carrier,source_differential_peak_v=peak,
            per_leg_bound_v=bound.tolist(),effective_bound_v=float(effective),
            frequency_rounding=False,periodic_repetition=False,window_edges=window_edges,
            scope='Shared stationary pad/package forcing with finite threshold-edge windows and assigned source/input noise.')

    def _voltage(self,t):
        return np.real(self.carrier_v*np.exp(2j*np.pi*self.carrier*t))-self.threshold+sum(
            np.real(v*np.exp(2j*np.pi*f*t)) for f,v in self.tones)

    def _window(self,start):
        indices=np.arange(start,start+self.window_edges+1)
        nominal=(indices+self.offset)/self.carrier
        brackets=[]
        for count in (32,64):
            grid=nominal[:,None]+np.linspace(-.5,.5,count+1)[None,:]/self.carrier
            value=self._voltage(grid)
            crossings=(value[:,:-1]<0)&(value[:,1:]>=0)
            if not np.all(crossings.sum(axis=1)==1):
                raise ValueError('Missing or multiple reference input edges')
            selected=np.argmax(crossings,axis=1)
            lo=grid[np.arange(len(indices)),selected];hi=lo+1/(count*self.carrier)
            brackets.append((lo,hi))
        lo,hi=brackets[-1]
        for _ in range(34):
            middle=(lo+hi)/2;above=self._voltage(middle)>=0
            hi=np.where(above,middle,hi);lo=np.where(above,lo,middle)
        roots=(lo+hi)/2
        if np.any(roots<brackets[0][0]) or np.any(roots>brackets[0][1]):
            raise ValueError('Reference edge grids disagree')
        delay=sum((np.real(v*np.exp(2j*np.pi*f*roots)) for f,v in self.delays),np.zeros_like(roots))
        phase=sum((a*np.cos(2*np.pi*f*roots+p) for f,a,p in self.phase_tones),np.zeros_like(roots))
        edges=roots+delay-phase/(2*np.pi*self.carrier)
        if not np.all(np.isfinite(edges)) or np.any(np.diff(edges)<=0):
            raise ValueError('Reference noise/delay reverses edge ordering')
        return edges

    def __call__(self,index):
        if type(index) is not int or index<1:raise ValueError('Positive reference edge index required')
        start=1+((index-1)//self.window_edges)*self.window_edges
        if start not in self.windows:self.windows[start]=self._window(start)
        return float(self.windows[start][index-start])


if __name__=='__main__':main()
