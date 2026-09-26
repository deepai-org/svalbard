"""Linear capacitor charge redistribution with explicit driven/floating nodes.
Branch capacitances are supplied by the caller, not inferred or silicon-qualified.
Ground is represented by None. Optional linear RC recovery holds topology fixed;
switch injection, nonlinear devices and source current limits are not implied.
"""
import numpy as np

class CapacitorNetwork:
    def __init__(self, nodes, branches):
        self.nodes=tuple(nodes)
        nodes=self.nodes
        if len(set(nodes))!=len(nodes) or None in nodes:
            raise ValueError('Node names must be unique and non-ground')
        self.index={n:i for i,n in enumerate(nodes)}
        self.matrix=np.zeros((len(nodes),len(nodes)))
        for a,b,cap in branches:
            if a==b or not np.isfinite(cap) or cap<=0:
                raise ValueError('Each branch needs distinct nodes and positive capacitance')
            vector=np.zeros(len(nodes))
            for node,sign in [(a,1),(b,-1)]:
                if node is not None:vector[self.index[node]]+=sign
            self.matrix+=cap*np.outer(vector,vector)

    def step(self, previous, driven):
        """Conserve charge at floating nodes; return voltages and source charge.

        Source charge is change of node charge, positive into the network.
        A driven node retains none of the previous voltage constraint implicitly.
        """
        return self.redistribute(previous, [], driven)

    def redistribute(self, previous, connections, driven=None, injected_charge=None):
        """Close ideal switches and conserve total charge on each floating group.

        Connections are node pairs tied by zero-resistance switches. The returned
        per-node charge changes include internal transfer; their GROUP sum is the
        external charge. Optional injected_charge maps nodes to supplied coulombs;
        floating groups conserve initial charge plus that injection. Driven groups
        impose voltage and absorb any residual charge. Returned values remain
        total node charge changes, not injection-subtracted source currents.
        Injection is caller-supplied, not a device model. No switch transient.
        """
        driven={} if driven is None else driven
        before=np.asarray([previous[n] for n in self.nodes],dtype=float)
        if not np.all(np.isfinite(before)):
            raise ValueError('Voltages must be finite')
        projection,group=self._groups(connections)
        unique=range(projection.shape[1])
        capacitance=projection.T@self.matrix@projection
        injection=np.zeros(len(self.nodes))
        for n,value in (injected_charge or {}).items():
            if not np.isfinite(value):raise ValueError("Injected charge must be finite")
            injection[self.index[n]]+=value
        charge=projection.T@(self.matrix@before+injection)
        imposed={}
        for n,value in driven.items():
            if not np.isfinite(value):raise ValueError('Voltages must be finite')
            g=group[n]
            if g in imposed and imposed[g]!=value:
                raise ValueError('Conflicting voltage sources on a connected group')
            imposed[g]=value
        fixed=list(imposed)
        floating=[i for i in range(len(unique)) if i not in imposed]
        voltages=np.zeros(len(unique))
        for g,value in imposed.items():voltages[g]=value
        if floating:
            block=capacitance[np.ix_(floating,floating)]
            eigenvalues=np.linalg.eigvalsh(block)
            if eigenvalues[0]<=np.finfo(float).eps*len(floating)*eigenvalues[-1]:
                raise ValueError('Floating network lacks a well-conditioned voltage anchor')
            rhs=charge[floating]-capacitance[np.ix_(floating,fixed)]@voltages[fixed]
            voltages[floating]=np.linalg.solve(block,rhs)
        after=projection@voltages
        delta=self.matrix@(after-before)
        return dict(zip(self.nodes,map(float,after))),dict(zip(self.nodes,map(float,delta)))

    def _groups(self, connections):
        parent=list(range(len(self.nodes)))
        def root(i):
            while parent[i]!=i:
                parent[i]=parent[parent[i]]
                i=parent[i]
            return i
        for a,b in connections:
            parent[root(self.index[a])]=root(self.index[b])
        roots=[root(i) for i in range(len(parent))]
        unique=list(dict.fromkeys(roots))
        group={n:unique.index(roots[i]) for n,i in self.index.items()}
        projection=np.zeros((len(self.nodes),len(unique)))
        for n,i in self.index.items():projection[i,group[n]]=1
        return projection,group

    def relax(self, previous, connections, sources, seconds, driven=None):
        """Exact linear RC evolution with switch topology held fixed.

        sources maps node to (target_voltage, resistance_ohms). No current limit,
        nonlinear buffer, switch resistance, or time-varying driven voltage is
        implied. First applies ideal charge sharing using redistribute().
        """
        from scipy.linalg import expm
        if not np.isfinite(seconds) or seconds<0:
            raise ValueError('Finite nonnegative interval required')
        connections=list(connections)
        driven={} if driven is None else driven
        initial,_=self.redistribute(previous,connections,driven)
        projection,group=self._groups(connections)
        count=projection.shape[1]
        voltage=np.zeros(count)
        for node,value in initial.items():voltage[group[node]]=value
        capacitance=projection.T@self.matrix@projection
        conductance=np.zeros(count);forcing=np.zeros(count)
        for node,(target,resistance) in sources.items():
            if not np.isfinite(target) or not np.isfinite(resistance) or resistance<=0:
                raise ValueError('Finite target and positive resistance required')
            g=group[node];conductance[g]+=1/resistance;forcing[g]+=target/resistance
        fixed={group[n] for n in driven}
        floating=[i for i in range(count) if i not in fixed]
        if floating and seconds:
            c=capacitance[np.ix_(floating,floating)]
            evolution=np.zeros((len(floating)+1,len(floating)+1))
            evolution[:-1,:-1]=-np.linalg.solve(c,np.diag(conductance[floating]))
            evolution[:-1,-1]=np.linalg.solve(c,forcing[floating])
            voltage[floating]=(expm(evolution*seconds)@np.r_[voltage[floating],1])[:-1]
        after=projection@voltage
        return dict(zip(self.nodes,map(float,after)))
