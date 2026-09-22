"""Read phase-aware network pad voltage in an independent carrier frame.

Only for networks already driven by the physical LO phase. No source-voltage
reconstruction, gain normalization or additional LO rotation is applied.
"""
import math,cmath

def observe(network,time,carrier_hz):
    if not math.isfinite(time) or not math.isfinite(carrier_hz) or carrier_hz<=0:
        raise ValueError('Finite time and positive observation carrier required')
    if network.time!=time:raise ValueError('Pad network must be advanced to observation time')
    delta=network.omega-2*math.pi*carrier_hz
    return complex(network.voltage[1])*cmath.exp(1j*math.remainder(delta*time,2*math.pi))
