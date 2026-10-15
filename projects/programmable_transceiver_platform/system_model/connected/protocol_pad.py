"""Finite two-node USB/shared-pad circuit and protocol-independent timed fixtures.

Lumped parameters are hypotheses. No transmission-line/package or USB PHY
compliance claim. Local and external source power are accounted separately.
"""
import math
import hashlib
import json
from copy import deepcopy
import numpy as np
from scipy.linalg import expm


class SharedWiredPad:
    def __init__(self,cap_f=2e-12,mutual_f=.2e-12,off_cap_f=.3e-12,
                 *, off_branches_f=None, rail_clamp=None, ground_clamp=None, positive_ground_clamp=None,
                 current_source=None,divider_ground_clamp=None,divider_clamp_cap_f=0.):
        if not all(math.isfinite(x) and x>0 for x in (cap_f,mutual_f,off_cap_f)):
            raise ValueError('Positive pad capacitances')
        # Explicit inactive-branch inventory replaces, never adds to, the
        # legacy aggregate. Each branch has independent P/N capacitances.
        # These are assigned small-signal values, not off-state clamp models.
        if off_branches_f is None:
            self.off_branches_f={'aggregate':(off_cap_f,off_cap_f)}
        else:
            if not off_branches_f:
                raise ValueError('Explicit off-branch inventory cannot be empty')
            self.off_branches_f={}
            for name, pair in off_branches_f.items():
                if (not isinstance(name,str) or not name or len(pair)!=2
                        or any(not math.isfinite(x) or x<0 for x in pair)):
                    raise ValueError('Named finite nonnegative per-leg capacitances required')
                self.off_branches_f[name]=tuple(pair)
        off=np.sum(list(self.off_branches_f.values()),axis=0)
        self.C=np.array([[cap_f+off[0]+mutual_f,-mutual_f],
                         [-mutual_f,cap_f+off[1]+mutual_f]])
        self.invC=np.linalg.inv(self.C);self.voltage=np.zeros(2);self.time=0.
        # Explicit piecewise-linear protection hypotheses: (drop_V, ohms).
        # None means omitted/unqualified, not a demonstrated fail-safe pad.
        for clamp in (rail_clamp,ground_clamp,positive_ground_clamp,divider_ground_clamp):
            if clamp is not None and (len(clamp)!=2 or
                    not all(math.isfinite(x) for x in clamp) or
                    clamp[0]<0 or clamp[1]<=0):
                raise ValueError('Clamp requires nonnegative drop and positive resistance')
        law=dict(reference_supply_v=3.3,reference_pad_v=.4,supply_fraction_per_v=0.,
                 output_resistance_ohm=math.inf,trim=1.)
        if current_source is not None:
            if set(current_source)-set(law):raise ValueError('Unknown current-source parameter')
            law.update(current_source)
        if (any(not math.isfinite(law[k]) for k in law if k!='output_resistance_ohm') or
                law['reference_supply_v']<=0 or law['reference_pad_v']<0 or law['trim']<=0 or
                not law['output_resistance_ohm']>0):
            raise ValueError('Finite current law and positive output resistance required')
        if not math.isfinite(divider_clamp_cap_f) or divider_clamp_cap_f<0:
            raise ValueError('Finite nonnegative internal clamp capacitance required')
        self.divider_ground_clamp=divider_ground_clamp
        self.divider_clamp_cap_f=divider_clamp_cap_f
        self.divider_clamp_charge_c=np.zeros(2)
        self.supply_backfeed_charge_c=0.
        self._construction_context=dict(result_role="independent_pad_fixture")
        self.current_source=law
        self.compliance_headroom_v=.3;self.shunt_leakage_ohm=1e9
        self.rail_clamp=rail_clamp;self.ground_clamp=ground_clamp
        self.positive_ground_clamp=positive_ground_clamp
        self.mode='isolated';self.role='device';self.speed='fs'
        self.local='Z';self.peer='Z';self.attached=False
        self.local_passives=None
        self.peer_passives=None
        self.local_drive=None
        self.peer_supply=3.3;self.hs_current=.4/(1/(1/45+1/45))
        self.peer_hs_current=self.hs_current
        self.hs_termination_ohm=45.;self.pullup_ohm=1500.;self.pulldown_ohm=15000.
        self.fs_output_ohm=30.;self.squelch_v=.1
        self.single_ended_low_v=.3;self.single_ended_high_v=.8
        self.source_energy_j=0.;self.external_energy_j=0.;self.dissipated_j=0.
        self.injection_energy_j=0.
        self.external_sources=None
        self.divider_voltage=np.zeros(2)
        self.divider_cap_f=.1e-12+divider_clamp_cap_f
        self.divider_top_ohm=2000.;self.divider_bottom_ohm=2000.
        self.divider_off_ohm=1e9
        self.serial_differential_termination_ohm=100.

    def _circuit_parameters(self):
        """Circuit constants only; live local/peer controls and charge are separate."""
        names=('C','invC','off_branches_f','current_source','compliance_headroom_v',
               'shunt_leakage_ohm','rail_clamp','ground_clamp','positive_ground_clamp',
               'divider_ground_clamp','divider_clamp_cap_f','hs_current',
               'hs_termination_ohm','pullup_ohm','pulldown_ohm','fs_output_ohm',
               'squelch_v','single_ended_low_v','single_ended_high_v','divider_cap_f',
               'divider_top_ohm','divider_bottom_ohm','divider_off_ohm',
               'serial_differential_termination_ohm')
        def record(value):
            if isinstance(value,np.ndarray):return record(value.tolist())
            if isinstance(value,dict):return {key:record(v) for key,v in value.items()}
            if isinstance(value,(tuple,list)):return [record(v) for v in value]
            # An omitted output conductance is an intentional ideal open circuit.
            if isinstance(value,float) and math.isinf(value):return 'infinity' if value>0 else '-infinity'
            return value
        return {name:record(getattr(self,name)) for name in names}

    def _validate_circuit_parameters(self):
        if self._construction_context.get('result_role')=='shared_architecture_pad':
            if self._circuit_parameters()!=self._construction_parameters:
                raise ValueError('Shared pad circuit parameters changed after construction; use a changed design or explicit construction probe')

    @classmethod
    def from_architecture(cls,architecture,**probe_overrides):
        """Resolve selected loading once; explicit protection probes stay hypotheses."""
        original_overrides=deepcopy(probe_overrides)
        spec=architecture['pad_behavioral_contract']['shared_wired_network']
        cap=spec['base_shunt_cap_f_per_leg'];off=spec['inactive_branch_cap_f_per_leg']
        mutual=spec['mutual_cap_f']
        budget=architecture['blocks']['wirepad']['parameters']['capacitance_f_per_leg']
        if not math.isclose(cap+off+2*mutual,budget,rel_tol=1e-9,abs_tol=1e-24):
            raise ValueError('Wired pad odd-mode capacitance differs from architecture budget')
        if set(probe_overrides)&{'cap_f','off_cap_f','mutual_f','off_branches_f'}:
            raise ValueError('Loading overrides must be explicit architecture changes, not double counted probes')
        sensing=architecture['model_assumptions']['wired_pad_sensing']['parameters']
        if (set(sensing)!={'single_ended_low_v','single_ended_high_v'} or
                any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in sensing.values()) or
                not 0<=sensing['single_ended_low_v']<sensing['single_ended_high_v']):
            raise ValueError('Complete ordered shared pad sensing thresholds required')
        driver=architecture['model_assumptions']['wired_pad_driver']['parameters']
        required={'reference_supply_v','reference_pad_v','supply_fraction_per_v',
                  'output_conductance_s','trim','compliance_headroom_v','shunt_leakage_ohm'}
        if set(driver)!=required:
            raise ValueError('Complete shared wired-pad driver assumptions required')
        for key,value in driver.items():
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
                raise ValueError('Finite wired-pad driver assumptions required')
            if key!='supply_fraction_per_v' and (value<0 or
                    (key not in ('reference_pad_v','output_conductance_s') and value==0)):
                raise ValueError('Invalid wired-pad driver assumption: '+key)
        law={key:driver[key] for key in ('reference_supply_v','reference_pad_v','supply_fraction_per_v','trim')}
        law['output_resistance_ohm']=1/driver['output_conductance_s'] if driver['output_conductance_s'] else math.inf
        overrides=probe_overrides.pop('current_source',None)
        if overrides is not None:
            if set(overrides)-set(law):raise ValueError('Unknown current-source parameter')
            law.update(overrides)
        pad=cls(cap_f=cap,off_cap_f=off,mutual_f=mutual,current_source=law,**probe_overrides)
        pad.compliance_headroom_v=driver['compliance_headroom_v']
        pad.shunt_leakage_ohm=driver['shunt_leakage_ohm']
        pad.single_ended_low_v=sensing['single_ended_low_v']
        pad.single_ended_high_v=sensing['single_ended_high_v']
        for key in ('divider_cap_f_per_leg','divider_top_ohm','divider_bottom_ohm',
                    'divider_off_ohm','serial_differential_termination_ohm'):
            if not math.isfinite(spec[key]) or spec[key]<=0:
                raise ValueError('Finite positive shared-pad network parameters required')
        pad.divider_cap_f=spec['divider_cap_f_per_leg']+pad.divider_clamp_cap_f
        pad.divider_top_ohm=spec['divider_top_ohm'];pad.divider_bottom_ohm=spec['divider_bottom_ohm']
        pad.divider_off_ohm=spec['divider_off_ohm']
        pad.serial_differential_termination_ohm=spec['serial_differential_termination_ohm']
        for attribute,block,key in (
                ('hs_current','usbhs','drive_current_a'),
                ('squelch_v','usbhs','squelch_v'),
                ('hs_termination_ohm','usbhs','termination_ohm_per_leg'),
                ('pullup_ohm','usbfs','pullup_ohm'),
                ('pulldown_ohm','usbfs','pulldown_ohm'),
                ('fs_output_ohm','usbfs','effective_output_r_ohm')):
            value=architecture['blocks'][block]['parameters'][key]
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
                raise ValueError('Finite positive local USB pad parameters required')
            setattr(pad,attribute,value)
        pad._construction_context=dict(result_role='shared_architecture_pad',
            architecture_sha256=hashlib.sha256(json.dumps(architecture,sort_keys=True,
                separators=(',',':'),allow_nan=False).encode()).hexdigest(),
            probe_overrides=original_overrides,
            scope='Construction circuit identity and explicit probes; subsequent controls and state are separate.')
        pad._construction_parameters=pad._circuit_parameters()
        return pad

    def construction_context(self):
        self._validate_circuit_parameters()
        return deepcopy(dict(self._construction_context,circuit_parameters=self._circuit_parameters()))

    def control_context(self):
        """Detached live controls and initial voltages, not a restart checkpoint.

        Explicit passive overrides are mathematical probes; this record does
        not grant arbitrary resistor values as programmable silicon settings.
        None retains the mode's automatic branch selection.
        """
        return deepcopy(dict(
            local=dict(mode=self.mode,role=self.role,speed=self.speed,
                attached=self.attached,drive_state=self.local,
                passive_override=self.local_passives,drive_override=self.local_drive),
            peer=dict(drive_state=self.peer,passive_override=self.peer_passives,
                supply_v=self.peer_supply,hs_current_a=self.peer_hs_current,
                external_sources_v_ohm=self.external_sources),
            initial_state=dict(time_s=self.time,pad_voltage_v=self.voltage.tolist(),
                divider_voltage_v=self.divider_voltage.tolist()),
            scope='Live control observation, not full physical parameter identity or a restart checkpoint; '
                  'passive/drive overrides remain mathematical probes pending hardware mapping'))

    def configure(self,mode,role='device',speed='fs',attached=False):
        if mode not in ('isolated','serial','usb','tmds') or role not in ('host','device') or speed not in ('ls','fs','hs'):
            raise ValueError('Pad profile')
        if self.local!='Z' or self.peer!='Z':raise ValueError('Release both drivers before pad reconfiguration')
        self.mode=mode;self.role=role;self.speed=speed;self.attached=bool(attached)
        self.local_passives=None
        self.local_drive=None

    def transition_mode(self,mode,*,command_delay_s,dead_time_s,rail=3.3,
                        role='device',speed='fs',attached=False,edge_charge_c=None,injection_duration_s=None):
        """Finite local mode-change sequence under an assigned constant rail.

        Existing configuration persists during command latency, then all local
        functional branches are isolated for a positive break-before-make time.
        Explicit board sources and peer passives persist throughout. For active
        peer drive use external_sources, not the mode-dependent legacy USB peer
        shorthand. Optional break/make charge packets use finite constant-current
        pulses on pad P/N and divider P/N; they are explicit hypotheses, not
        inferred transistor channel charge or control skew.
        """
        if (mode not in ('isolated','serial','usb','tmds') or
                role not in ('host','device') or speed not in ('ls','fs','hs')):
            raise ValueError('Pad profile')
        if (not all(math.isfinite(v) for v in (command_delay_s,dead_time_s,rail)) or
                command_delay_s<0 or dead_time_s<=0 or rail<0):
            raise ValueError('Nonnegative latency/rail and positive dead time required')
        if self.peer!='Z':
            raise ValueError('Use independent external sources for peer drive across mode changes')
        charge=None if edge_charge_c is None else np.asarray(edge_charge_c,float)
        if charge is not None and (charge.shape!=(2,4) or not np.all(np.isfinite(charge)) or
                injection_duration_s is None or not math.isfinite(injection_duration_s) or
                not 0<injection_duration_s<=dead_time_s):
            raise ValueError('Two finite four-node charge packets and positive pulse duration within dead time required')
        def inject(index):
            if charge is None:return None
            return self.advance_network(self.time+injection_duration_s,rail,
                injected_current_a=charge[index]/injection_duration_s,max_step_s=injection_duration_s/16)
        start=self.time
        self.advance_network(start+command_delay_s,rail)
        self.local='Z';self.local_drive=None
        self.configure('isolated')
        break_pulse=inject(0)
        broken=dict(time_s=self.time,voltage_v=self.voltage.tolist(),
                    divider_voltage_v=self.divider_voltage.tolist())
        self.advance_network(start+command_delay_s+dead_time_s,rail)
        self.configure(mode,role=role,speed=speed,attached=attached)
        make_time=self.time;make_pulse=inject(1)
        return dict(command_time_s=start,break_time_s=start+command_delay_s,make_time_s=make_time,
                    break_state=broken,charge_packets_c=None if charge is None else charge.tolist(),
                    injection_duration_s=injection_duration_s,break_pulse=break_pulse,make_pulse=make_pulse,
                    make_state=dict(time_s=self.time,voltage_v=self.voltage.tolist(),
                                    divider_voltage_v=self.divider_voltage.tolist()),
                    mode=mode,scope='Finite command delay and isolation interval; atomic switch edges, '
                    'optional finite assigned charge pulses, no transistor switch-slew or control-skew model. '
                    'Pulse voltage extrema are solver-sampled, not continuous-time stress guarantees. Output drive remains released after make.')

    def set_external_sources(self, sources):
        """Board/peer Thevenin sources (volts, ohms) on P/N, or None per leg.

        Retained across local mode changes, reset and zero local supply. These
        are fixture stimuli, not chip controls. Explicit sources replace the
        serial fixture's implicit peer common-mode termination.
        """
        if len(sources)!=2:
            raise ValueError('Two external leg sources required')
        for item in sources:
            if item is not None and (len(item)!=2 or
                    not all(math.isfinite(v) for v in item) or item[1]<=0):
                raise ValueError('Finite external voltage and positive resistance required')
        self.external_sources=tuple(None if x is None else tuple(x) for x in sources)

    def set_local_passives(self,*,pull_up_ohm=(None,None),
                           pull_down_ohm=(None,None),termination_ohm=(None,None)):
        """Atomic mathematical apply of independent local passive branches.

        Tuple order is P,N; None disconnects a branch. Pull-ups use the local
        rail; pull-downs and terminations use local return. Remote drive and
        passives are unchanged. No switch injection, latency or ABI is implied.
        """
        if self.mode!='usb':raise ValueError('Local bidirectional branch must own pads')
        candidate={}
        for name,values in (('up',pull_up_ohm),('down',pull_down_ohm),('term',termination_ohm)):
            if len(values)!=2 or any(v is not None and
                    (not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0) for v in values):
                raise ValueError('Two positive finite resistances or disconnected branches required')
            candidate[name]=tuple(values)
        self.local_passives=candidate

    def set_peer_passives(self,*,pull_up_ohm=(None,None),
                          pull_down_ohm=(None,None),termination_ohm=(None,None)):
        """Explicit remote branches, retained across local reconfiguration.

        This fixture control belongs to the peer, never the chip ABI. None on
        every leg means electrically disconnected, not automatic speed matching.
        """
        candidate={}
        for name,values in (('up',pull_up_ohm),('down',pull_down_ohm),('term',termination_ohm)):
            if len(values)!=2 or any(v is not None and
                    (not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0) for v in values):
                raise ValueError('Two positive finite peer resistances or disconnected branches required')
            candidate[name]=tuple(values)
        self.peer_passives=candidate

    def set_local_drive(self,style,*,node=0,levels=(0,0),current_a=None,resistance_ohm=None):
        """Independent local drive hypothesis; numeric states, no negotiation FSM.

        A bounded current source may operate against a remote voltage driver.
        Two active voltage drivers remain rejected. Levels are rail fractions
        restricted to 0/1; current steering selects the physical P/N leg.
        """
        if current_a is None:current_a=self.hs_current
        if resistance_ohm is None:resistance_ohm=self.fs_output_ohm
        if self.mode!='usb' or style not in ('off','voltage','current'):
            raise ValueError('Bidirectional pad ownership and supported drive style required')
        if node not in (0,1) or len(levels)!=2 or any(v not in (0,1) for v in levels):
            raise ValueError('Physical leg and binary voltage levels required')
        if not all(math.isfinite(v) and v>0 for v in (current_a,resistance_ohm)):
            raise ValueError('Positive finite current and resistance required')
        if style=='voltage' and self.peer!='Z':raise ValueError('Competing voltage drive is not a supported state')
        self.local_drive=dict(style=style,node=node,levels=tuple(levels),current_a=current_a,resistance_ohm=resistance_ohm)
        self.local='Z'

    def sense(self,*,low_v=None,high_v=None,squelch_v=None):
        """Raw ideal comparators, independent of speed; no delay or hysteresis."""
        if low_v is None:low_v=self.single_ended_low_v
        if high_v is None:high_v=self.single_ended_high_v
        if squelch_v is None:squelch_v=self.squelch_v
        if not all(math.isfinite(v) for v in (low_v,high_v,squelch_v)) or not 0<=low_v<high_v or squelch_v<0:
            raise ValueError('Ordered finite sensing thresholds required')
        return dict(single_ended_low=tuple(bool(v<low_v) for v in self.voltage),
            single_ended_high=tuple(bool(v>high_v) for v in self.voltage),
            differential_positive=bool(self.voltage[0]>self.voltage[1]),
            squelch=bool(abs(self.voltage[0]-self.voltage[1])<squelch_v),timestamp_s=self.time)

    def drive(self,local='Z',peer='Z'):
        if local not in ('Z','J','K','SE0') or peer not in ('Z','J','K','SE0'):
            raise ValueError('Line state')
        if self.mode!='usb' and (local!='Z' or peer!='Z'):raise ValueError('USB branch is isolated')
        if self.local_drive is not None:
            if local!='Z':raise ValueError('Use numeric local drive while override is active')
            if peer!='Z' and self.local_drive['style']=='voltage':raise ValueError('Competing voltage drive is not supported')
        if local!='Z' and peer!='Z':raise ValueError('USB bus contention')
        if self.speed=='hs' and (local=='SE0' or peer=='SE0'):
            raise ValueError('HS zero state is driver release, not FS push-pull SE0')
        self.local=local;self.peer=peer

    def local_current(self,nominal_a,pad_v,rail_v):
        """Assigned finite output resistance and reference supply sensitivity.

        Local driver only; external peer does not inherit chip imperfections.
        Parameters are hypotheses, not transistor characterization or PSRR data.
        """
        law=self.current_source
        demand=nominal_a*law['trim']*(1+law['supply_fraction_per_v']*(rail_v-law['reference_supply_v']))
        demand-=(pad_v-law['reference_pad_v'])/law['output_resistance_ohm']
        return max(0.,demand)*max(0.,min(1.,(rail_v-pad_v)/self.compliance_headroom_v))

    def electrical(self,voltage,rail,*,_network_evaluation=False):
        """Return dV/dt, local supply current, external power, dissipated power."""
        if self.mode=='tmds' and not _network_evaluation:
            raise ValueError('TMDS requires the connected divider-state network')
        v=np.asarray(voltage);current=np.zeros(2);supply=0.;external=0.;loss=0.
        def resistor(node,target,r,owner):
            nonlocal supply,external,loss
            i=(target-v[node])/r;current[node]+=i;loss+=i*i*r
            if owner=='local':supply+=i
            elif owner=='peer':external+=target*i
        for n in range(2):resistor(n,0.,self.shunt_leakage_ohm,'ground')
        # Protection remains connected even with every functional branch off.
        # Upper clamp current is negative supply draw: it back-powers the rail.
        for n in range(2):
            if self.rail_clamp is not None:
                drop,r=self.rail_clamp
                i=max(0.,(v[n]-rail-drop)/r)
                current[n]-=i;supply-=i;loss+=(v[n]-rail)*i
            if self.positive_ground_clamp is not None:
                # Assigned rail-independent shunt characteristic, not a
                # validated avalanche/SCR/ESD structure. Dissipation goes to
                # the ground-referenced protection device, never the rail.
                threshold,r=self.positive_ground_clamp
                i=max(0.,(v[n]-threshold)/r)
                current[n]-=i;loss+=v[n]*i
            if self.ground_clamp is not None:
                drop,r=self.ground_clamp
                i=max(0.,(-v[n]-drop)/r)
                current[n]+=i;loss+=-v[n]*i
        if self.external_sources is not None:
            for n,item in enumerate(self.external_sources):
                if item is not None:resistor(n,item[0],item[1],'peer')
        if self.peer_passives is not None:
            for n in range(2):
                for branch,target,owner in (('up',self.peer_supply,'peer'),('down',0.,'ground'),('term',0.,'ground')):
                    resistance=self.peer_passives[branch][n]
                    if resistance is not None:resistor(n,target,resistance,owner)
        if self.mode=='serial' and self.external_sources is None:
            # Isolated USB branch contributes C_off; serial CM comes from peer fixture.
            for n in range(2):resistor(n,.8,50.,'peer')
        if self.mode=='serial':
            r=self.serial_differential_termination_ohm
            if not math.isfinite(r) or r<=0:raise ValueError('Positive serial termination required')
            i=(v[0]-v[1])/r
            current[0]-=i;current[1]+=i;loss+=i*i*r
        if self.mode=='usb':
            if self.speed=='hs':
                for n in range(2):
                    if self.local_passives is None:resistor(n,0.,self.hs_termination_ohm,'ground')
                    if self.attached and self.peer_passives is None:resistor(n,0.,45.,'ground')
            else:
                # Host pull-downs; a connected device advertises FS on D+ or LS on D-.
                for n in range(2):
                    if ((self.role=='host' and self.local_passives is None) or
                            (self.role=='device' and self.attached and self.peer_passives is None)):resistor(n,0.,self.pulldown_ohm if self.role=='host' else 15000.,'ground')
                if ((self.role=='device' and self.local_passives is None) or
                        (self.role=='host' and self.attached and self.peer_passives is None)):
                    local_device=self.role=='device'
                    resistor(1 if self.speed=='ls' else 0,rail if local_device else self.peer_supply,self.pullup_ohm if local_device else 1500.,'local' if local_device else 'peer')
            if self.local_passives is not None:
                for n in range(2):
                    for branch,target,owner in (('up',rail,'local'),('down',0.,'ground'),('term',0.,'ground')):
                        resistance=self.local_passives[branch][n]
                        if resistance is not None:resistor(n,target,resistance,owner)
            if self.local_drive is not None:
                d=self.local_drive
                if d['style']=='current':
                    node=d['node'];i=self.local_current(d['current_a'],v[node],rail)
                    current[node]+=i;supply+=i;loss+=(rail-v[node])*i
                elif d['style']=='voltage':
                    for n in range(2):
                        target=rail*d['levels'][n]
                        resistor(n,target,d['resistance_ohm'],'local' if target else 'ground')
            for state,owner,source in ((self.local,'local',rail),(self.peer,'peer',self.peer_supply)):
                if state=='Z':continue
                jnode=1 if self.speed=='ls' else 0
                high=jnode if state=='J' else 1-jnode
                if self.speed=='hs':
                    # Current source loses compliance above its supply, rather than infinite drive.
                    i=(self.local_current(self.hs_current,v[high],source) if owner=='local' else
                       self.peer_hs_current*max(0.,min(1.,(source-v[high])/.3)))
                    current[high]+=i;loss+=(source-v[high])*i
                    if owner=='local':supply+=i
                    else:external+=source*i
                else:
                    for n in range(2):resistor(n,source if n==high and state!='SE0' else 0.,self.fs_output_ohm if owner=='local' else 30.,owner if n==high and state!='SE0' else 'ground')
        return self.invC@current,supply,external,loss

    def internal_clamp_current(self,internal):
        """Ground-to-divider current; no ideal clipping or supply-rail shortcut."""
        internal=np.asarray(internal,float)
        if internal.shape!=(2,) or not np.all(np.isfinite(internal)):
            raise ValueError('Finite divider-node pair required')
        if self.divider_ground_clamp is None:return np.zeros(2)
        drop,resistance=self.divider_ground_clamp
        return np.maximum(0.,-internal-drop)/resistance

    def electrical_network(self,state,rail):
        """Connected pad pair plus finite TMDS divider-node capacitances.

        The disabled divider retains off resistance and stored charge. Existing
        pad capacitance includes separately budgeted off-switch drain loading.
        Primary protection is still an assigned hypothesis, not a PDK device.
        """
        state=np.asarray(state,float)
        if state.shape!=(4,) or not np.all(np.isfinite(state)) or not math.isfinite(rail) or rail<0:
            raise ValueError('Finite four-node state and nonnegative rail required')
        if not all(math.isfinite(v) and v>0 for v in
                   (self.divider_cap_f,self.divider_top_ohm,self.divider_bottom_ohm,self.divider_off_ohm)):
            raise ValueError('Positive finite divider elements required')
        v=state[:2];internal=state[2:]
        dv,supply,external,loss=self.electrical(v,rail,_network_evaluation=True)
        top=self.divider_top_ohm if self.mode=='tmds' else self.divider_off_ohm
        branch=(v-internal)/top
        bottom=internal/self.divider_bottom_ohm
        dv-=self.invC@branch
        clamp=self.internal_clamp_current(internal)
        dint=(branch-bottom+clamp)/self.divider_cap_f
        loss-=float(internal@clamp)
        loss+=float(np.sum(branch**2*top+bottom**2*self.divider_bottom_ohm))
        return np.r_[dv,dint],supply,external,loss

    def advance_network(self,time,rail=3.3,*,max_step_s=None,injected_current_a=None):
        """Nonlinear retained-state evolution with board drive and protection.

        Rail may be constant or a continuous callable of absolute time. A callable
        requires an explicit integration step bound; split discontinuities at
        call boundaries. No instantaneous capacitor reset accompanies events.
        Optional constant four-node injected current also needs a step bound.
        Its signed voltage-times-current work is recorded in injection_energy_j,
        separately from chip and board supply work. Returned extrema sample the
        solver trajectory; they are not continuous-time stress bounds.
        """
        self._validate_circuit_parameters()
        from scipy.integrate import solve_ivp
        dynamic=callable(rail)
        if not math.isfinite(time) or time<self.time:
            raise ValueError('Finite monotonic time required')
        if (dynamic or injected_current_a is not None or max_step_s is not None) and (
                max_step_s is None or not math.isfinite(max_step_s) or max_step_s<=0):
            raise ValueError('Dynamic rail or injected current requires a positive finite integration step bound')
        injection=np.zeros(4) if injected_current_a is None else np.asarray(injected_current_a,float)
        if injection.shape!=(4,) or not np.all(np.isfinite(injection)):
            raise ValueError('Finite four-node injection current required')
        def rail_at(t):
            value=float(rail(t) if dynamic else rail)
            if not math.isfinite(value) or value<0:raise ValueError('Finite nonnegative rail required')
            return value
        rail_at(self.time);rail_at(time)
        if time==self.time:return
        initial=np.r_[self.voltage,self.divider_voltage,
                      self.source_energy_j,self.external_energy_j,self.dissipated_j,self.injection_energy_j,self.divider_clamp_charge_c,self.supply_backfeed_charge_c]
        def rhs(t,state):
            voltage=rail_at(t)
            dv,supply,external,loss=self.electrical_network(state[:4],voltage)
            dv+=np.r_[self.invC@injection[:2],injection[2:]/self.divider_cap_f]
            return np.r_[dv,voltage*supply,external,loss,float(state[:4]@injection),self.internal_clamp_current(state[2:4]),max(0.,-supply)]
        result=solve_ivp(rhs,(self.time,time),initial,method='Radau',rtol=1e-8,
                         atol=np.r_[np.full(4,1e-10),np.full(4,1e-21),np.full(3,1e-24)],
                         max_step=max_step_s if max_step_s is not None else np.inf)
        if not result.success:raise ValueError('Pad network integration failed')
        final=result.y[:,-1]
        self.voltage=final[:2];self.divider_voltage=final[2:4]
        self.source_energy_j,self.external_energy_j,self.dissipated_j,self.injection_energy_j=final[4:8]
        self.divider_clamp_charge_c=final[8:10]
        self.supply_backfeed_charge_c=float(final[10])
        supplies=[self.electrical_network(result.y[:4,i],rail_at(t))[1] for i,t in enumerate(result.t)]
        start=self.time;self.time=time
        return dict(supply_backfeed_charge_c=float(final[10]-initial[10]),
            sampled_peak_backfeed_a=max(0.,-min(supplies)),start_s=start,end_s=time,injected_charge_c=(injection*(time-start)).tolist(),
            sampled_node_min_v=np.min(result.y[:4],axis=1).tolist(),
            sampled_node_max_v=np.max(result.y[:4],axis=1).tolist(),sampled_points=len(result.t))

    def network_energy(self):
        return self.energy()+.5*self.divider_cap_f*float(self.divider_voltage@self.divider_voltage)

    def small_signal_transfer(self,frequency_hz,rail):
        """Differential response around retained bias, from explicit board sources.

        Includes off-branch C, finite divider and local termination. This is a
        local linearization; it does not establish large-signal eye or ESD.
        """
        self._validate_circuit_parameters()
        if (not math.isfinite(frequency_hz) or frequency_hz<0 or
                self.external_sources is None or any(x is None for x in self.external_sources)):
            raise ValueError('Nonnegative frequency and both board sources required')
        state=np.r_[self.voltage,self.divider_voltage]
        step=1e-6
        jac=np.column_stack([(self.electrical_network(state+np.eye(4)[k]*step,rail)[0]-
                              self.electrical_network(state-np.eye(4)[k]*step,rail)[0])/(2*step)
                             for k in range(4)])
        drive=np.r_[self.invC@np.array([.5/self.external_sources[0][1],
                                       -.5/self.external_sources[1][1]]),0.,0.]
        nodes=np.linalg.solve(2j*math.pi*frequency_hz*np.eye(4)-jac,drive)
        return dict(pad_differential=complex(nodes[0]-nodes[1]),
                    divider_differential=complex(nodes[2]-nodes[3]))

    def energy(self):return .5*float(self.voltage@self.C@self.voltage)

    def observe(self):
        p,n=self.voltage
        return dict(dp_v=float(p),dm_v=float(n),differential_v=float(p-n),
                    squelch=abs(p-n)<self.squelch_v,se0=max(p,n)<self.single_ended_low_v,
                    j=bool((n>p) if self.speed=='ls' else (p>n)))

    def advance(self,time,rail=3.3):
        """Standalone exact affine step, used to check the coupled ODE primitive."""
        self._validate_circuit_parameters()
        if any(clamp is not None for clamp in (self.rail_clamp,self.ground_clamp,self.positive_ground_clamp)):
            raise ValueError('Use coupled nonlinear solver with protection clamps')
        if not math.isfinite(time) or time<self.time or not rail>0:raise ValueError('Pad time/rail')
        dt=time-self.time
        if dt==0:return
        # Remains in the HS current-source compliance region for valid USB levels.
        b=self.electrical(np.zeros(2),rail)[0]
        a=np.column_stack([self.electrical(np.eye(2)[i]*.01,rail)[0]-b for i in range(2)])/.01
        aug=np.zeros((3,3));aug[:2,:2]=a;aug[:2,2]=b
        out=(expm(aug*dt)@np.r_[self.voltage,1])[:2]
        current_legs=[]
        if self.local_drive is not None and self.local_drive['style']=='current':
            current_legs.append((self.local_drive['node'],rail))
        if self.speed=='hs' and self.mode=='usb':
            for state,source in ((self.local,rail),(self.peer,self.peer_supply)):
                if state!='Z':current_legs.append((0 if state=='J' else 1,source))
        if any(max(out[node],self.voltage[node])>source-.3 for node,source in current_legs):
            raise ValueError('Use coupled nonlinear solver outside current-source compliance')
        self.voltage=out;self.time=time


def usb_nrzi(bits):
    level=1;ones=0;out=[]
    for bit in bits:
        if bit not in (0,1):raise ValueError('Binary USB data')
        if bit==0:level^=1
        out.append(level);ones=ones+1 if bit else 0
        if ones==6:level^=1;out.append(level);ones=0
    return out


def usb_decode(levels):
    previous=1;ones=0;out=[]
    for level in levels:
        if level not in (0,1):raise ValueError('Binary line levels')
        bit=int(level==previous);previous=level
        if ones==6:
            if bit:raise ValueError('USB bit stuffing violation')
            ones=0;continue
        out.append(bit);ones=ones+1 if bit else 0
    if ones==6:raise ValueError('Missing stuffed bit')
    return out


def usb_crc16(data):
    """External FPGA fixture CRC-16/USB; never a chip primitive."""
    crc=0xffff
    for byte in bytes(data):
        crc^=byte
        for _ in range(8):crc=(crc>>1)^(0xa001 if crc&1 else 0)
    return crc^0xffff


def usb_hs_packet(pid,payload=b''):
    """External direct-link DATA0/DATA1/ACK fixture, full SYNC and no hub dribble.

    USB 2.0 sections 7.1.10, 7.1.13.2 and 8: body is stuffed, EOP is not.
    This helper does not implement token/address/endpoint transaction state.
    """
    if pid not in (0xc3,0x4b,0xd2):raise ValueError('Unsupported fixture PID')
    payload=bytes(payload)
    if pid==0xd2 and payload:raise ValueError('ACK has no payload')
    body=bytes([pid])+payload
    if pid!=0xd2:body+=usb_crc16(payload).to_bytes(2,'little')
    bits=[0]*31+[1]+[(byte>>n)&1 for byte in body for n in range(8)]
    levels=usb_nrzi(bits)
    # EOP begins with a transition, then seven unstuffed ones.
    levels.extend([1-levels[-1]]*8)
    return levels


def usb_hs_decode_packet(levels):
    """External receiver validates observed framing/PID/CRC, without payload truth."""
    levels=list(levels)
    if len(levels)<48 or any(type(x) is not int or x not in (0,1) for x in levels):
        raise ValueError('Invalid HS packet levels')
    previous=1;raw=[]
    for level in levels:raw.append(int(level==previous));previous=level
    if raw[:32]!=[0]*31+[1]:raise ValueError('HS SYNC')
    if raw[-8:]!=[0]+[1]*7:raise ValueError('HS EOP')
    bits=usb_decode(levels[:-8])[32:]
    if len(bits)%8:raise ValueError('Partial packet byte')
    body=bytes(sum(bits[k+n]<<n for n in range(8)) for k in range(0,len(bits),8))
    pid=body[0]
    if ((pid>>4)^(pid&15))!=15:raise ValueError('PID complement')
    if pid==0xd2:
        if len(body)!=1:raise ValueError('ACK length')
        return pid,b''
    if pid not in (0xc3,0x4b) or len(body)<3:raise ValueError('Unsupported data packet')
    payload=body[1:-2]
    if int.from_bytes(body[-2:],'little')!=usb_crc16(payload):raise ValueError('USB CRC16')
    return pid,payload



class USBStreamingPacket:
    """External FPGA parser reference; finite storage, no chip protocol logic.

    Eight raw levels are held back for unstuffed EOP. Two body bytes are held
    back for CRC. Payload is retained until validation, bounded by max_payload.
    feed() implements ordered bit updates; a parallel implementation must
    realize these dependencies within its declared processing-cycle budget.
    """
    def __init__(self,max_payload=1024):
        if type(max_payload) is not int or max_payload<0:raise ValueError('Payload capacity')
        self.max_payload=max_payload;self.tail=[];self.previous=1;self.raw_count=0
        self.ones=0;self.byte=0;self.byte_bits=0;self.pid=None
        self.crc=0xffff;self.crc_tail=[];self.payload=bytearray();self.fault=None
        self.finished=False

    def feed(self,levels):
        if self.finished:raise ValueError('Packet already finalized')
        for level in levels:
            if self.fault:continue
            try:
                if type(level) is not int or level not in (0,1):raise ValueError('Invalid HS packet levels')
                self.tail.append(level)
                if len(self.tail)<=8:continue
                value=self.tail.pop(0);bit=int(value==self.previous);self.previous=value
                self.raw_count+=1
                if self.raw_count<=32:
                    if bit!=int(self.raw_count==32):raise ValueError('HS SYNC')
                    self.ones=bit
                    continue
                if self.ones==6:
                    if bit:raise ValueError('USB bit stuffing violation')
                    self.ones=0;continue
                self.ones=self.ones+1 if bit else 0
                self.byte|=bit<<self.byte_bits;self.byte_bits+=1
                if self.byte_bits!=8:continue
                value=self.byte;self.byte=0;self.byte_bits=0
                if self.pid is None:
                    if ((value>>4)^(value&15))!=15:raise ValueError('PID complement')
                    if value not in (0xc3,0x4b,0xd2):raise ValueError('Unsupported data packet')
                    self.pid=value
                else:
                    if self.pid==0xd2:raise ValueError('ACK length')
                    self.crc_tail.append(value)
                    if len(self.crc_tail)>2:
                        byte=self.crc_tail.pop(0)
                        if len(self.payload)>=self.max_payload:raise ValueError('Payload capacity exceeded')
                        self.payload.append(byte);self.crc^=byte
                        for _ in range(8):self.crc=(self.crc>>1)^(0xa001 if self.crc&1 else 0)
            except ValueError as error:self.fault=str(error)

    def finish(self):
        if self.finished:raise ValueError('Packet already finalized')
        self.finished=True
        if self.fault:raise ValueError(self.fault)
        if self.raw_count<40 or len(self.tail)!=8:raise ValueError('Invalid HS packet levels')
        previous=self.previous;raw=[]
        for level in self.tail:raw.append(int(level==previous));previous=level
        if raw!=[0]+[1]*7:raise ValueError('HS EOP')
        if self.ones==6:raise ValueError('Missing stuffed bit')
        if self.byte_bits:raise ValueError('Partial packet byte')
        if self.pid!=0xd2:
            if len(self.crc_tail)!=2:raise ValueError('Unsupported data packet')
            if int.from_bytes(bytes(self.crc_tail),'little')!=self.crc^0xffff:raise ValueError('USB CRC16')
        return self.pid,bytes(self.payload)


def sata_oob(kind):
    if kind not in ('reset','init','wake'):raise ValueError('SATA OOB kind')
    burst=160/1.5e9;gap=(160 if kind=='wake' else 480)/1.5e9
    return [(i*(burst+gap),i*(burst+gap)+burst) for i in range(6)]


def detect_oob(intervals,tolerance=.15):
    """Envelope-only detector: reset/init electrically identical; no CDR oracle."""
    if not 0<tolerance<.5:raise ValueError('OOB tolerance')
    if len(intervals)<4:return None
    widths=[b-a for a,b in intervals]
    gaps=[intervals[i+1][0]-intervals[i][1] for i in range(len(intervals)-1)]
    near=lambda vals,nominal:all(abs(v/nominal-1)<=tolerance for v in vals)
    if not near(widths,160/1.5e9):return None
    if near(gaps,160/1.5e9):return 'wake'
    if near(gaps,480/1.5e9):return 'reset_or_init'
    return None


def response_budget(*,word_hz,rx_words,tx_words,fpga_s,turnaround_s,deadline_s,
                    phase_words=1,queue_words=0,framed=False):
    vals=(word_hz,rx_words,tx_words,fpga_s,turnaround_s,deadline_s,phase_words,queue_words)
    if not all(math.isfinite(v) for v in vals) or word_hz<=0 or deadline_s<=0 or any(v<0 for v in vals[1:]):
        raise ValueError('Response envelope')
    # Each direction can just miss its service point; old framed path also waits a frame.
    transport=(rx_words+tx_words+2*phase_words+queue_words+(128 if framed else 0))/word_hz
    elapsed=transport+fpga_s+turnaround_s
    return dict(elapsed_s=elapsed,margin_s=deadline_s-elapsed,met=elapsed<=deadline_s)


def usb_framed_turnaround(frame_words=8,word_hz=250e6,fpga_s=40e-9,
                          analog_s=34e-9,cdc_words=4,queue_words=4,packing_bits=20,
                          h2d_commit_words=0,h2d_cdc_hz=None):
    """Conservative round-trip bound for the existing two-bank frame snapshots.

    Each direction: <1 frame to snapshot, one frame until emission, <=1 frame
    to deliver the last word. USB-IF EL_22 requires 8..192 HS bit times for
    ordinary host/device responses, measured at the relevant port boundaries.
    No built-in-hub or cable allowance is consumed by this local chip/FPGA budget.
    """
    values=(word_hz,fpga_s,analog_s,cdc_words,queue_words,packing_bits,h2d_commit_words)
    if frame_words not in (8,64) or not all(math.isfinite(v) for v in values) or word_hz<=0 or any(v<0 for v in values[1:]):
        raise ValueError('USB framed timing envelope')
    if h2d_cdc_hz is not None and (not math.isfinite(h2d_cdc_hz) or h2d_cdc_hz<=0):
        raise ValueError('Positive destination CDC clock required')
    worst=(6*frame_words+cdc_words+queue_words)/word_hz+fpga_s+analog_s+packing_bits/480e6
    # Replace the old combined CDC placeholder with H2D visibility only.
    # D2H crossing is deliberately still unbudgeted in this comparison.
    extra_cdc=0. if h2d_cdc_hz is None else 3/h2d_cdc_hz-cdc_words/word_hz
    worst+=h2d_commit_words/word_hz+extra_cdc
    earliest=fpga_s+analog_s
    minimum=8/480e6;maximum=192/480e6
    return dict(frame_words=frame_words,word_hz=word_hz,
                raw_payload_capacity_bps=(frame_words-5)*10*word_hz/frame_words,
                earliest_s=earliest,worst_s=worst,minimum_s=minimum,maximum_s=maximum,
                minimum_guard_s=max(0.,minimum-earliest),margin_s=maximum-max(worst,minimum),
                meets_bound=max(worst,minimum)<=maximum,
                assumptions=dict(fpga_s=fpga_s,analog_s=analog_s,cdc_words=cdc_words,
                                 queue_words=queue_words,packing_bits=packing_bits,
                                 h2d_commit_words=h2d_commit_words,h2d_cdc_hz=h2d_cdc_hz,
                                 h2d_visibility_s=None if h2d_cdc_hz is None else 3/h2d_cdc_hz,
                                 cdc_scope='legacy combined word allowance' if h2d_cdc_hz is None else 'H2D only; D2H crossing and physical margins missing'))


class BurstEnvelopeReceiver:
    """Generic first-order envelope, hysteretic comparator and timed burst counter.

    Input is a rectified envelope voltage, not decoded burst timestamps. Detector
    windows are supplied by the profile. This reduction has ideal comparator
    thresholds and a frozen supply; RF rectification, package and clock error
    need qualification. Emits completed patterns only after observed inactivity.
    """
    def __init__(self,patterns,*,tau_s=10e-9,on_v=.12,off_v=.08,min_bursts=4):
        if (not all(math.isfinite(v) and v>0 for v in (tau_s,on_v,off_v)) or
                off_v>=on_v or not isinstance(min_bursts,int) or min_bursts<2):
            raise ValueError('Envelope detector parameters')
        self.patterns=dict(patterns)
        for widths,gaps,release in self.patterns.values():
            if (not all(math.isfinite(v) and v>0 for v in (*widths,*gaps,release)) or
                    not widths[0]<widths[1] or not gaps[0]<gaps[1] or release<=gaps[1]):
                raise ValueError('Burst timing windows')
        if not self.patterns:raise ValueError('At least one pattern required')
        self.tau=tau_s;self.on=on_v;self.off=off_v;self.minimum=min_bursts
        self.time=0.;self.voltage=0.;self.target=0.;self.active=False
        self.rise=None;self.fall=None;self.candidates=set();self.count=0;self.events=[]

    def _edge(self,active,time):
        if active:
            if self.fall is not None:
                gap=time-self.fall
                self.candidates={k for k in self.candidates
                    if self.patterns[k][1][0]<=gap<=self.patterns[k][1][1]}
            if not self.candidates:
                self.candidates=set(self.patterns);self.count=0
            self.rise=time
        else:
            width=time-self.rise
            self.candidates={k for k in self.candidates
                if self.patterns[k][0][0]<=width<=self.patterns[k][0][1]}
            self.count=self.count+1 if self.candidates else 0
            self.fall=time
        self.active=active

    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Monotonic finite detector time')
        threshold=self.off if self.active else self.on
        crossing=None
        if ((self.active and self.target<threshold<self.voltage) or
                (not self.active and self.voltage<threshold<self.target)):
            crossing=self.time-self.tau*math.log((threshold-self.target)/(self.voltage-self.target))
        self._release(min(time,crossing) if crossing is not None else time)
        if crossing is not None and crossing<=time:self._edge(not self.active,crossing)
        self.voltage=self.target+(self.voltage-self.target)*math.exp(-(time-self.time)/self.tau)
        self.time=time
        self._release(time)
        return list(self.events)

    def _release(self,time):
        if not self.active and self.fall is not None and self.count>=self.minimum:
            completed=[k for k in self.candidates if time>=self.fall+self.patterns[k][2]]
            if len(completed)==1:
                key=completed[0]
                self.events.append(dict(kind=key,time_s=self.fall+self.patterns[key][2],bursts=self.count))
                self.candidates=set();self.count=0;self.fall=None

    def drive(self,voltage,time):
        if not math.isfinite(voltage) or voltage<0:raise ValueError('Nonnegative finite envelope')
        self.advance(time);self.target=voltage

    @property
    def next_event(self):
        threshold=self.off if self.active else self.on
        crossing=math.inf
        if ((self.active and self.target<threshold<self.voltage) or
                (not self.active and self.voltage<threshold<self.target)):
            crossing=self.time-self.tau*math.log((threshold-self.target)/(self.voltage-self.target))
        release=math.inf
        if not self.active and self.fall is not None and self.count>=self.minimum:
            release=min((self.fall+self.patterns[k][2] for k in self.candidates),default=math.inf)
        return min(crossing,release)


def sata_envelope_receiver(**kwargs):
    """Candidate interior windows, not complete SATA detector acceptance limits.

    Quiet-release delays follow SATA 1.0 section 6.7.4. Burst/gap +/-15%
    windows retain the earlier fixture's candidate hypothesis for comparison.
    """
    burst=160/1.5e9
    return BurstEnvelopeReceiver({
        'reset_or_init':((.85*burst,1.15*burst),(.85*480/1.5e9,1.15*480/1.5e9),525e-9),
        'wake':((.85*burst,1.15*burst),(.85*burst,1.15*burst),175e-9)},**kwargs)


class SataOobStartup:
    """External-FPGA startup reduction driven by received envelope observations.

    Enters await_alignment, then times out without alignment; never asserts PHY
    ready. Local reaction and overall
    timeout are exploration parameters, not standard timing claims. Actual ALIGN,
    calibration, D10.2, retry and power-management behavior remain unimplemented.
    """
    def __init__(self,role,*,reaction_s=100e-9,timeout_s=100e-6,detector_tau_s=10e-9):
        if role not in ('host','device') or not 0<reaction_s<timeout_s or not math.isfinite(timeout_s):
            raise ValueError('Startup role/timing')
        self.role=role;self.reaction=reaction_s;self.timeout=timeout_s
        self.detector=sata_envelope_receiver(tau_s=detector_tau_s)
        self.state='stopped';self.time=0.;self.deadline=math.inf
        self.observed=0;self.history=[];self.transmissions=[]
        self.oob_completed_at=None;self.fault_reason=None

    def _transmit(self,kind,start):
        self.transmissions.append(dict(kind=kind,start_s=start,
            intervals=[(start+a,start+b) for a,b in sata_oob(kind)]))

    def start(self,time=0.):
        if self.state!='stopped' or not math.isfinite(time) or time<self.time:
            raise ValueError('Stopped startup controller required')
        self.detector.advance(time);self.time=time;self.deadline=time+self.timeout
        self.state='wait_init' if self.role=='host' else 'wait_reset'
        if self.role=='host':self._transmit('reset',time)

    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Monotonic startup time')
        if time>self.next_event:raise ValueError('Do not skip startup observation/deadline')
        self.detector.advance(time)
        for event in self.detector.events[self.observed:]:
            when=event['time_s'];kind=event['kind']
            if when>=self.deadline:
                self.state='fault';self.fault_reason='startup timeout'
            before=self.state
            if self.state=='wait_reset' and kind=='reset_or_init':
                self._transmit('init',when+self.reaction);self.state='wait_wake'
            elif self.state=='wait_init' and kind=='reset_or_init':
                self._transmit('wake',when+self.reaction);self.state='wait_wake'
            elif self.state=='wait_wake' and kind=='wake':
                if self.role=='device':self._transmit('wake',when+self.reaction)
                self.state='await_alignment';self.oob_completed_at=when
            elif self.state not in ('fault','stopped'):
                self.state='fault';self.fault_reason='unexpected OOB during startup'
            self.history.append(dict(time_s=when,kind=kind,before=before,after=self.state))
        self.observed=len(self.detector.events)
        if time>=self.deadline and self.state not in ('stopped','fault'):
            self.state='fault';self.fault_reason='startup timeout'
        self.time=time

    def drive_received(self,voltage,time):
        self.advance(time);self.detector.drive(voltage,time)

    @property
    def phy_ready(self):return False

    @property
    def next_event(self):
        timeout=self.deadline if self.state not in ('stopped','fault') else math.inf
        return min(self.detector.next_event,timeout)
