import numpy as np, re
def read(path):
    """ngspice binary rawfile (real, unpadded) -> dict name -> array (lower-case names)."""
    b = open(path, 'rb').read()
    i = b.index(b'Binary:\n')
    hdr = b[:i].decode('latin1')
    nv = int(re.search(r'No\. Variables:\s*(\d+)', hdr).group(1))
    npts = int(re.search(r'No\. Points:\s*(\d+)', hdr).group(1))
    names = [l.split()[1].lower() for l in hdr.split('Variables:\n')[1].strip().splitlines()[:nv]]
    d = np.frombuffer(b, dtype='<f8', count=nv*npts, offset=i+8).reshape(npts, nv)
    return {n: d[:, k] for k, n in enumerate(names)}
