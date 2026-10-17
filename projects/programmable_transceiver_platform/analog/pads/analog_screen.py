"""Dedicated RF/reference pad lifecycle and loading screens.

One physical pad netlist is used in AC and retained-state transient analyses.
The attached core is an explicit behavioral boundary using shared match/drive
parameters. This does not qualify that core or pretend disabled clamps vanish.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from circuits import build
from design import PROJECT
from screen import run_spice as raw_run_spice,control as base_control


def control(work,name,analysis,vectors):
    # Preserve current-accounting precision at tens of mA; default wrdata
    # rounding can otherwise dominate a 100pA KCL residual check.
    return base_control(work,name,analysis,vectors).replace('.control\n','.control\nset numdgt=15\n',1)


def screen(work,pdk,physical,family,external_termination_ohm=None, *, route_report=None,
           capacitance_location="bond", resistance_corner="nominal", external_coupling_f=None, rf_tx_gain=None, external_series_l_h=0., external_inductor_q=30., numerical_anchor_resistance=1e12):
    if not np.isfinite(external_series_l_h) or external_series_l_h<0 or not np.isfinite(external_inductor_q) or external_inductor_q<=0:
        raise ValueError('External inductance must be nonnegative and Q positive')
    if external_series_l_h and family!='rf_transmit':
        raise ValueError('External series-match probe currently supports RF TX only')
    if rf_tx_gain is not None and family!='rf_transmit':raise ValueError('RF TX gain applies only to RF transmit')
    work.mkdir(parents=True,exist_ok=True)
    def run_spice(directory, name, deck):
        return raw_run_spice(directory, name, deck, reject_transient_op=True)
    circuit=build(family)
    if external_termination_ohm is not None and (family!='reference_clock' or
            not np.isfinite(external_termination_ohm) or external_termination_ohm<=0):
        raise ValueError('Optional finite positive board termination is a reference-clock fixture')
    architecture=json.loads((PROJECT/'spec/analog-architecture.json').read_text())
    contract=json.loads((PROJECT/'spec/contract.json').read_text())
    model=physical.read_text()
    route_evidence=None
    if route_report is not None:
        from rf_route import augment
        model,route_evidence=augment(model,family,route_report,capacitance_location,resistance_corner)
        (work/'segmented-pad.spice').write_text(model)
    if not np.isfinite(numerical_anchor_resistance) or numerical_anchor_resistance < 1e12:
        raise ValueError('Numerical floating-metal anchors must be at least 1 Tohm')
    from loading_audit import anchor_floating_conductors
    model, anchors = anchor_floating_conductors(model, numerical_anchor_resistance)
    core_prefix='COREPAD' if route_evidence else 'PAD'
    subckt=next(line.split()[1] for line in model.splitlines() if line.startswith('.subckt '))
    declared=next(line.split()[2:] for line in model.splitlines() if line.startswith('.subckt '))
    if declared!=circuit.ports+(['COREPAD_P','COREPAD_N'] if route_evidence else []):raise ValueError('Physical cell port order differs from circuit')
    header=(f'{family} retained analog pad screen\n.include {pdk}/design.ngspice\n'
            f'.lib {pdk}/sm141064.ngspice typical\n.lib {pdk}/sm141064.ngspice res_typical\n'
            f'.temp 27\n{model}\nXpad '+ ' '.join(declared)+' '+subckt+'\nVSS VSS 0 0\n')
    caps={}
    for mode in ('odd','common'):
        sign=-.5 if mode=='odd' else .5
        bench=header+f'VP PAD_P 0 DC 1.65 AC .5\nVN PAD_N 0 DC 1.65 AC {sign}\n'
        if family=='reference_clock':bench+='VCM VCM 0 1.65\n'
        bench+=control(work,'cap_'+mode,'ac lin 1 1G 1G','real(i(VP)) imag(i(VP)) real(i(VN)) imag(i(VN))')
        x=np.atleast_2d(run_spice(work,'cap_'+mode,bench))[0]
        # Sources supply negative branch current. Both legs are reported;
        # mismatch cannot disappear into a single nominal pair value.
        caps[mode]=[-float(x[2])/(2*np.pi*1e9*.5),-float(x[4])/(2*np.pi*1e9*sign)]
    dc=header+'VP PAD_P 0 0\nVN PAD_N 0 1.65\n'
    if family=='reference_clock':dc+='VCM VCM 0 1.65\n'
    dc+=control(work,'dc','dc VP -1 4 .02','i(VP) i(VSS)')
    sweep=run_spice(work,'dc',dc)
    def at(volts):return sweep[int(np.argmin(abs(sweep[:,0]-volts)))]
    dc_summary=dict(pad_source_current_at_minus_0p8_v_a=float(at(-.8)[1]),
                    pad_source_current_at_3p6_v_a=float(at(3.6)[1]),
                    scope='DC loading/clamp probe only; -0.8V and 4V endpoints are adverse, not safe operating claims.')
    if family=='reference_clock':
        lo,hi=at(1.4),at(1.9)
        dc_summary['effective_bias_resistance_ohm']=float(-(hi[0]-lo[0])/(hi[1]-lo[1]))
    ref=family=='reference_clock'; tx=family=='rf_transmit'
    coupling=(10e-9 if ref else 100e-12) if external_coupling_f is None else external_coupling_f
    if not np.isfinite(coupling) or coupling<=0:raise ValueError('External coupling must be finite and positive')
    reference_package=architecture['model_assumptions']['reference_input_package']['parameters']
    bond_l=reference_package['bond_l_h'] if ref else 1e-9
    mutual_l=reference_package['mutual_l_h'] if ref else 0.
    source_r=reference_package['source_r_ohm'] if ref else 50.
    if not 0<=mutual_l<bond_l:raise ValueError('Invalid shared bond inductance matrix')
    frequency=2.5e9 if ref else 2.4e9
    peak=contract['physical_services']['external_clock_input']['source_differential_peak_v'] if ref else .1
    tx_target=None
    if tx:
        driver=architecture['blocks']['rfdriver']['parameters']
        target_w=1e-3*10**(driver['target_mean_power_dbm']/10)
        target_load_peak=(2*target_w*driver['load_ohm_differential'])**.5
        peak=target_load_peak*(1+driver['source_r_ohm_differential']/driver['load_ohm_differential'])
        selected_gain=driver['nominal_gain'] if rf_tx_gain is None else rf_tx_gain
        if not np.isfinite(selected_gain) or not driver['gain_range'][0]<=selected_gain<=driver['gain_range'][1]:
            raise ValueError('RF TX gain exceeds shared driver range')
        implied_input_peak=peak/driver['nominal_gain']
        peak=implied_input_peak*selected_gain
        tx_target=dict(selected_gain=selected_gain,nominal_gain=driver['nominal_gain'],
            allowed_gain_range=driver['gain_range'],implied_driver_input_peak_v=implied_input_peak,
            target_mean_power_w=target_w,target_mean_power_dbm=driver['target_mean_power_dbm'],
            ideal_load_differential_peak_v=target_load_peak,command_differential_peak_v=peak,
            basis='Shared output-power target converted to a sinusoid, compensating only shared source/load resistance. Input amplitude is fixed at the nominal gain calibration; selected gain changes only the command, not current/headroom limits. No fit to measured pad or route loss; no claim of modulated-signal crest-factor margin.')
    network=header
    network+='VDD VDD 0 PWL(0 3.3 28n 3.3 29n 0 40n 0 41n 1.5 48n 1.5 49n 3.3 80n 3.3)\n'
    finite_bias=None
    finite_tx=None
    if family=='rf_receive':
        # Conservative split-resistor input load retained. This is not inferred
        # from the differential match target to be the actual LNA DC topology.
        bias=architecture['blocks']['bias']['parameters']
        allocation=architecture['blocks']['lna']['resource_allocation']['current_budget_ma']['rf_rx']*1e-3
        limit=10*bias['bias_unit_a']
        if not 0<limit<allocation:raise ValueError('RX bias probe consumes LNA allocation')
        nominal=2*bias['common_mode_v']; bleed=bias['common_mode_v']/bias['bias_unit_a']
        output_r=100.; output_c=10e-12; headroom=.2
        finite_bias=dict(current_limit_a=limit,lna_total_current_allocation_a=allocation,
            limit_basis='Ten shared bias-current units; engineering probe, not measured output capacity.',
            output_r_ohm=output_r,output_c_f=output_c,headroom_v=headroom,
            passive_bleed_ohm=bleed,
            input_loading='Retained split resistors at half the shared differential match. Conservative DC/common-mode fixture, not implemented common-source LNA impedance.',
            scope='Supply-connected bounded behavioral driver; no loop bandwidth, quiescent current, reverse diode paths or transistor-level power-off proof.')
        network+=(f'BVCM_TARGET VCM_TARGET 0 V=.5*V(VDD)\n'
            f'BBIAS_REQUEST BIAS_REQUEST 0 V={limit}*tanh((V(VCM_TARGET)-V(VCM))/({output_r}*{limit}))\n'
            f'BBIAS_SOURCE VDD BIAS_SOURCE_I I=max(V(BIAS_REQUEST),0)*min(max((V(VDD)-V(VCM))/{headroom},0),1)*min(max(V(VDD)/{nominal},0),1)\n'
            f'BBIAS_SINK BIAS_SINK_I VSS I=max(-V(BIAS_REQUEST),0)*min(max(V(VCM)/{headroom},0),1)*min(max(V(VDD)/{nominal},0),1)\n'
            'VBIAS_SOURCE_I BIAS_SOURCE_I BIAS_OUT 0\nVBIAS_SINK_I BIAS_OUT BIAS_SINK_I 0\n'
            'VBIAS BIAS_OUT VCM 0\n'
            f'CBIAS VCM VSS {output_c}\nRBIAS_BLEED VCM VSS {bleed}\n')
    else:network+='BVCM VCM 0 V=.5*V(VDD)\n'
    network+='VEN ENABLE 0 PWL(0 1 12n 1 12.2n 0 60n 0 60.2n 1 80n 1)\n'
    for leg,sign in [('P',1),('N',-1)]:
        if tx:
            driver=architecture['blocks']['rfdriver']['parameters']
            load=driver['load_ohm_differential']/2
            resistance=driver['source_r_ohm_differential']/2
            # Commands are unloaded; output current comes from the rails.
            # Passive bleed is retained when the behavioral driver turns off.
            network+=f'BCORE_{leg} CORE_{leg} 0 V=V(VCM)+{sign*peak/2}*V(ENABLE)*sin(2*pi*{frequency}*time)\n'
            limit=driver['bias_current_a']/2
            headroom=driver['headroom_per_rail_v']
            nominal=driver['gain_reference_v']
            finite_tx=dict(current_limit_a_per_leg=limit,output_r_ohm_per_leg=resistance,
                headroom_v=headroom,passive_bleed_ohm_per_leg=1e6,
                active_bias_current_floor_a=driver['bias_current_a'],
                scope='Supply-connected bounded output boundary with a declared active bias-current floor. Sourced output current consumes that floor rather than being counted twice. Half the shared bias current per leg is an assumed capacity, not a proven transistor driver. Reverse junctions and feedback bandwidth remain unmodeled.')
            node=f'{core_prefix}_{leg}'
            network+=f'BREQUEST_{leg} REQUEST_{leg} 0 V={limit}*tanh((V(CORE_{leg})-V({node}))/({resistance}*{limit}))*V(ENABLE)*min(max(V(VDD)/{nominal},0),1)\n'
            network+=f'BSOURCE_{leg} VDD SOURCE_{leg} I=max(V(REQUEST_{leg}),0)*min(max((V(VDD)-V({node}))/{headroom},0),1)\n'
            network+=f'BSINK_{leg} SINK_{leg} VSS I=max(-V(REQUEST_{leg}),0)*min(max(V({node})/{headroom},0),1)\n'
            network+=f'VSOURCE_{leg} SOURCE_{leg} {node} 0\nVSINK_{leg} {node} SINK_{leg} 0\n'
            network+=f'RBLEED_{leg} {node} VSS 1e6\n'
            network+=f'CCORE_{leg} {core_prefix}_{leg} VSS .1p\n'
            network+=f'VEXT_{leg} EXT_{leg} 0 SIN(0 {sign*.0025} {frequency})\n'
            network+=f'RLOAD_{leg} EXT_{leg} BOARD_{leg} {load}\n'
        else:
            network+=f'VEXT_{leg} EXT_{leg} 0 SIN(0 {sign*peak/2} {frequency})\n'
            network+=f'RSOURCE_{leg} EXT_{leg} BOARD_{leg} {source_r}\n'
            if not ref:
                match=architecture['blocks']['lna']['parameters']['input_match_ohm_differential']/2
                network+=f'RCORE_{leg} {core_prefix}_{leg} VCM {match}\n'
            # Receiver input device loading remains explicit and separate
            # from the extracted pad. It must be replaced by the real core.
            network+=f'CCORE_{leg} {core_prefix}_{leg} VSS .1p\n'
        if external_series_l_h:
            esr=2*np.pi*frequency*external_series_l_h/external_inductor_q
            network+=f'CCOUPLE_{leg} BOARD_{leg} MATCH_{leg} {coupling}\n'
            network+=f'RMATCH_{leg} MATCH_{leg} MATCH_L_{leg} {esr}\n'
            network+=f'LMATCH_{leg} MATCH_L_{leg} CAP_{leg} {external_series_l_h}\n'
        else:
            network+=f'CCOUPLE_{leg} BOARD_{leg} CAP_{leg} {coupling}\n'
        # The shared reference source_r already includes its series loss.
        # Do not add the independent RF fixture's 1 ohm on top of that.
        if ref:bond_start=f'CAP_{leg}'
        else:
            network+=f'RBOND_{leg} CAP_{leg} BOND_{leg} 1\n'
            bond_start=f'BOND_{leg}'
        network+=f'LBOND_{leg} {bond_start} PAD_{leg} {bond_l}\n'
    if tx:
        # Complete the active bias draw without adding output current twice.
        # This is an explicit behavioral assumption for the intended biased
        # transconductance driver, not an extracted bias/control implementation.
        floor=f"{driver['bias_current_a']}*min(max(V(ENABLE),0),1)*min(max(V(VDD)/{nominal},0),1)"
        network+=f'BBIAS_FLOOR VDD BIAS_FLOOR_RETURN I=max(({floor})-I(VSOURCE_P)-I(VSOURCE_N),0)\n'
        network+='VBIAS_FLOOR BIAS_FLOOR_RETURN VSS 0\n'
    if mutual_l:
        network+=f'KBOND LBOND_P LBOND_N {mutual_l/bond_l}\n'
    if external_termination_ohm is not None:
        network+=f'REXTTERM BOARD_P BOARD_N {external_termination_ohm}\n'
    # Measure transfer through the actual pad + bond + coupling + core boundary,
    # rather than treating isolated pad capacitance as an RF bandwidth verdict.
    # AC operating points are independent; the retained transient below remains
    # responsible for charge history across transitions.
    transfer = {}
    for state,supply,enabled in [('active',3.3,1),('disabled',3.3,0),('unpowered',0,0)]:
        lines=[]
        for line in network.splitlines():
            if line.startswith('VDD VDD '):line=f'VDD VDD 0 {supply}'
            elif line.startswith('VEN ENABLE '):line=f'VEN ENABLE 0 {enabled}'
            for leg,sign in [('P',1),('N',-1)]:
                if line.startswith(f'VEXT_{leg} '):
                    line=f'VEXT_{leg} EXT_{leg} 0 DC 0 AC {0 if tx else sign*.5}'
                if line.startswith(f'BCORE_{leg} '):
                    line=f'VCORE_{leg} CORE_{leg} 0 DC {supply/2} AC {sign*.5}'
            lines.append(line)
        output='v(BOARD_P)-v(BOARD_N)' if tx else f'v({core_prefix}_P)-v({core_prefix}_N)'
        name='transfer_'+state
        bench='\n'.join(lines)+'\n'+control(work,name,f'ac lin 1 {frequency} {frequency}',
                    f'real({output}) imag({output})')
        row=np.atleast_2d(run_spice(work,name,bench))[0]
        amplitude=float(np.hypot(row[1],row[2]))
        sweep_name='bandwidth_'+state
        sweep_deck='\n'.join(lines)+'\n'+control(work,sweep_name,'ac dec 40 100Meg 10G',
                    f'real({output}) imag({output})')
        sweep_data=np.atleast_2d(run_spice(work,sweep_name,sweep_deck))
        magnitude=np.hypot(sweep_data[:,1],sweep_data[:,2])
        maximum=int(np.argmax(magnitude))
        broadband=dict(start_hz=float(sweep_data[0,0]),stop_hz=float(sweep_data[-1,0]),
            points=len(sweep_data),peak_frequency_hz=float(sweep_data[maximum,0]),
            peak_magnitude_v_per_v=float(magnitude[maximum]),
            minimum_magnitude_v_per_v=float(magnitude.min()),
            frequency_hz=sweep_data[:,0].tolist(),magnitude_v_per_v=magnitude.tolist(),
            phase_deg=np.degrees(np.unwrap(np.arctan2(sweep_data[:,2],sweep_data[:,1]))).tolist(),
            scope='Nominal small-signal sweep only; lumped package probes and behavioral core boundary, no process/package tolerance or extracted distributed resistance.')
        transfer[state]=dict(frequency_hz=float(row[0]),magnitude_v_per_v=amplitude,
            gain_db=float(20*np.log10(max(amplitude,1e-300))),bandwidth_sweep=broadband,
            phase_deg=float(np.degrees(np.arctan2(row[2],row[1]))),
            scope='Independent linearized operating point with actual pad and retained network topology. Unit differential core stimulus for TX, external stimulus for RX/reference; disabled TX command transfer is zero by construction; missing driver parasitic feedthrough is not isolation evidence. Core impedances remain declared assumptions.')
    bias_vector='i(VBIAS)' if finite_bias else 'i(BVCM)'
    vectors=f'v(PAD_P) v(PAD_N) v(VCM) i(VSS) i(VDD) v({core_prefix}_P) v({core_prefix}_N) {bias_vector}'
    if finite_bias:vectors+=' i(VBIAS_SOURCE_I) i(VBIAS_SINK_I) v(VDD) v(VCM_TARGET)'
    if tx:vectors+=' i(VSOURCE_P) i(VSINK_P) i(VSOURCE_N) i(VSINK_N) v(BOARD_P) v(BOARD_N) v(EXT_P) v(EXT_N) v(VDD) i(VBIAS_FLOOR)'
    retained_network=network
    network+=control(work,'lifecycle','tran 2p 80n',vectors)
    x=run_spice(work,'lifecycle',network)
    if finite_bias:x[:,8]*=-1  # match voltage-source sink-positive convention
    if x.shape[1]!=(19 if tx else 13 if finite_bias else 9):raise ValueError('Analog vector column mismatch')
    if not np.isfinite(x).all():raise ValueError('Nonfinite analog lifecycle')
    windows={'active':(4,11),'disabled':(14,19),'reset':(22,27),'unpowered':(32,39),
             'brownout':(43,47),'reconfiguration':(48,60),'reactivated':(65,79)}
    states={}
    # Voltage-source current is positive into the source. Sum clipped leg
    # currents separately: signed differential currents can cancel.
    def boundary_current(data):
        if tx:
            return dict(peak_source_current_a=float(np.max(data[:,9]+data[:,11])),
                        peak_sink_current_a=float(np.max(data[:,10]+data[:,12])),
                        peak_supply_source_current_a=float(np.max(-data[:,5])),
                        mean_supply_draw_a=float(np.trapezoid(-data[:,5],data[:,0])/(data[-1,0]-data[0,0])),
                        mean_bias_completion_current_a=float(np.trapezoid(data[:,18],data[:,0])/(data[-1,0]-data[0,0])))
        currents=data[:,8:9]
        return dict(peak_source_current_a=float(np.max(np.maximum(-currents,0).sum(axis=1))),
                    peak_sink_current_a=float(np.max(np.maximum(currents,0).sum(axis=1))),
                    peak_vcm_source_current_a=float(np.max(np.maximum(-data[:,8],0))),
                    peak_vcm_sink_current_a=float(np.max(np.maximum(data[:,8],0))))
    for name,(a,b) in windows.items():
        data=x[(x[:,0]>=a*1e-9)&(x[:,0]<=b*1e-9)]
        if len(data)<2 or x[-1,0]<b*1e-9:
            states[name]=dict(status='not_reached_by_transient',samples=len(data));continue
        states[name]=dict(status='window_reached_not_acceptance',samples=len(data),pad_min_v=float(data[:,1:3].min()),
                          pad_max_v=float(data[:,1:3].max()),
                          core_common_mode_min_v=float(((data[:,6]+data[:,7])/2).min()),
                          core_common_mode_max_v=float(((data[:,6]+data[:,7])/2).max()),
                          bias_min_v=float(data[:,3].min()),bias_max_v=float(data[:,3].max()),
                          differential_pp_v=float(np.ptp(data[:,1]-data[:,2])),
                          core_differential_pp_v=float(np.ptp(data[:,6]-data[:,7])),
                          attached_core_source_demand=boundary_current(data),
                          peak_pad_and_core_return_current_a=float(np.max(abs(data[:,4]))))
    report=dict(status='extracted_capacitance_pad_with_behavioral_core_boundary',family=family,
                signal_route_model=route_evidence,
                capacitance_f_per_leg=caps,
                dc=dc_summary,
                assigned_budget_f_per_leg=circuit.requirements['electrical_parameters']['capacitance_f_per_leg'],
                finite_rx_bias=finite_bias,finite_tx_driver=finite_tx,tx_power_target=tx_target,
                attached_core_source_demand=dict(whole_transient=boundary_current(x),
                    scope=('Finite RX bias output current; excludes passive bleed/displacement. Not a transistor implementation.' if finite_bias else 'Finite supply-connected TX branch currents, summed without cancellation; behavioral capacity is unqualified.' if tx else 'Ideal reference bias-source demand; not implemented supply current.')),
                states=states,transfer_at_carrier=transfer,transient_complete=bool(x[-1,0]>=79.99e-9),
                assumptions=dict(frequency_hz=frequency,source_differential_peak_v=peak,
                                 external_coupling_f=coupling,bond_h_per_leg=bond_l,
                                 external_series_matching=dict(inductance_h_per_leg=external_series_l_h,assumed_q_at_carrier=external_inductor_q,series_resistance_ohm_per_leg=2*np.pi*frequency*external_series_l_h/external_inductor_q,scope='Fixed series L and R retained in all states; Q is a design assumption, not a selected component. Self-resonance and board parasitics remain absent.'),
                                 coupling_scope='Ideal board capacitor; component ESR/ESL and board traces remain unmodeled. Default RF100pF, reference10nF; fixed throughout each run.',
                                 mutual_bond_h=mutual_l,source_r_ohm_per_leg=source_r if not tx else None,
                                 package_source='shared_reference_input_package' if ref else 'declared_RF_package_probe',
                                 external_differential_termination_ohm=external_termination_ohm,
                                 bond_r_ohm_per_leg=0 if ref else 1,core_load_f_per_leg=.1e-12),
                limitations=[
                    'Physical pad devices and extracted capacitance are connected; full distributed interconnect R is absent. Optional segmented metal estimate is identified separately.',
                    'Capacitance/DC probes leave the attached core absent; transfer/lifecycle probes include its declared load.',
                    'Core input capacitance, finite off impedance and bias behavior are declared fixtures, not extracted core circuitry.',
                    'Reference bias remains ideal; RX bias and TX output use finite supply-connected boundaries. TX command sources carry no load. None is implemented core circuitry.',
                    'Differential RF match does not establish common-mode or DC impedance. The split resistive RX fixture remains a conservative loading assumption, not the planned common-source LNA topology.',
                    'Passive pad has no digital reset; disabled/reset differ only through the attached core controls.',
                    'External network and capacitor/inductor state persist through all transitions.',
                    'An 80ns run does not establish slow bias/coupling settling: 10nF with the reference bias path has an approximately millisecond time constant.',
                    'Odd/common capacitance includes protection and physical wiring; do not add the assigned budget again.',
                    'VSS current includes displacement and declared core-load current, not only protection conduction.',
                    'Input protection has no demonstrated positive ESD trigger/survival; no ESD qualification.',
                    'Receiver sensitivity, additive jitter and RF output distortion require the actual attached core.'],
                source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                               (physical,Path(__file__),Path(__file__).with_name('circuits.py'),
                                PROJECT/'spec/analog-architecture.json',PROJECT/'spec/contract.json',
                                pdk/'design.ngspice',pdk/'sm141064.spice',pdk/'sm141064.ngspice')})
    if finite_tx:
        def supply_exposure(data):
            result={}
            for name,(start,stop) in {'supply_fall':(28,30),'unpowered':(32,39),
                    'brownout':(43,47),'supply_recovery':(48,60),'recovered':(65,79)}.items():
                rows=data[(data[:,0]>=start*1e-9)&(data[:,0]<=stop*1e-9)]
                if len(rows)<2 or data[-1,0]<stop*1e-9:
                    result[name]={'status':'not_reached_by_transient'};continue
                result[name]=dict(status='exposure_measured_not_safe_stress_verdict',
                    peak_pad_above_supply_v=float(np.maximum(rows[:,1:3]-rows[:,17,None],0).max()),
                    peak_core_above_supply_v=float(np.maximum(rows[:,6:8]-rows[:,17,None],0).max()),
                    peak_core_below_ground_v=float(np.maximum(-rows[:,6:8],0).max()),
                    peak_supply_return_current_a=float(np.maximum(rows[:,5],0).max()),
                    peak_ground_return_current_a=float(abs(rows[:,4]).max()),
                    peak_source_branch_current_a=float(rows[:,[9,11]].max()),
                    peak_sink_branch_current_a=float(rows[:,[10,12]].max()))
            return result
        report['retained_supply_exposure']=supply_exposure(x)
        # One control fault; same pad, protection, charge storage and board peer.
        lines=retained_network.splitlines()
        controls=[i for i,line in enumerate(lines) if line.startswith('VEN ENABLE ')]
        if len(controls)!=1:raise ValueError('Expected one RF enable source')
        lines[controls[0]]='VEN ENABLE 0 1'
        stale_deck='\n'.join(lines)+'\n'+control(work,'stale_enable','tran 2p 80n',vectors)
        stale=run_spice(work,'stale_enable',stale_deck)
        if stale.shape[1]!=19 or not np.isfinite(stale).all():raise ValueError('Invalid RF stale-enable waveform')
        stale_error=float(np.max(abs(stale[:,5]+stale[:,9]+stale[:,11]+stale[:,18])))
        stale_peak=float(stale[:,9:13].max())
        if stale_error>1e-10 or stale_peak>finite_tx['current_limit_a_per_leg']*(1+1e-6):
            raise ValueError('RF stale-enable branch limit or rail accounting failure')
        report['stale_enable_diagnostic']=dict(transient_complete=bool(stale[-1,0]>=79.99e-9),
            last_time_s=float(stale[-1,0]),supply_current_accounting_error_a=stale_error,
            maximum_branch_current_a=stale_peak,exposure=supply_exposure(stale),
            scope='Enable request held high through supply collapse, brownout and recovery. Only VEN differs from nominal retained network. The behavioral rail/headroom gates are not an implemented supervisor; absent driver reverse junctions prevent a power-off safety claim.')
        error=float(np.max(abs(x[:,5]+x[:,9]+x[:,11]+x[:,18])))
        maximum=float(np.max(x[:,9:13]))
        if error>1e-10 or maximum>finite_tx['current_limit_a_per_leg']*(1+1e-6):
            raise ValueError('TX rail accounting or branch current limit violated')
        report['finite_tx_driver'].update(supply_current_accounting_error_a=error,
            maximum_branch_current_a=maximum)
        # Integer carrier periods and uniform interpolation avoid weighting
        # adaptive SPICE steps as if they were uniformly spaced samples.
        measurements={}
        for name in ('active','reactivated'):
            start,stop=windows[name]
            cycles=int(np.floor((stop-start)*1e-9*frequency))
            if cycles<1 or x[-1,0]<stop*1e-9:
                measurements[name]={'status':'insufficient_retained_waveform'};continue
            count=cycles*128
            times=start*1e-9+np.arange(count)/(128*frequency)
            drop=x[:,13]-x[:,14]-x[:,15]+x[:,16]
            voltage=np.interp(times,x[:,0],drop)
            centered=voltage-voltage.mean()
            phase=2*np.pi*frequency*times
            harmonics=[float(np.hypot(2*np.mean(centered*np.cos(k*phase)),
                                     2*np.mean(centered*np.sin(k*phase)))) for k in range(1,6)]
            load=driver['load_ohm_differential']
            fundamental=harmonics[0]**2/(2*load)
            measurements[name]=dict(status='measured_not_compliance',cycles=cycles,
                fundamental_differential_peak_v=harmonics[0],
                fundamental_power_w=fundamental,
                fundamental_power_dbm=float(10*np.log10(max(fundamental,1e-300)/1e-3)),
                differential_ac_power_w=float(np.mean(centered**2)/load),
                target_power_ratio=fundamental/tx_target['target_mean_power_w'],
                meets_target_power=bool(fundamental>=tx_target['target_mean_power_w']),
                harmonic_peak_v=harmonics,
                harmonics_2_to_5_ratio=float(np.linalg.norm(harmonics[1:])/max(harmonics[0],1e-300)))
        report['tx_load_power']=dict(windows=measurements,
            scope='Differential voltage across the actual external resistors, subtracting the retained peer-source voltage. Excludes common-mode dissipation. Integer-cycle tone measurement with interpolation; not EVM, spectral-mask or modulated-power qualification.')

    if finite_bias:
        accounting_error=float(np.max(abs(x[:,8]-(x[:,10]-x[:,9]))))
        supply_error=float(np.max(abs(x[:,5]+x[:,9])))
        if max(accounting_error,supply_error)>1e-10:
            raise ValueError('RX finite bias source/rail accounting mismatch')
        report['finite_rx_bias'].update(
            bias_current_accounting_error_a=accounting_error,
            supply_current_accounting_error_a=supply_error,
            peak_supply_source_current_a=float(np.max(x[:,9])),
            peak_ground_sink_current_a=float(np.max(x[:,10])),
            source_current_limit_observed=bool(np.max(x[:,9])<=limit*(1+1e-6)),
            sink_current_limit_observed=bool(np.max(x[:,10])<=limit*(1+1e-6)),
            peak_bias_target_error_v=float(np.max(abs(x[:,3]-x[:,12]))),
            peak_core_input_above_supply_v=float(np.max(x[:,6:8]-x[:,11,None])),
            bias_endpoint_v=float(x[-1,3]))
    if ref:
        # Separate slow bias dynamics from GHz carrier steps, retaining every
        # device and external storage element. Start genuinely unpowered.
        target = architecture['blocks']['refpad']['parameters']['common_mode_v']
        supply = 2*target
        tau = architecture['blocks']['refpad']['parameters']['input_r_ohm'] * coupling
        rise = tau/100
        off = 8*tau + 2*rise
        on = off + 8*tau + rise
        stop = on + 8*tau + rise
        lines = []
        for line in retained_network.splitlines():
            if line.startswith('VDD VDD '):
                line = (f'VDD VDD 0 PWL(0 0 {rise} 0 {2*rise} {supply} '
                        f'{off} {supply} {off+rise} 0 {on} 0 {on+rise} {supply} {stop} {supply})')
            elif line.startswith('VEN ENABLE '):
                line = 'VEN ENABLE 0 0'
            elif line.startswith(('VEXT_P ', 'VEXT_N ')):
                line = ' '.join(line.split()[:3])+' 0'
            lines.append(line)
        slow = run_spice(work, 'reference_bias_envelope', '\n'.join(lines)+'\n'+
                         control(work, 'reference_bias_envelope', f'tran {tau/100} {stop}', vectors))
        if not np.isfinite(slow).all() or slow[-1,0] < stop*(1-1e-9):
            raise ValueError('Incomplete reference bias envelope')
        target = architecture['blocks']['refpad']['parameters']['common_mode_v']
        cm = .5*(slow[:,1]+slow[:,2])
        def settled(start, end):
            indices = np.flatnonzero((slow[:,0]>=start)&(slow[:,0]<=end))
            bad = np.flatnonzero(abs(cm[indices]-target)>.01*target)
            i = int(bad[-1]+1) if len(bad) else 0
            return float(slow[indices[i],0]-start) if i<len(indices) else None
        report['reference_bias_envelope'] = dict(
            scope='Same extracted pad, numerical anchor and external network; carrier removed and enable held low. One-percent settling is a diagnostic, not an allocated clock-ready deadline. Ideal bias source remains.',
            transient_complete=True, estimated_rc_s=tau,
            cold_settling_to_one_percent_s=settled(2*rise,off),
            restored_settling_to_one_percent_s=settled(on+rise,stop),
            bias_before_power_off_v=float(np.interp(off,slow[:,0],cm)),
            bias_after_unpowered_interval_v=float(np.interp(on,slow[:,0],cm)),
            final_common_mode_v=float(cm[-1]),
            source_sha256=hashlib.sha256((work/'reference_bias_envelope.spice').read_bytes()).hexdigest())
    if finite_bias:
        # Carrier-free common-mode diagnostic: preserve every device, load and
        # storage element, but remove the RF stimulus to span bias time scales.
        guard=architecture['blocks']['bias']['parameters']['startup_guard_s']
        charge_time=2*coupling*(nominal/2)/limit
        discharge_tau=bleed*2*coupling
        rise=guard/20
        step=min(guard/10,charge_time/50)
        power_off=max(10*guard,5*charge_time)
        power_on=power_off+rise+6*discharge_tau
        stop=power_on+rise+power_off
        lines=[]
        for line in retained_network.splitlines():
            if line.startswith('VDD VDD '):
                line=(f'VDD VDD 0 PWL(0 0 {rise} 0 {2*rise} {nominal} '
                      f'{power_off} {nominal} {power_off+rise} 0 '
                      f'{power_on} 0 {power_on+rise} {nominal} {stop} {nominal})')
            elif line.startswith('VEN ENABLE '):line='VEN ENABLE 0 0'
            elif line.startswith(('VEXT_P ','VEXT_N ')):
                fields=line.split();line=' '.join(fields[:3])+' 0'
            lines.append(line)
        slow_deck='\n'.join(lines)+'\n'+control(work,'bias_envelope',
                    f'tran {step} {stop}',vectors)
        slow=run_spice(work,'bias_envelope',slow_deck)
        if slow.shape[1]!=13 or not np.isfinite(slow).all():raise ValueError('Invalid slow-bias data')
        def at(t):return float(np.interp(t,slow[:,0],slow[:,3]))
        def settled(start,end):
            section=slow[(slow[:,0]>=start)&(slow[:,0]<=end)]
            bad=np.flatnonzero(abs(section[:,3]-nominal/2)>.01*nominal/2)
            index=int(bad[-1]+1) if len(bad) else 0
            return float(section[index,0]-start) if index<len(section) else None
        report['finite_rx_bias']['common_mode_envelope']=dict(
            scope='Same connected circuit and external network; carrier removed, enable held low. DC/common-mode startup/discharge diagnostic only, not RF acquisition or timing qualification.',
            transient_complete=bool(slow[-1,0]>=stop*(1-1e-9)),
            nominal_step_s=step,supply_rise_s=rise,
            unpowered_duration_s=6*discharge_tau,
            reference_startup_guard_s=guard,
            bias_at_guard_after_full_supply_v=at(2*rise+guard),
            cold_time_to_stay_within_one_percent_s=settled(2*rise,power_off),
            restored_time_to_stay_within_one_percent_s=settled(power_on+rise,stop),
            bias_before_power_off_v=at(power_off),
            bias_after_unpowered_interval_v=at(power_on),
            bias_endpoint_v=float(slow[-1,3]),
            source_current_limit_observed=bool(slow[:,9].max()<=limit*(1+1e-6)),
            sink_current_limit_observed=bool(slow[:,10].max()<=limit*(1+1e-6)),
            peak_supply_source_current_a=float(slow[:,9].max()),
            peak_ground_sink_current_a=float(slow[:,10].max()),
            ideal_charge_time_lower_estimate_s=charge_time,
            off_discharge_time_constant_estimate_s=discharge_tau)
    if finite_bias and external_coupling_f is None and route_report is None:
        report['large_coupling_diagnostic']=screen(work/'large-coupling',pdk,physical,family,
            external_coupling_f=10e-9)
    report['numerical_floating_conductor_anchors'] = anchors
    helper = Path(__file__).with_name('loading_audit.py')
    report['source_sha256'][str(helper)] = hashlib.sha256(helper.read_bytes()).hexdigest()
    report['source_sha256'][str(Path(__file__).with_name('screen.py'))] = hashlib.sha256(Path(__file__).with_name('screen.py').read_bytes()).hexdigest()
    report['operating_point_policy'] = 'Capacitor-only internal metal receives a declared numerical DC anchor; reject transient operating-point fallback. Anchors are not fabricated resistors.'
    (work/'screen-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(family=family,capacitance_f_per_leg=caps,states=states),indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--family',choices=('reference_clock','rf_receive','rf_transmit'),required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--physical',type=Path,required=True)
    p.add_argument('--pdk-model-dir',type=Path,required=True)
    p.add_argument('--external-differential-termination-ohm',type=float)
    p.add_argument('--external-coupling-f',type=float)
    p.add_argument('--route-report',type=Path)
    p.add_argument('--numerical-anchor-resistance',type=float,default=1e12)
    p.add_argument('--rf-tx-gain',type=float)
    p.add_argument('--external-series-l-h',type=float,default=0.)
    p.add_argument('--external-inductor-q',type=float,default=30.)
    p.add_argument('--capacitance-location',choices=('bond','core'),default='bond')
    p.add_argument('--resistance-corner',choices=('nominal','high_resistance','low_resistance'),default='nominal')
    a=p.parse_args()
    screen(a.output_dir.resolve(),a.pdk_model_dir.resolve(),a.physical.resolve(),a.family,
           a.external_differential_termination_ohm,route_report=a.route_report,
           capacitance_location=a.capacitance_location,resistance_corner=a.resistance_corner,
           external_coupling_f=a.external_coupling_f,rf_tx_gain=a.rf_tx_gain,
           external_series_l_h=a.external_series_l_h,external_inductor_q=a.external_inductor_q,numerical_anchor_resistance=a.numerical_anchor_resistance)
