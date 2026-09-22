"""Exact Fourier projection of piecewise-constant differential mixer drive.

Input values are normalized switching effectiveness, not gate voltages. Mapping
GF180 gate voltage/load to these values requires separate circuit evidence.
"""
import cmath
import math

def coefficient(edges,values,frequency_hz):
    if len(edges)!=len(values)+1 or not values:raise ValueError('Require interval edges and values')
    if not all(math.isfinite(x) for x in list(edges)+list(values)+[frequency_hz]):raise ValueError('Nonfinite drive')
    if any(b<=a for a,b in zip(edges,edges[1:])):raise ValueError('Nonincreasing edges')
    duration=edges[-1]-edges[0]
    if frequency_hz==0:return sum(v*(b-a) for a,b,v in zip(edges,edges[1:],values))/duration
    omega=2*math.pi*frequency_hz
    # Midpoint/sinc form avoids cancellation for very short edge intervals.
    return sum(v*(b-a)*cmath.exp(-1j*omega*(a+b)/2)*
               (math.sin(omega*(b-a)/2)/(omega*(b-a)/2))
               for a,b,v in zip(edges,edges[1:],values))/duration

def iq_projection(edges,i_values,q_values,carrier_hz):
    ci=coefficient(edges,i_values,carrier_hz);cq=coefficient(edges,q_values,carrier_hz)
    normalization=4/math.pi
    desired=(ci+1j*cq)/normalization
    image=(ci.conjugate()+1j*cq.conjugate())/normalization
    return dict(desired=desired,image=image,
        dc=complex(coefficient(edges,i_values,0),coefficient(edges,q_values,0)),
        image_relative_rms=abs(image/desired) if desired else math.inf)

def square_fixture(carrier_hz,cycles=240,missing_i_period=None,i_scale=1.,q_scale=1.):
    """Quarter-cycle edges; missing I cycles become zero differential drive."""
    if carrier_hz<=0 or type(cycles) is not int or cycles<1:raise ValueError('Invalid fixture')
    if missing_i_period is not None and (type(missing_i_period) is not int or missing_i_period<1):raise ValueError('Invalid dropout period')
    edges=[k/(4*carrier_hz) for k in range(4*cycles+1)]
    iv=[];qv=[]
    for k in range(4*cycles):
        cycle,quarter=divmod(k,4)
        i=(1 if quarter in (0,3) else -1)*i_scale
        q=(1 if quarter in (0,1) else -1)*q_scale
        iv.append(0. if missing_i_period is not None and cycle%missing_i_period==0 else i)
        qv.append(q)
    return edges,iv,qv

def iq_sidebands(edges,i_values,q_values,carrier_hz,offsets_hz):
    """Retained envelope Fourier terms around both LO carrier signs.

    Uses the same complex-LO convention as iq_projection. For periodic records,
    offsets should be integer multiples of 1/record_duration. This is a truncated
    envelope expansion; it does not model carrier harmonics or gate physics.
    """
    if not math.isfinite(carrier_hz) or carrier_hz<=0:
        raise ValueError('Invalid carrier')
    result=[]
    for offset in offsets_hz:
        if not math.isfinite(offset) or abs(offset)>=carrier_hz:
            raise ValueError('Offsets must lie strictly between carrier signs')
        def iq(f):
            return (coefficient(edges,i_values,f)+1j*coefficient(edges,q_values,f))/(4/math.pi)
        result.append((offset,iq(carrier_hz+offset),iq(-carrier_hz+offset)))
    return result
