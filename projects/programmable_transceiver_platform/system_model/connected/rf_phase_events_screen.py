"""Drive loaded RF network from an autonomous noisy oscillator prediction."""
import copy,json,math,pickle
from itertools import product
import numpy as np
from chip_model import P
from fractional_rf_chip import ShapedRFClock
from oscillator_noise import FrequencyNoise
from rf_loaded_detector import LoadedDetector
from rf_phase_forcing import advance_phase

def main():
    clock=ShapedRFClock(reference_hz=40e6,divider=60,free_hz=2.4e9*.96,
        phase_cycles=.2,bandwidth_hz=300e3,fast_fraction=.30)
    clock.retarget(0,2412000000);clock.set_noise(0,FrequencyNoise.seeded(20000,seed=830))
    clock.advance(40e-6);snapshot=(clock.time,clock.output_phase_cycles)
    original_state=pickle.dumps(clock)
    origin=clock.time
    future=copy.copy(clock);future.advance(origin+100e-9)
    events=sorted(set(t-origin for t,current in future.transitions if origin<t<origin+100e-9))
    assert events

    def phase(t):
        trial=copy.copy(clock);trial.advance(origin+t)
        return 2*math.pi*(trial.output_phase_cycles-2412000000*(origin+t))
    rows=[];results=[]
    source=[(.2+.05j,0j),(.05,-2e7+2j*math.pi*3e6)]
    for aligned,step in product((False,True),(4e-9,1e-9,.25e-9)):
        load=LoadedDetector();load.network.configure(True,False)
        diag=dict(steps=0,max_midpoint_phase_error=0.);trace=[];powers=[]
        for endpoint in np.linspace(10e-9,100e-9,10):
            start=load.network.time
            part=advance_phase(load,float(endpoint),[(v*np.exp(p*start),p) for v,p in source],phase,step,events if aligned else ())
            diag['steps']+=part['steps']
            diag['max_midpoint_phase_error']=max(diag['max_midpoint_phase_error'],part['max_midpoint_phase_error'])
            trace.append(load.network.voltage.copy());powers.append(load.detector.value)
        results.append((np.array(trace),np.array(powers)))
        rows.append(dict(event_aligned=aligned,step_s=step,**diag,monitor_power=load.detector.value))
    assert pickle.dumps(clock)==original_state
    assert snapshot==(clock.time,clock.output_phase_cycles)
    for row,(v,p) in zip(rows,results):
        row['voltage_difference_from_finest']=float(np.max(abs(v-results[-1][0])))
        row['detector_difference_from_finest']=float(np.max(abs(p-results[-1][1])))
    assert rows[1]['voltage_difference_from_finest']<1e-6
    assert rows[1]['detector_difference_from_finest']<1e-8
    assert rows[4]['voltage_difference_from_finest']<1e-8
    assert rows[4]['voltage_difference_from_finest']<rows[1]['voltage_difference_from_finest']/10
    # Linear phase is exact for any subdivision, independently check rate shift.
    a=LoadedDetector();b=LoadedDetector();slope=2*math.pi*17e6;offset=.7
    advance_phase(a,10e-9,source,lambda t:offset+slope*t,3e-9)
    b.advance(10e-9,[(v*np.exp(1j*offset),p+1j*slope) for v,p in source])
    assert max(abs(a.network.voltage-b.network.voltage))<1e-12
    assert abs(a.detector.value-b.detector.value)<1e-12
    report=dict(status='passed',cases=rows,phase_event_times=events,limitations=[
        'One100ns noisy oscillator trajectory; finite step convergence is not a global error guarantee.',
        'Midpoint residual is diagnostic and can miss high-frequency phase structure.',
        'Clock is forecast without mutation; future external disturbances must split forcing intervals.',
        'Not yet connected to managed loaded-chip timing or full-chain quality.'])
    (P/'evidence/connected-rf-phase-events.json').write_text(json.dumps(report,indent=2)+'\n');print(rows)

if __name__=='__main__':main()
