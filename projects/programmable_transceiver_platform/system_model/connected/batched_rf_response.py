"""Batched linear solves for the same loaded-network exponential response."""
import numpy as np

def voltage_terms(network,source_terms):
    if not source_terms:raise ValueError('Finite nonempty exponential source required')
    source=np.asarray(source_terms,dtype=complex)
    if source.ndim!=2 or source.shape[1]!=2 or not np.all(np.isfinite(source)):
        raise ValueError('Invalid exponential source')
    rates,vectors=np.linalg.eig(network.A)
    if np.linalg.cond(vectors)>1e8:raise ValueError('Ill-conditioned network modes')
    drive=np.linalg.solve(network.C,np.array([1/50,0,0,0]))
    matrices=source[:,1,None,None]*np.eye(4)[None,:,:]-network.A[None,:,:]
    if np.any(np.linalg.cond(matrices)>1e12):raise ValueError('Resonant source needs polynomial-exponential representation')
    rhs=source[:,0,None]*drive[None,:]
    forced=np.linalg.solve(matrices,rhs[:,:,None])[:,:,0]
    modal=np.linalg.solve(vectors,network.voltage-np.sum(forced,axis=0))
    return [(v,p) for v,p in zip(forced,source[:,1])]+[(vectors[:,i]*modal[i],rates[i]) for i in range(4)]
