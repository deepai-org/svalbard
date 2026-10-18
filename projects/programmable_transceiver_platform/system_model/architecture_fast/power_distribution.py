"""Common bonded supply with explicit passive local branches.

No ideal independent domain supplies or isolation multipliers. The generated
SPICE network and nodal equations describe the same lumped R/L/C circuit.
Geometry-dependent impedance, voltage-dependent loads and device safety remain
outside this linear model.
"""
import math
import numpy as np


class CommonRingSupply:
    def __init__(self, network, return_r, return_l, branches, raw_cap_f):
        self.network=dict(network);self.return_r=return_r;self.return_l=return_l
        self.branches={name:dict(values) for name,values in branches.items()}
        self.nodes=['board','raw','die_return',*self.branches]
        if len({name.lower() for name in self.nodes})!=len(self.nodes) or any(name.lower() in ('source','gnd','gnd!','0') for name in self.branches):raise ValueError('Unique nonreserved branch names required')
        if not all(name.isidentifier() for name in self.nodes):raise ValueError('SPICE-safe node names required')
        if not all(math.isfinite(v) and v>0 for v in (return_r,raw_cap_f)) or not math.isfinite(return_l) or return_l<0:
            raise ValueError('Positive finite return resistance/capacitance and nonnegative inductance required')
        for value in self.network.values():
            if not math.isfinite(value) or value<0:raise ValueError('Finite nonnegative passive network required')
        if min(self.network['feed_r'],self.network['package_r'],self.network['board_c'])<=0:
            raise ValueError('Positive feed/package resistance and board capacitance required')
        for values in self.branches.values():
            if set(values)!={'r_ohm','cap_f'} or not all(math.isfinite(v) and v>0 for v in values.values()):
                raise ValueError('Explicit positive branch R and C required')
        self.raw_cap_f=raw_cap_f

    @property
    def capacitance_f(self):return self.raw_cap_f+sum(b['cap_f'] for b in self.branches.values())

    def _elements(self):
        n=self.network
        elements=[('feed','source','board',n['feed_r'],n['feed_l'],0.),
                  ('package','board','raw',n['package_r'],n['package_l'],0.),
                  ('return','die_return','0',self.return_r,self.return_l,0.),
                  ('boardcap','board','0',n['board_esr'],n['board_esl'],n['board_c'])]
        for name,c in [('raw',self.raw_cap_f),*[(name,b['cap_f']) for name,b in self.branches.items()]]:
            # Constant total capacitor plate resistance; partitioning does not
            # invent more total decap conductance. ESL remains an assigned path.
            fraction=c/self.capacitance_f
            elements.append((name+'cap',name,'die_return',n['die_esr']/fraction,n['die_esl'],c))
        elements.extend((name+'feed','raw',name,b['r_ohm'],0.,0.) for name,b in self.branches.items())
        return elements

    def solve(self, frequency_hz, loads, source_v=0., *, return_injection_a=0.):
        if not math.isfinite(frequency_hz) or frequency_hz<0 or not np.isfinite(source_v) or not np.isfinite(return_injection_a):raise ValueError('Finite frequency/source/return injection required')
        if set(loads)-set(self.nodes[1:2]+list(self.branches)):raise ValueError('Loads must draw on the die side of package impedance')
        if not all(np.isfinite(x) for x in loads.values()):raise ValueError('Finite loads required')
        index={name:i for i,name in enumerate(self.nodes)};a=np.zeros((len(index),len(index)),complex);rhs=np.zeros(len(index),complex)
        known={'source':complex(source_v),'0':0j};elements=[];w=2j*np.pi*frequency_hz
        for name,left,right,r,l,c in self._elements():
            if c and frequency_hz==0:continue
            y=1/(r+w*l+(1/(w*c) if c else 0))
            elements.append((left,right,y))
            for node,other in ((left,right),(right,left)):
                if node not in index:continue
                i=index[node];a[i,i]+=y
                if other in index:a[i,index[other]]-=y
                else:rhs[i]+=y*known[other]
        injection=np.zeros(len(index),complex)
        for node,current in loads.items():
            injection[index[node]]-=current;injection[index['die_return']]+=current
        injection[index['die_return']]+=return_injection_a
        rhs+=injection;v=np.linalg.solve(a,rhs);voltages={**known,**dict(zip(self.nodes,v))}
        source_current=sum((voltages['source']-voltages[b])*y for a,b,y in elements if a=='source')
        loss=sum(abs(voltages[a]-voltages[b])**2*y.real for a,b,y in elements)
        load_power=sum(((voltages[name]-voltages['die_return'])*complex(i).conjugate()).real for name,i in loads.items())
        load_power-=(voltages['die_return']*complex(return_injection_a).conjugate()).real
        source_power=(complex(source_v)*source_current.conjugate()).real
        return dict(voltages=voltages,rail_v={name:voltages[name]-voltages['die_return'] for name in ['raw',*self.branches]},
            kcl_residual_a=float(max(abs(a@v-rhs))),power_residual_w=float(source_power-load_power-loss))

    def spice(self, loads, source_v=3.3, ac_load='raw'):
        if ac_load not in ['raw',*self.branches]:raise ValueError('AC load must be on chip')
        if set(loads)-set(['raw',*self.branches]):raise ValueError('DC loads must be on chip')
        lines=['Common ring passive distribution','VSUP source 0 '+str(source_v)]
        for name,left,right,r,l,c in self._elements():
            parts=[('R',r)]+([('L',l)] if l else [])+([('C',c)] if c else [])
            for i,(kind,value) in enumerate(parts):
                end=right if i==len(parts)-1 else name+'_n'+str(i)
                lines.append(f'{kind}{name} {left} {end} {value:.16g}');left=end
        lines += [f'ILOAD_{name} {name} die_return DC {value:.16g}' for name,value in loads.items()]
        lines += [f'IAC {ac_load} die_return DC 0 AC 1']
        return '\n'.join(lines)+'\n'


def from_design(design, *, local_override=None):
    board=design.architecture['blocks']['board']['parameters']
    if board['analog_supply_v']!=board['digital_supply_v']:raise ValueError('Common ring requires one external voltage')
    power=design.architecture['blocks']['power']['parameters'];local=power['local_distribution'] if local_override is None else local_override
    network=dict(power['reduced_pdn_model']['network'],package_l=power['bond_l_h'])
    result=CommonRingSupply(network,power['reduced_pdn_model']['return_r_ohm'],power['shared_return_l_h'],
        local['branches'],local['raw_cap_f'])
    if not math.isclose(result.capacitance_f,power['total_on_die_decoupling_f'],rel_tol=1e-12):
        raise ValueError('Local distribution must conserve the allocated die capacitance')
    return result


def mode_loads(design, mode, *, local_override=None):
    from rf_quality_budget import current_allocation
    allocation=current_allocation(design.architecture,mode,branch='external_rf_clock' if mode.startswith('rf_') else None)
    local=design.architecture['blocks']['power']['parameters']['local_distribution'] if local_override is None else local_override
    branches=local['branches']
    loads={'raw':0.}
    for name,current in allocation['by_rail_ma'].items():
        if name=='external':continue
        owner=name if name in branches else 'raw';loads[owner]=loads.get(owner,0.)+current/1000
    if not math.isclose(sum(loads.values()),allocation['total_ma']/1000,abs_tol=1e-12):
        raise ValueError('Chip current ownership lost in common-ring mapping')
    return loads


def split_rc_experiment():
    """Explicit unadopted equal-capacitance control, not a design default."""
    return dict(raw_cap_f=250e-12,branches={
        'rf':dict(r_ohm=1.,cap_f=250e-12),
        'pll':dict(r_ohm=2.,cap_f=250e-12),
        'conv':dict(r_ohm=2.,cap_f=250e-12)})


def verify_spice(design, work, executable='ngspice'):
    """Independent DC/AC solve of selected circuit and unadopted RC experiment."""
    from pathlib import Path
    import subprocess
    work=Path(work);work.mkdir(parents=True,exist_ok=True);rows=[]
    version=subprocess.run([executable,'--version'],capture_output=True,text=True,check=True,timeout=10).stdout
    for name,override in (('selected',None),('split_rc_experiment',split_rc_experiment())):
        circuit=from_design(design,local_override=override)
        for mode in ('rf_rx','rf_tx','wired','usb'):
            loads=mode_loads(design,mode,local_override=override)
            stem=work/(name+'_'+mode);deck=stem.with_suffix('.cir');op=stem.with_suffix('.op');ac=stem.with_suffix('.ac')
            nodes=['raw',*circuit.branches];vectors=' '.join('v('+node+',die_return)' for node in nodes)
            supply=design.architecture['blocks']['board']['parameters']['analog_supply_v']
            deck.write_text(circuit.spice(loads,source_v=supply)+f'.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\nop\nwrdata {op} {vectors}\nac dec 20 1meg 2.4gig\nwrdata {ac} {vectors}\nquit\n.endc\n.end\n')
            # Remove stale observations: ngspice can exit zero after a control error.
            for path in (op,ac):path.unlink(missing_ok=True)
            run=subprocess.run([executable,'-b',str(deck)],capture_output=True,text=True,timeout=30)
            stem.with_suffix('.log').write_text(run.stdout+run.stderr)
            if run.returncode or not op.exists() or not ac.exists():raise RuntimeError('SPICE analysis failed: '+str(deck))
            actual=np.loadtxt(op,skiprows=1,ndmin=2)[0,1:];dc=circuit.solve(0.,loads,supply)
            dc_error=max(abs(actual[i]-dc['rail_v'][node]) for i,node in enumerate(nodes))
            data=np.loadtxt(ac,skiprows=1,ndmin=2);ac_error=0.
            for row in data:
                expected=circuit.solve(row[0],{'raw':1.})
                for i,node in enumerate(nodes):ac_error=max(ac_error,abs(complex(row[1+2*i],row[2+2*i])-expected['rail_v'][node]))
            if dc_error>1e-9 or ac_error>1e-8:raise AssertionError('SPICE/nodal disagreement')
            rows.append(dict(circuit=name,mode=mode,ac_points=len(data),max_dc_difference_v=float(dc_error),max_ac_difference_ohm=float(ac_error)))
    return dict(simulator_version=version.strip(),cases=rows,
        scope='Linear passive circuits only. Does not verify transistor startup, protection, noise, current dependence or physical RLC.')
