"""Atomic paired fixed-point I/Q correction before the physical DAC transfer.

Coefficients are loaded at construction; live update ownership is not provided.
Full-scale range matches signed normalized samples [-1, 1-2**(1-bits)].
"""
import math
import numpy as np

class DacCorrection:
    def __init__(self,calibration,bits,dc_gain=1.):
        if bits not in (8,10,12) or not math.isfinite(dc_gain) or dc_gain<=0:
            raise ValueError('Invalid DAC format or reconstruction DC gain')
        self.bits=bits;self.scale=1<<(bits-1);self.dc_gain=dc_gain
        self.matrix=np.asarray(calibration['matrix'],float).copy()
        self.offset=np.asarray(calibration['offset'],float).copy()/dc_gain
        if self.matrix.shape!=(2,2) or self.offset.shape!=(2,) or not np.all(np.isfinite(self.matrix)) or not np.all(np.isfinite(self.offset)):
            raise ValueError('Invalid correction coefficients')
        self.applied=0;self.rejected=0;self.last_codes=None
    def __call__(self,time,value):
        z=complex(value)
        v=self.matrix@np.array([z.real,z.imag])+self.offset
        if not np.all(np.isfinite(v)) or np.any(v < -1) or np.any(v>1-1/self.scale):
            self.rejected+=1;raise ValueError('Paired DAC correction exceeds headroom')
        codes=np.rint(v*self.scale).astype(int)
        self.last_codes=tuple(int(c) for c in codes);self.applied+=1
        return complex(*[float(c/self.scale) for c in codes])
