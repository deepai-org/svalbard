"""Anti-resonance finder (copied from e2_impedance.py so PD2 scripts can import it without running E2)."""
import numpy as np
def peaks(f, z):
    out = []
    for k in range(1, len(f)-1):
        if z[k] > z[k-1] and z[k] >= z[k+1] and 5e6 < f[k] < 5e9:
            h = z[k]/np.sqrt(2); a = k
            while a > 0 and z[a] > h: a -= 1
            b = k
            while b < len(f)-1 and z[b] > h: b += 1
            out.append(dict(f_MHz=round(f[k]/1e6, 1), Z=round(float(z[k]), 2), Q=round(float(f[k]/(f[b]-f[a])), 1)))
    return sorted(out, key=lambda d: -d['Z'])[:3]
