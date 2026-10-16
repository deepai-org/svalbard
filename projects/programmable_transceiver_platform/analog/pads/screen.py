"""Bounded PDK transistor checks with a retained external wired TX network.

Core control/bias waveforms are bench inputs, not completed control circuitry.
No transient result from this bench qualifies ESD or missing pad families.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
from circuits import wired_transmit
from design import PROJECT
from transmit_controls import attach as attach_transmit_guard


def run_spice(work,name,text, *, reject_transient_op=False):
    path=work/(name+'.spice')
    path.write_text(text)
    (work/(name+'.dat')).unlink(missing_ok=True)
    result=subprocess.run(['ngspice','-b',str(path)],capture_output=True,text=True,timeout=120)
    (work/(name+'.log')).write_text(result.stdout+result.stderr)
    result.check_returncode()
    if reject_transient_op and 'Transient op started' in result.stdout+result.stderr:
        raise ValueError('DC solve fell back to transient initialization: '+str(path))
    return np.loadtxt(work/(name+'.dat'),skiprows=1)


def header(circuit,pdk,physical=None):
    model=physical.read_text() if physical is not None else circuit.spice()
    definition=next(line.split() for line in model.splitlines() if line.startswith('.subckt '))
    if definition[2:]!=circuit.ports:raise ValueError('Physical port order differs from circuit')
    return ('Wired pad candidate with explicit core control interfaces\n'
            f'.include {pdk}/design.ngspice\n.lib {pdk}/sm141064.ngspice typical\n'
            f'.lib {pdk}/sm141064.ngspice res_typical\n.temp 27\n'+model+
            'Xpad '+' '.join(circuit.ports)+' '+definition[1]+'\nVSS VSS 0 0\n')


def control(work,name,analysis,vectors):
    return ('.control\nset wr_singlescale\nset wr_vecnames\n'+analysis+
            f'\nwrdata {work}/{name}.dat '+vectors+'\nquit\n.endc\n.end\n')


def dc_fixture(circuit,pdk,branch,physical=None):
    text=header(circuit,pdk,physical)+'VDD VDD 0 3.3\nVCAS CASCODE 0 3.3\n'
    for n in circuit.ports[5:]:
        value=3.3 if n in (branch+'_P','DETECT_PBIAS') else 0
        if branch=='DETECT' and n=='DETECT_ENABLE':value=3.3
        text+=f'V{n} {n} 0 {value}\n'
    if branch=='DETECT':
        text+='VPADP PAD_P 0 .4\nVPADN PAD_N 0 .4\n'
    else:
        text+='VPULL PULL 0 3.3\nRLP PULL PAD_P 50\nRLN PULL PAD_N 50\n'
    return text


def screen(work,pdk,physical=None,calibration_only=False):
    work.mkdir(parents=True,exist_ok=True)
    architecture=json.loads((PROJECT/'spec/analog-architecture.json').read_text())
    circuit=wired_transmit()
    targets={'MAIN':architecture['blocks']['wiredtx']['parameters']['tail_current_a'],
             'POST':architecture['blocks']['wiredtx']['parameters']['tail_current_a'] *
                    max(architecture['blocks']['wiredtx']['parameters']['postcursor_fraction']),
             'TMDS':architecture['blocks']['tmds']['parameters']['sink_current_a'],
             'DETECT':2*architecture['blocks']['detect']['parameters']['test_current_a']}
    calibration={}; calibration_curves={}
    for branch,target in targets.items():
        name='dc_'+branch.lower()
        source='VDETECT_PBIAS' if branch=='DETECT' else 'V'+branch+'_BIAS'
        current='-i(VPADP)-i(VPADN)' if branch=='DETECT' else 'i(VPULL)'
        text=dc_fixture(circuit,pdk,branch,physical)+control(work,name,f'dc {source} 0 3.3 .01',current)
        data=run_spice(work,name,text)
        currents=-data[:,1]
        calibration_curves[branch]=(data[:,0],currents)
        index=int(np.argmin(abs(currents-target)))
        calibration[branch]=dict(bias_v=float(data[index,0]),current_a=float(currents[index]),
                                target_a=target,maximum_a=float(max(currents)),
                                target_reached=bool(min(abs(currents-target))<target*.03))
    if physical is not None:
        # Reject inadequate combined-current headroom before long transients.
        calibration_path=work/'calibration.json'
        calibration_path.write_text(json.dumps(dict(calibration=calibration,
            sources_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                (Path(__file__),Path(__file__).with_name('circuits.py'),physical,
                 PROJECT/'spec/analog-architecture.json',pdk/'design.ngspice',pdk/'sm141064.ngspice',pdk/'sm141064.spice')}),indent=2)+'\n')
        from tx_compliance import screen as current_compliance_screen
        compliance=current_compliance_screen(work/'current-compliance',pdk,physical,work,calibration_path)
        if not all(case['loaded_current_within_3_percent'] for case in compliance['cases'].values()):
            raise ValueError('TX combined-current compliance failed; retain diagnostics and revise before lifecycle runs')
    if calibration_only:
        if physical is None:raise ValueError('Calibration-only publication requires a physical model')
        report=json.loads(calibration_path.read_text())
        report.update(status='DC_calibration_only_not_lifecycle',physical_capacitance_included=True,
            scope='Four branch DC calibration and current-compliance checks only. No lifecycle or loading acceptance.')
        (work/'screen-report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
        return report
    # Measure the complete resistor/switch branch, including off-state load.
    termination = {}
    for enabled in (False, True):
        fixture = dc_fixture(circuit,pdk,'MAIN',physical)
        fixture = fixture.replace('VPULL PULL 0 3.3\nRLP PULL PAD_P 50\nRLN PULL PAD_N 50\n',
                                  'VPADP PAD_P 0 1.8\nVPADN PAD_N 0 1.8\n')
        fixture = fixture.replace('VTERM_VCM TERM_VCM 0 0', 'VTERM_VCM TERM_VCM 0 1.8')
        if enabled:
            fixture = fixture.replace('VTERM_ENABLE TERM_ENABLE 0 0','VTERM_ENABLE TERM_ENABLE 0 3.3')
        name = 'termination_on' if enabled else 'termination_off'
        fixture += control(work,name,'dc VPADP 1.0 2.4 .01','i(VPADP) i(VTERM_VCM)')
        values = run_spice(work,name,fixture)
        center = int(np.argmin(abs(values[:,0]-1.8)))
        conductance = -(values[center+1,1]-values[center-1,1])/(values[center+1,0]-values[center-1,0])
        termination[name] = dict(differential_small_signal_ohm_per_leg=float(1/conductance),
            target_ohm_per_leg=architecture['blocks']['wiredtx']['parameters']['source_r_ohm_per_leg'] if enabled else None,
            common_mode_v=1.8,common_mode_source_current_a=float(-values[center,2]),maximum_abs_pad_current_a=float(max(abs(values[:,1]))),
            scope='Nominal local slope with ideal TERM_VCM; no resistor trim or finite regulator impedance.')
    def pwl(points):
        return 'PWL('+ ' '.join(f'{t}n {v}' for t,v in points)+')'
    text=header(circuit,pdk,physical)
    text+='VPULL PULL 0 3.3\nRLP PULL BOARD_P 50\nRLN PULL BOARD_N 50\n'
    # Explicit external bonds; not buried in on-die pad capacitance.
    text+='RBP BOARD_P BOND_P 1\nRBN BOARD_N BOND_N 1\nLBP BOND_P PAD_P 1n\nLBN BOND_N PAD_N 1n\n'
    # Planning metal loading only. Device junction/overlap C is already in MOS.
    if physical is None:
        text+='CMETALP PAD_P VSS .15p\nCMETALN PAD_N VSS .15p\n'
    text+='VDD VDD 0 '+pwl([(0,3.3),(32,3.3),(32.2,0),(44,0),(44.2,1.5),(52,1.5),(52.2,3.3),(100,3.3)])+'\n'
    text+='VTERM_VCM TERM_VCM 0 1.8\nVTERM_ENABLE TERM_ENABLE 0 '+pwl([(0,0),(60,0),(60.1,3.3),(76,3.3),(76.1,0),(100,0)])+'\n'
    text+='BCAS CASCODE 0 V=V(VDD)\nVDATA DATA 0 PULSE(0 3.3 0 20p 20p 380p 800p)\n'
    text+='VPOSTDATA POSTDATA 0 PULSE(0 3.3 400p 20p 20p 380p 800p)\n'
    spans={'TMDS':(8,24),'MAIN':(60,76),'POST':(68,72),'DETECT':(78,94)}
    for branch,span in spans.items():
        points=[(0,0),(100,0)] if span is None else [(0,0),(span[0],0),(span[0]+.1,1),(span[1],1),(span[1]+.1,0),(100,0)]
        text+=f'VEN_{branch} EN_{branch} 0 '+pwl(points)+'\n'
        if branch=='DETECT':
            drop=3.3-calibration[branch]['bias_v']
            text+=f'BDETECTBIAS DETECT_PBIAS 0 V=V(VDD)-{drop}*V(EN_DETECT)\n'
            text+='BDETECTEN DETECT_ENABLE 0 V=V(VDD)*V(EN_DETECT)\n'
        else:
            bias=calibration.get(branch,{}).get('bias_v',0)
            text+=f'BBIAS_{branch} {branch}_BIAS 0 V={bias}*V(EN_{branch})\n'
            data_node='POSTDATA' if branch=='POST' else 'DATA'
            # A negative delayed tap: main[n] - a*main[n-1]. Positive tap
            # polarity is also electrically possible, but is not this fixture.
            p_gate=f'(3.3-V({data_node}))' if branch=='POST' else f'V({data_node})'
            n_gate=f'V({data_node})' if branch=='POST' else f'(3.3-V({data_node}))'
            text+=f'BP_{branch} {branch}_P 0 V={p_gate}*V(EN_{branch})\n'
            text+=f'BN_{branch} {branch}_N 0 V={n_gate}*V(EN_{branch})\n'
    raw_lifecycle_network=text
    reset_request=pwl([(0,0),(26,0),(26.1,3.3),(31,3.3),(31.1,0),(100,0)])
    text=attach_transmit_guard(text,reset_request,'3.3')
    text+=control(work,'lifecycle','tran 5p 100n', 'v(PAD_P) v(PAD_N) v(VDD) i(VDD) i(VPULL)')
    data=run_spice(work,'lifecycle',text)
    windows={'disabled':(2,7),'active_tmds':(12,23),'reset':(27,31),
             'unpowered':(36,43),'brownout':(47,51),'recovered_disabled':(55,59),
             'active_main':(64,67),'active_main_post':(69,71),
             'reconfiguration':(76,78),'buffer_precharge':(58,60),'buffer_release':(78,82),'detect':(82,93)}
    states={}
    for name,(start,end) in windows.items():
        x=data[(data[:,0]>=start*1e-9)&(data[:,0]<=end*1e-9)]
        if len(x)<2 or data[-1,0]<end*1e-9:
            states[name]=dict(status='not_reached_by_transient',samples=len(x));continue
        states[name]=dict(status='window_reached_not_acceptance',samples=len(x),pad_min_v=float(x[:,1:3].min()),
                          pad_max_v=float(x[:,1:3].max()),
                          differential_pp_v=float(np.ptp(x[:,1]-x[:,2])),
                          maximum_supply_backfeed_a=float(max(0,x[:,4].max())),
                          external_mean_current_a=float(-x[:,5].mean()))
    # Reuse the entire retained trajectory and external network, changing only
    # the attached common-mode source. These impedances are sensitivity probes,
    # not a claimed regulator implementation or measured silicon parameters.
    finite_bias = {}
    common_mode = architecture['blocks']['bias']['parameters']['common_mode_v']
    for resistance in (1., 10., 100.):
        name = f'lifecycle_bias_{int(resistance)}ohm'
        source = (f'BTERM_TARGET TERM_TARGET 0 V=min(max(V(VDD),0),{common_mode})\n'
                  f'RTERM_SOURCE TERM_TARGET TERM_VCM {resistance}\n'
                  'CTERM_SOURCE TERM_VCM VSS 10p\n')
        probe = text[:text.index('.control')].replace('VTERM_VCM TERM_VCM 0 1.8\n', source)
        probe += control(work,name,'tran 5p 100n',
                         'v(PAD_P) v(PAD_N) v(TERM_VCM) v(TERM_TARGET) i(BTERM_TARGET)')
        values = run_spice(work,name,probe)
        complete = bool(values[-1,0] >= 99.99e-9)
        measured = {}
        for state,(start,end) in windows.items():
            x = values[(values[:,0]>=start*1e-9)&(values[:,0]<=end*1e-9)]
            if len(x)<2 or values[-1,0]<end*1e-9:
                measured[state] = dict(status='not_reached_by_transient')
                continue
            measured[state] = dict(status='window_reached_not_acceptance',
                common_mode_min_v=float(x[:,3].min()), common_mode_max_v=float(x[:,3].max()),
                maximum_target_error_v=float(abs(x[:,3]-x[:,4]).max()),
                peak_required_sink_a=float(max(0,x[:,5].max())),
                peak_required_source_a=float(max(0,-x[:,5].min())),
                differential_pp_v=float(np.ptp(x[:,1]-x[:,2])))
        finite_bias[name] = dict(transient_complete=complete,series_resistance_ohm=resistance,
            shunt_capacitance_f=10e-12,target_v=common_mode,lifecycle_states=measured,
            scope='Unmeasured R/C sensitivity probe, supply-tracking shared bias target; source can sink unlimited current. Retained external TMDS pullups also during serial operation are an adverse contention fixture. No regulator power or current-limit qualification.')
    # A finite attached buffer, not a second ideal power source on VCM. Its
    # source current comes from VDD and its sink current returns to VSS. Retain
    # the same pad branches, powered peer and capacitor through every state.
    # This is a core-boundary capability probe, not a transistor implementation.
    tx_parameters=architecture['blocks']['wiredtx']['parameters']
    bleed_current=termination['termination_off']['common_mode_source_current_a']*common_mode/1.8
    buffer_limit=1.1*(max(tx_parameters['current_range_a'])*(1+max(tx_parameters['postcursor_fraction']))+max(0,bleed_current))
    if buffer_limit>architecture['blocks']['wiredtx']['resource_allocation']['current_budget_ma']['wired']*1e-3:
        raise ValueError('Termination buffer capability exceeds the complete wired-TX current allocation')
    output_r=1.; output_c=10e-12; headroom=.2
    bounded_source=('VTERM_BUFFER_REQUEST TERM_BUFFER_REQUEST 0 '+pwl([(0,0),(58,0),(58.1,3.3),(78,3.3),(78.1,0),(100,0)])+'\n'
        'BTERM_ON TERM_ON 0 V=min(max(V(TERM_BUFFER_REQUEST)/3.3,0),1)\n'
        f'BTERM_TARGET TERM_TARGET 0 V=min(max(V(VDD),0),{common_mode})*V(TERM_ON)\n'
        f'BTERM_REQUEST TERM_REQUEST 0 V={buffer_limit}*tanh((V(TERM_TARGET)-V(TERM_VCM))/({output_r}*{buffer_limit}))\n'
        f'BTERM_SOURCE VDD TERM_SOURCE_I I=max(V(TERM_REQUEST),0)*min(max((V(VDD)-V(TERM_VCM))/{headroom},0),1)*min(max(V(VDD)/3.3,0),1)*V(TERM_ON)\n'
        f'BTERM_SINK TERM_SINK_I VSS I=max(-V(TERM_REQUEST),0)*min(max(V(TERM_VCM)/{headroom},0),1)*min(max(V(VDD)/3.3,0),1)*V(TERM_ON)\n'
        'VTERM_SOURCE_I TERM_SOURCE_I TERM_VCM 0\nVTERM_SINK_I TERM_VCM TERM_SINK_I 0\n'
        f'CTERM_SOURCE TERM_VCM VSS {output_c}\n')
    bounded_models={}
    for load_case in ('powered_pullups','differential_load','stale_termination_request','external_source_termination'):
        name='lifecycle_bounded_bias'+{'powered_pullups':'','differential_load':'_differential','stale_termination_request':'_stale_request','external_source_termination':'_external_termination'}[load_case]
        probe=raw_lifecycle_network.replace('VTERM_VCM TERM_VCM 0 1.8\n',bounded_source)
        if load_case=='differential_load':
            probe=probe.replace('RLP PULL BOARD_P 50\nRLN PULL BOARD_N 50\n',
                f'RDIFF_LOAD BOARD_P BOARD_N {architecture["blocks"]["termination"]["parameters"]["differential_ohm"]}\n')
        external_details=None
        if load_case=='stale_termination_request':
            original_request=next(line for line in probe.splitlines() if line.startswith('VTERM_ENABLE '))
            probe=probe.replace(original_request,'VTERM_ENABLE TERM_ENABLE 0 3.3')
            original_buffer_request=next(line for line in probe.splitlines() if line.startswith('VTERM_BUFFER_REQUEST '))
            probe=probe.replace(original_buffer_request,'VTERM_BUFFER_REQUEST TERM_BUFFER_REQUEST 0 3.3')
        if load_case=='external_source_termination':
            for source,node in [('VTERM_ENABLE','TERM_ENABLE'),('VTERM_BUFFER_REQUEST','TERM_BUFFER_REQUEST')]:
                original_request=next(line for line in probe.splitlines() if line.startswith(source+' '))
                probe=probe.replace(original_request,f'{source} {node} 0 0')
            receive_r=architecture['blocks']['termination']['parameters']['differential_ohm']/2
            coupling=100e-9  # Declared external fixture, not an on-chip budget.
            probe+=f'VREMOTE_CM REMOTE_CM 0 {common_mode}\n'
            for leg in ('P','N'):
                probe+=f'CAC_{leg} BOARD_{leg} REMOTE_{leg} {coupling}\nRREMOTE_{leg} REMOTE_{leg} REMOTE_CM {receive_r}\n'
            programmed={}
            for branch,target in [('MAIN',max(tx_parameters['current_range_a'])),
                                  ('POST',max(tx_parameters['current_range_a'])*max(tx_parameters['postcursor_fraction']))]:
                voltages,currents=calibration_curves[branch];index=int(np.argmin(abs(currents-target)))
                old=f'BBIAS_{branch} {branch}_BIAS 0 V={calibration[branch]["bias_v"]}*V(EN_{branch})'
                if old not in probe:raise ValueError('Driver bias binding changed')
                probe=probe.replace(old,f'BBIAS_{branch} {branch}_BIAS 0 V={voltages[index]}*V(EN_{branch})')
                programmed[branch]=dict(target_a=target,calibrated_current_a=float(currents[index]),bias_v=float(voltages[index]),target_reached=bool(abs(currents[index]-target)<.03*target))
            external_details=dict(source_pullup_v=3.3,source_pullup_ohm_per_leg=50,
                coupling_f_per_leg=coupling,remote_termination_ohm_per_leg=receive_r,
                remote_common_mode_v=common_mode,programmed_current=programmed,
                scope='Separate serial board fixture. Source pullups and AC-coupled receiver stay attached in all states; its TMDS window is an electrical stress probe, not a valid TMDS connection. Board traces and distributed metal R remain absent.')
        if load_case!='stale_termination_request':
            probe=attach_transmit_guard(probe,reset_request,'3.3')
        probe+=control(work,name,'tran 5p 100n',
            'v(PAD_P) v(PAD_N) v(TERM_VCM) v(TERM_TARGET) i(VTERM_SOURCE_I) i(VTERM_SINK_I) v(VDD) i(VDD) v(TERM_ON)'+
            (' v(REMOTE_P) v(REMOTE_N) i(VPULL) i(VREMOTE_CM) i(VSS)' if external_details else ''))
        bounded=run_spice(work,name,probe);bounded_states={}
        for state,(start,end) in windows.items():
            x=bounded[(bounded[:,0]>=start*1e-9)&(bounded[:,0]<=end*1e-9)]
            if len(x)<2 or bounded[-1,0]<end*1e-9:
                bounded_states[state]=dict(status='not_reached_by_transient');continue
            bounded_states[state]=dict(status='window_reached_not_acceptance',
                common_mode_min_v=float(x[:,3].min()),common_mode_max_v=float(x[:,3].max()),
                maximum_target_error_v=float(abs(x[:,3]-x[:,4]).max()),
                end_target_error_v=float(abs(x[-1,3]-x[-1,4])),end_common_mode_v=float(x[-1,3]),
                peak_buffer_source_a=float(x[:,5].max()),peak_buffer_sink_a=float(x[:,6].max()),
                peak_total_supply_draw_a=float(max(0,-x[:,8].min())),
                maximum_supply_backfeed_a=float(max(0,x[:,8].max())),
                buffer_request_min=float(x[:,9].min()),buffer_request_max=float(x[:,9].max()),
                peak_buffer_output_dissipation_w=float(((x[:,7]-x[:,3])*x[:,5]+x[:,3]*x[:,6]).max()),
                fraction_near_current_limit=float(np.mean(np.maximum(x[:,5],x[:,6])>=.95*buffer_limit)),
                differential_pp_v=float(np.ptp(x[:,1]-x[:,2])))
            if external_details:
                bounded_states[state].update(remote_differential_pp_v=float(np.ptp(x[:,10]-x[:,11])),
                    remote_common_mode_min_v=float(((x[:,10]+x[:,11])/2).min()),
                    remote_common_mode_max_v=float(((x[:,10]+x[:,11])/2).max()),
                    peak_external_pullup_source_current_a=float(max(0,-x[:,12].min())),
                    peak_remote_bias_source_current_a=float(max(0,-x[:,13].min())),
                    peak_pad_return_current_a=float(max(0,x[:,14].max())),
                    mean_external_sources_power_w=float(np.mean(-3.3*x[:,12]-common_mode*x[:,13])))
        bounded_models[load_case]=dict(external_source_termination=external_details,transient_complete=bool(bounded[-1,0]>=99.99e-9),
            source_sink_limit_a=buffer_limit,estimated_bleeder_current_a=bleed_current,small_error_output_resistance_ohm=output_r,
            output_capacitance_f=output_c,headroom_probe_v=headroom,
            limit_basis='Shared maximum main-plus-postcursor current plus measured off-termination bias load scaled to target voltage, with 10% transient allowance. Must fit the shared total wired-TX current allocation; not achieved buffer capability.',
            current_limits_observed=bool(np.all(bounded[:,5:7]>=-1e-12) and np.max(bounded[:,5:7])<=buffer_limit*(1+1e-6)),
            lifecycle_states=bounded_states,
            alternating_postcursor_check=dict(main_pp_v=bounded_states['active_main'].get('differential_pp_v'),
                main_plus_post_pp_v=bounded_states['active_main_post'].get('differential_pp_v'),
                swing_increases=(bounded_states['active_main_post'].get('differential_pp_v',0)>bounded_states['active_main'].get('differential_pp_v',float('inf'))),
                scope='Alternating-pattern negative-tap polarity check only; peak-to-peak values include ringing and are not an eye, arbitrary-data, or protocol-compliance result.'),
            control_scope='On-chip termination and buffer requests held off; all physical branches remain. External source resistors and AC-coupled receiver supply the serial load.' if external_details else 'Termination and buffer requests both held high throughout reset/power loss: deliberately invalid/fault configuration, not a supported operating mode.' if load_case=='stale_termination_request' else 'Explicit core sequencing: enable buffer at58ns before termination at60ns; disconnect termination at76ns before disabling buffer at78ns. Both source and sink turn off when unrequested. The 2ns lead/hold is a fixture scheduling assumption, not an implemented controller or a settled-loop guarantee.',
            limitations=['Behavioral attached-core buffer only; output-stage and control circuitry are not laid out.',
                'Includes source current in VDD accounting and finite output headroom; excludes quiescent/control power and loop dynamics. Request gating is an ideal core-boundary control, not implemented enable logic.',
                'No reverse path is modeled inside this buffer. Its power-off isolation must be implemented, not assumed from this screen.',
                'Smooth current limiting, 1ohm incremental output impedance and 10pF output storage are unmeasured probes.',
                'External load is fixed throughout each lifecycle: powered 3.3V/50ohm pullups (adverse for serial) or the shared differential termination (a separate serial loading probe).'])
    bounded_bias=dict(cases=bounded_models,transient_complete=all(v['transient_complete'] for v in bounded_models.values()))
    # Keep external enable high while unpowered; test the local circuit
    # rather than silently forcing its input safe in the bench.
    negative=dc_fixture(circuit,pdk,'MAIN',physical).replace('VDD VDD 0 3.3','VDD VDD 0 0')
    negative=negative.replace('VDETECT_ENABLE DETECT_ENABLE 0 0',
                              'VDETECT_ENABLE DETECT_ENABLE 0 3.3')
    negative=negative.replace('VDETECT_PBIAS DETECT_PBIAS 0 3.3',
                              'VDETECT_PBIAS DETECT_PBIAS 0 0')
    negative+=control(work,'stale_enable','op','v(PAD_P) v(PAD_N) i(VDD)')
    adverse=np.atleast_2d(run_spice(work,'stale_enable',negative))
    report=dict(status='first_pass_transistor_screen_not_pad_qualification',calibration=calibration,
                physical_capacitance_included=physical is not None,
                termination=termination,finite_common_mode_probes=finite_bias,
                bounded_common_mode_buffer=bounded_bias,
                transient_complete=bool(data[-1,0]>=99.99e-9),
                stale_detect_enable_unpowered=dict(pad_p_v=float(adverse[0,1]),
                    pad_n_v=float(adverse[0,2]),supply_backfeed_a=float(adverse[0,3]),
                    scope='Independently held enable tests local isolation at DC; transient discharge and brownout need separate checks.'),
                lifecycle_states=states,device_count=len(circuit.devices),
                control_guard=dict(integrated_in_lifecycle=True,
                    bounded_buffer_guarded_cases=['powered_pullups','differential_load','external_source_termination'],
                    deliberate_bypass_cases=['stale_termination_request','raw_DC_branch_characterization'],
                    scope='Behavioral mode exclusion, reset and supply-window gating; QUALIFIED prescribed. No physical hazard control, sticky fault storage or buffer-ready detection.'),
                assumptions=dict(temperature_c=27,supply_v=3.3,external_pullup_v=3.3,
                                 external_pullup_ohm=50,bond_inductance_h=1e-9,
                                 bond_resistance_ohm=1,assigned_metal_capacitance_f_per_leg=.15e-12 if physical is None else None,
                                 alternating_bit_rate_hz=2.5e9,postcursor_polarity='negative delayed tap; complementary gate controls reversed for POST'),
                limitations=circuit.limitations+[
                    'Behavioral mode/reset/supply guard is integrated; ideal core biases and prescribed qualification do not establish physical reset/brownout circuitry.',
                    'Detection lifecycle uses retained 3.3V pullups: no useful injection is expected above source compliance.',
                    'DC detection calibration at 0.4V is a separate load fixture, not the lifecycle load.',
                    'No package return coupling, statistical mismatch, noise, ESD or distributed wire resistance in this run.',
                    'Extracted capacitance replaces assigned metal C when a physical netlist is supplied; it is never added twice.',
                    'R/C common-mode probes have unlimited current. The separately identified bounded-buffer probe adds current/headroom limits and output-stage power accounting, not implemented regulation or reset/brownout controls.'],
                sources_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in [Path(__file__),Path(__file__).with_name('transmit_controls.py'),Path(__file__).with_name('circuits.py'),
                                          PROJECT/'spec/analog-architecture.json',pdk/'design.ngspice',
                                          pdk/'sm141064.ngspice',pdk/'sm141064.spice']+([physical] if physical is not None else [])})
    (work/'screen-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(calibration=calibration,states=states),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--pdk-model-dir',type=Path,required=True)
    parser.add_argument('--physical',type=Path)
    parser.add_argument("--calibration-only",action="store_true")
    args=parser.parse_args()
    screen(args.output_dir.resolve(),args.pdk_model_dir.resolve(),args.physical.resolve() if args.physical else None,args.calibration_only)
