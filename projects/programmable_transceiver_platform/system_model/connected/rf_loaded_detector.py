"""Connect continuous switched-network voltage to the finite power detector.

Exponential source coefficients are RMS Thevenin-voltage envelopes at the
current network time. No hidden gain normalization or ideal monitor is used.
"""
import numpy as np
from rf_switched_load import SwitchedLoad
from tx_power_detector import PowerDetector

def voltage_terms(network,source_terms):
    if not source_terms or any(not np.isfinite(a) or not np.isfinite(p) for a,p in source_terms):
        raise ValueError('Finite nonempty exponential source required')
    rates,vectors=np.linalg.eig(network.A)
    if np.linalg.cond(vectors)>1e8:raise ValueError('Ill-conditioned network modes')
    drive=np.linalg.solve(network.C,np.array([1/50,0,0,0]))
    particular=[]
    for amplitude,rate in source_terms:
        matrix=rate*np.eye(4)-network.A
        if np.linalg.cond(matrix)>1e12:raise ValueError('Resonant source needs polynomial-exponential representation')
        particular.append((np.linalg.solve(matrix,drive*amplitude),rate))
    residual=network.voltage-sum((v for v,p in particular),np.zeros(4,dtype=complex))
    modal=np.linalg.solve(vectors,residual)
    return particular+[(vectors[:,i]*modal[i],rates[i]) for i in range(4)]

class LoadedDetector:
    def __init__(self,network=None,detector=None):
        self.network=network if network is not None else SwitchedLoad()
        self.detector=detector if detector is not None else PowerDetector()
        if self.network.time!=self.detector.time:raise ValueError('Unaligned analog clocks')
    def advance(self,time,source_terms):
        n=self.network;dt=time-n.time
        if not np.isfinite(dt) or dt<0:raise ValueError('Invalid time')
        terms=voltage_terms(n,source_terms)
        voltage=sum((v*np.exp(p*dt) for v,p in terms),np.zeros(4,dtype=complex))
        self.detector.advance(time,[(complex(v[2]),complex(p)) for v,p in terms])
        n.voltage=voltage;n.time=time
        return voltage.copy()
