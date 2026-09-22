"""Weighted finite-record multitone fit; peak phasor uses exp(+jwt)."""
import numpy as np

def fit(t,y,frequencies):
 columns=[np.ones(len(t)),(t-t.mean())/(t[-1]-t[0])]
 for f in frequencies:columns.extend([np.cos(2*np.pi*f*t),np.sin(2*np.pi*f*t)])
 design=np.column_stack(columns);dt=np.diff(t);weights=np.r_[dt[0]/2,(dt[:-1]+dt[1:])/2,dt[-1]/2];weights/=weights.sum();root=np.sqrt(weights)
 co,_,rank,_=np.linalg.lstsq(design*root[:,None],y*root,rcond=None);assert rank==design.shape[1]
 phasor=co[2]-1j*co[3];res=y-design@co
 return phasor,float(np.sqrt(np.sum(weights*res**2)))
