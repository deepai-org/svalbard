"""Small frequency-domain nodal solver for the M1 PDN model (linear R/L/C + mutually coupled RL groups).
Node 0 (name 'gnd') is the reference (board ground plane). All branches are admittances, so no MNA
current unknowns are needed: Y(w) V = I.  DC is w = 0 (capacitors open)."""
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spl


class Net:
    def __init__(self):
        self.idx = {'gnd': -1}; self.names = []
        self.rl = []      # (a, b, R, L)
        self.rc = []      # (a, b, R, C)  series R-C
        self.coupled = [] # (pairs[(a,b)], Rvec, Lmatrix)
        self.gshunt = []  # (a, b, G)

    def n(self, name):
        if name not in self.idx:
            self.idx[name] = len(self.names); self.names.append(name)
        return self.idx[name]

    def add_rl(self, a, b, R, L=0.0): self.rl.append((self.n(a), self.n(b), R, L))
    def add_rc(self, a, b, R, C): self.rc.append((self.n(a), self.n(b), R, C))
    def add_coupled(self, pairs, R, Lm):
        self.coupled.append(([(self.n(a), self.n(b)) for a, b in pairs], np.asarray(R, float), np.asarray(Lm, float)))

    def Y(self, w):
        N = len(self.names); r = []; c = []; v = []
        def st(a, b, y):
            for (i, j, s) in ((a, a, 1), (b, b, 1), (a, b, -1), (b, a, -1)):
                if i >= 0 and j >= 0: r.append(i); c.append(j); v.append(s*y)
        for a, b, R, L in self.rl: st(a, b, 1.0/(R+1j*w*L))
        for a, b, R, C in self.rc:
            if w > 0: st(a, b, 1.0/(R+1.0/(1j*w*C)))
        for pairs, R, Lm in self.coupled:
            Yb = np.linalg.inv(np.diag(R)+1j*w*Lm)
            for p, (a, b) in enumerate(pairs):
                for q, (cn, d) in enumerate(pairs):
                    y = Yb[p, q]
                    for (i, j, s) in ((a, cn, 1), (b, d, 1), (a, d, -1), (b, cn, -1)):
                        if i >= 0 and j >= 0: r.append(i); c.append(j); v.append(s*y)
        return sp.csc_matrix((np.array(v, complex), (r, c)), shape=(N, N))

    def solve(self, w, rhs):
        """rhs: (N, k) complex injections (current INTO node). Returns (N, k) node voltages."""
        lu = spl.splu(self.Y(w)+sp.identity(len(self.names), format='csc')*1e-12)
        return lu.solve(np.asarray(rhs, complex))

    def inj(self, entries):
        """entries: list of (node_name, current_into_node). Returns an RHS column."""
        x = np.zeros(len(self.names), complex)
        for nm, i in entries:
            k = self.idx[nm]
            if k >= 0: x[k] += i
        return x

    def v(self, V, name):
        k = self.idx[name]
        return 0.0 if k < 0 else V[k]


def pulse_harm(i_avg, f0, tw, n):
    """Peak amplitude of the n-th harmonic of a periodic triangular current pulse train (base 2*tw, mean i_avg)."""
    return 2*i_avg*np.sinc(n*f0*tw)**2

def trap_harm(i_pp, f0, tr, n, duty=0.5):
    """Peak amplitude of harmonic n of a trapezoid (square with 10-90-ish edge tr) of pk-pk i_pp."""
    return 2*i_pp*abs(np.sinc(n*duty)*duty*np.sinc(n*f0*tr))
