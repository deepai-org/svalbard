"""Independent KCL, energy, subdivision and explicit pulse-compliance screens."""
import json
import math
import numpy as np
from charge_pump_filter import ChargePumpFilter
from autonomous_pll import AutonomousPLL
from chip_model import P


def controls():
    a=ChargePumpFilter(60e3,.2e-12,4e-12,voltage=.25)
    b=ChargePumpFilter(60e3,.2e-12,4e-12,voltage=.25)
    initial_charge=a.cf*a.v+a.cs*a.w
    for time,current in ((5e-9,100e-6),(100e-9,0.),(105e-9,-100e-6),(200e-9,0.)):
        start=b.time
        a.advance(time,current)
        for index in range(1,101):b.advance(start+(time-start)*index/100,current)
    assert abs(a.v-b.v)<1e-12 and abs(a.w-b.w)<1e-12
    assert abs(a.voltage_integral-b.voltage_integral)<1e-19
    assert abs(a.cf*a.v+a.cs*a.w-initial_charge-a.charge)<1e-26
    assert abs(a.metrics()['energy_residual_j'])<1e-24
    # Independent small-step midpoint integration of capacitor KCL equations.
    v=w=.25;dt=1e-12;source=100e-6;count=5000
    for _ in range(count):
        av=(source-(v-w)/a.r)/a.cf;aw=(v-w)/(a.r*a.cs)
        vm=v+dt*av/2;wm=w+dt*aw/2
        v+=dt*(source-(vm-wm)/a.r)/a.cf
        w+=dt*(vm-wm)/(a.r*a.cs)
    c=ChargePumpFilter(a.r,a.cf,a.cs,voltage=.25);c.advance(count*dt,source)
    assert max(abs(c.v-v),abs(c.w-w))<1e-8
    return dict(subdivision_voltage_error=max(abs(a.v-b.v),abs(a.w-b.w)),
                midpoint_kcl_error=max(abs(c.v-v),abs(c.w-w)),energy_residual_j=a.metrics()['energy_residual_j'])


def local_matrices(pll,fraction):
    current=100e-6;period=1/pll.reference_hz;g=pll.kvco/pll.divider
    matrices={}
    for kind in ('held_current','impulsive_charge'):
        columns=[]
        for error,voltage,slow in np.eye(3):
            f=ChargePumpFilter.from_gains(pll.kp,pll.ki,current,fraction)
            f.v=voltage;f.w=slow
            if kind=='impulsive_charge':f.v+=current*period*error/f.cf
            f.advance(period,current*error if kind=='held_current' else 0.)
            columns.append((error-g*f.voltage_integral,f.v,f.w))
        matrices[kind]=np.array(columns).T
    # Finite positive-width pulses converge to the impulsive small-signal map.
    differences=[]
    for error in (1e-5,1e-6,1e-7):
        f=ChargePumpFilter.from_gains(pll.kp,pll.ki,current,fraction)
        f.advance(error*period,current);f.advance(period,0.)
        column=np.array((error-g*f.voltage_integral,f.v,f.w))/error
        differences.append(float(max(abs(column-matrices['impulsive_charge'][:,0]))))
    assert differences[-1]<differences[0]/20
    return dict(held_current_radius=float(max(abs(np.linalg.eigvals(matrices['held_current'])))),
                impulsive_charge_radius=float(max(abs(np.linalg.eigvals(matrices['impulsive_charge'])))),
                finite_pulse_linearization_errors=differences)


def screen(rate,fraction,width):
    p=AutonomousPLL(reference_hz=10e6,divider=rate/10e6,free_hz=rate*.96,
                    phase_cycles=.05,lock_phase_cycles=.0025,lock_frequency_hz=1000)
    current=100e-6;bias=(rate-p.free_hz)/p.kvco
    f=ChargePumpFilter.from_gains(p.kp,p.ki,current,fraction,voltage=bias)
    assert abs(current/f.total-p.ki)<1e-7
    assert abs(current*f.r*(f.cs/f.total)**2-p.kp)<1e-12
    period=1/p.reference_hz
    # Balanced alternating UP/DOWN pulses avoid imposing a fictitious DC phase
    # error forever; this is an open-loop stress fixture, not a closed-loop PFD.
    for index in range(64):
        start=index*period;sign=1 if index%2==0 else -1
        f.advance(start+width,sign*current);f.advance(start+period,0.)
    row=f.metrics();row.update(local_stability=local_matrices(p,fraction),rate_hz=rate,fast_fraction=fraction,pulse_width_s=width,
        current_a=current,nominal_bias_v=bias,requested_kp=p.kp,requested_ki=p.ki)
    assert abs(row['energy_residual_j'])<1e-22
    return row


def main():
    checks=controls()
    rows=[screen(rate,fraction,width) for rate in (1.25e9,2.5e9)
          for fraction in (.02,.1,.2,.5) for width in (250e-12,5e-9)]
    assert any(not row['ideal_current_within_compliance'] for row in rows)
    assert any(row['ideal_current_within_compliance'] for row in rows)
    # The two detector-waveform approximations disagree for the large shunt
    # capacitor. Do not call it stable without closing the actual pulse loop.
    assert all(row['local_stability']['held_current_radius']>1 and
               row['local_stability']['impulsive_charge_radius']<1
               for row in rows if row['fast_fraction']==.5)
    report=dict(status='passed',controls=checks,cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Explicit imposed balanced current pulses into an exact passive network; not yet closed around actual reference/feedback-edge PFD logic.',
            'Voltage excursions outside the declared control/compliance range invalidate ideal-current operation; no capacitor voltage is clipped to fake feasibility.',
            'The100uA current, control range and VCO gain are assumed. Compliance droop, pump mismatch, leakage and noise are absent.',
            'Preserving low-frequency PI coefficients introduces an extra pole; held-current and impulsive-detector stability can disagree. Actual edge-driven PFD feedback remains required.'])
    (P/'evidence/connected-charge-pump-filter.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed passive-filter KCL/energy controls and16 pulse/compliance screens')
    for row in rows:
        if row['pulse_width_s']==5e-9:
            print(row['rate_hz'],row['fast_fraction'],row['maximum_v'],row['extra_pole_hz'],row['ideal_current_within_compliance'])


if __name__=='__main__':main()
