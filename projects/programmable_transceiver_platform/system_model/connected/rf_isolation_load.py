"""Three-node linear isolation/monitor network using RMS phasors.

Finite source R drives an internal node, Riso||Cfeed connects that node to
an externally loaded pad. Monitor Rtap feeds Rin||Cin from either node.
This is a topology sensitivity model, not a GF180 switch or package model.
"""
import math
import numpy as np

def solve(frequency_hz,*,source_v=1.,source_ohm=50.,load_ohm=50.,
          isolation_ohm=5.,feedthrough_f=1e-15,tap_ohm=1000.,
          input_ohm=10000.,input_f=50e-15,monitor_location='upstream',dummy_ohm=None):
    positive=(frequency_hz,source_ohm,load_ohm,isolation_ohm,tap_ohm,input_ohm)
    if not all(math.isfinite(x) and x>0 for x in positive):raise ValueError('Invalid resistance/frequency')
    if not all(math.isfinite(x) and x>=0 for x in (feedthrough_f,input_f)) or not math.isfinite(source_v):raise ValueError('Invalid capacitance/source')
    if monitor_location not in ('upstream','pad'):raise ValueError('Invalid monitor location')
    if dummy_ohm is not None and (not math.isfinite(dummy_ohm) or dummy_ohm<=0):raise ValueError('Invalid dummy load')
    gd=0. if dummy_ohm is None else 1/dummy_ohm
    omega=2*math.pi*frequency_hz
    gs=1/source_ohm;gl=1/load_ohm;gt=1/tap_ohm
    yi=1/isolation_ohm+1j*omega*feedthrough_f;ym=1/input_ohm+1j*omega*input_f
    # Nodes: internal driver, pad, monitor. Explicit branch stamps.
    a=np.diag(np.array([gs+gd,gl,ym],dtype=complex))
    def stamp(i,j,y):
        a[i,i]+=y;a[j,j]+=y;a[i,j]-=y;a[j,i]-=y
    stamp(0,1,yi);tap=0 if monitor_location=='upstream' else 1;stamp(tap,2,gt)
    v=np.linalg.solve(a,np.array([source_v*gs,0,0],dtype=complex))
    internal,pad,monitor=v
    source_i=(source_v-internal)*gs;iso_i=(internal-pad)*yi;tap_i=(v[tap]-monitor)*gt
    loss=dict(dummy_load=abs(internal)**2*gd,source_resistor=abs(source_i)**2*source_ohm,
        isolation_resistor=abs(internal-pad)**2/isolation_ohm,
        external_load=abs(pad)**2/load_ohm,tap_resistor=abs(tap_i)**2*tap_ohm,
        detector_resistor=abs(monitor)**2/input_ohm)
    power=(source_v*source_i.conjugate()).real
    # Independent KCL expressions, not just reuse the matrix residual.
    residual=[source_i-internal*gd-iso_i-(tap_i if tap==0 else 0),
              iso_i-pad*gl-(tap_i if tap==1 else 0),tap_i-monitor*ym]
    return dict(internal=internal,pad=pad,monitor=monitor,source_current=source_i,
        losses=loss,source_real_power=power,kcl_error=max(abs(x) for x in residual),
        power_error=abs(power-sum(loss.values())))
