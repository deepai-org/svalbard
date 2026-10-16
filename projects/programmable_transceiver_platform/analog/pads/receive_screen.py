"""Connected RX/USB pad screens; retained external network through state changes."""
import hashlib
import json
from pathlib import Path
import numpy as np
from wired_receive import build
import receive_core
from receive_controls import attach as attach_control_guard
from design import PROJECT
from screen import header, control, run_spice


def screen(work,pdk,physical=None):
    work.mkdir(parents=True,exist_ok=True)
    circuit=build()
    probe_prefix="xpad.xphysical" if physical and any(l.startswith("XPHYSICAL ") for l in physical.read_text().splitlines()) else "xpad"
    architecture=json.loads((PROJECT/'spec/analog-architecture.json').read_text())
    core_cap=architecture['blocks']['rxlevel']['parameters']['output_cap_budget_f_per_leg']
    controls=[p for p in circuit.ports if p not in ('PAD_P','PAD_N','VDD','VSS','RX_P','RX_N')]
    def fixture(overrides=None):
        values={'HS_PBIAS':3.3,**(overrides or {})}
        text=header(circuit,pdk,physical)+receive_core.model(physical)+'VDD VDD 0 3.3\n'
        for port in controls:text+=f'V{port} {port} 0 {values.get(port,0)}\n'
        text+=receive_core.loads(physical)
        return text
    # Dedicated static load fixtures measure each branch without conflating
    # current in gate-discharge resistors with current delivered at the bond.
    measured={}
    for name,settings in [('off',{}),('term',{'TERM_ENABLE':3.3}),
                          ('fs_high',{'FS_HIGH_P':3.3}),('fs_low',{'FS_LOW_P':3.3}),
                          ('pullup',{'PULLUP_P':3.3}),('pulldown',{'PULLDOWN_P':3.3}),
                          ('divider',{'DIV_ENABLE':3.3}),('bypass',{'BYPASS_ENABLE':3.3})]:
        deck=fixture(settings)+'VPADP PAD_P 0 0\nVPADN PAD_N 0 0\n'
        deck+=control(work,name,'dc VPADP 0 3.6 .02','i(VPADP) v(RX_P) i(VDD)')
        data=run_spice(work,name,deck)
        i=int(np.argmin(abs(data[:,0]-(3.2 if name in ('fs_high','pullup') else .2))))
        slope=-(data[i+1,1]-data[i-1,1])/(data[i+1,0]-data[i-1,0])
        measured[name]=dict(small_signal_ohm=float(1/slope),at_pad_v=float(data[i,0]),
            receiver_v_at_3v3=float(data[np.argmin(abs(data[:,0]-3.3)),2]),
            peak_abs_pad_current_a=float(max(abs(data[:,1]))),peak_supply_backfeed_a=float(max(0,max(data[:,3]))))
    shared_low_controls={}
    for name,term,pull_p,pull_n in [('off',0,0,0),('p_only',0,1,0),('n_only',0,0,1),('both',0,1,1),('termination',1,0,0)]:
        deck=fixture({'TERM_ENABLE':3.3*term,'FS_LOW_P':3.3*pull_p,'FS_LOW_N':3.3*pull_n})
        deck+='VPADP PAD_P 0 .2\nVPADN PAD_N 0 .2\n'
        run='shared_low_'+name;deck+=control(work,run,'op','i(VPADP) i(VPADN)')
        row=np.atleast_2d(run_spice(work,run,deck))[0]
        shared_low_controls[name]=dict(ground_bias_v=0,pad_p_sink_a=float(-row[1]),pad_n_sink_a=float(-row[2]),
            requested_p=bool(term or pull_p),requested_n=bool(term or pull_n))
    deck=fixture({'FS_LOW_P':3.3,'TERM_VCM':1.65})+'VPADP PAD_P 0 .2\nVPADN PAD_N 0 .2\n'
    deck+=control(work,'shared_low_wrong_bias','op','i(VPADP) i(VPADN) i(VTERM_VCM)')
    row=np.atleast_2d(run_spice(work,'shared_low_wrong_bias',deck))[0]
    shared_low_controls['wrong_bias_diagnostic']=dict(common_mode_v=1.65,pad_p_sink_a=float(-row[1]),pad_n_sink_a=float(-row[2]),
        scope='Invalid USB bias with a lone FS-low request. Physical bias qualification should block this branch; TERM_ENABLE conflicts and dynamic trip behavior need separate checks.')
    deck=fixture({'FS_LOW_P':3.3})+'VPADP PAD_P 0 .2\nVPADN PAD_N 0 .2\n'
    deck+=control(work,'bias_qualification_dc','dc VTERM_VCM 0 2.4 .01',
                  f'v({probe_prefix}.VCM_LOW_OK) v({probe_prefix}.TERM_GATE_P) i(VPADP) i(VDD)')
    qualification=run_spice(work,'bias_qualification_dc',deck)
    crossing=int(np.argmin(abs(qualification[:,1]-1.65)))
    bias_qualification=dict(nominal_detector_midrail_crossing_v=float(qualification[crossing,0]),
        maximum_static_supply_current_a=float(np.maximum(-qualification[:,4],0).max()),
        scope='Nominal 3.3V supply, 27C, DC sweep. Skewed CMOS inverter, not a precision ground detector; process/temperature trip range and low-bias validity remain unqualified.')
    differential={}
    for enabled in (False,True):
        for common_mode in (1.0,1.65,2.0):
            name=f'differential_{int(enabled)}_{common_mode}'
            deck=fixture({'DIFF_ENABLE':3.3 if enabled else 0})
            deck+=f'VCMDIFF CM_DIFF 0 {common_mode}\nVDIFF D_DIFF 0 0\n'
            deck+='BPADP PAD_P 0 V=V(CM_DIFF)+V(D_DIFF)/2\nBPADN PAD_N 0 V=V(CM_DIFF)-V(D_DIFF)/2\n'
            deck+=control(work,name,'dc VDIFF -.1 .1 .002','i(BPADP) i(BPADN)')
            rows=run_spice(work,name,deck);center=int(np.argmin(abs(rows[:,0])))
            current=-(rows[:,1]-rows[:,2])/2
            conductance=(current[center+1]-current[center-1])/(rows[center+1,0]-rows[center-1,0])
            differential[name]=dict(enabled=enabled,common_mode_v=common_mode,
                differential_ohm=float(1/conductance),target_ohm=architecture['blocks']['termination']['parameters']['differential_ohm'],
                scope='Complete connected circuit DC slope with shunts disabled; switch headroom, trim and mutual exclusion remain unqualified.')
    loading={}
    for name,settings in [('disabled',{}),('serial_bypass',{'BYPASS_ENABLE':3.3}),
                          ('usb_terminated',{'TERM_ENABLE':3.3}),('differential_terminated',{'DIFF_ENABLE':3.3})]:
        deck=fixture(settings)+'VPADP PAD_P 0 DC 1.65 AC .5\nVPADN PAD_N 0 DC 1.65 AC -.5\n'
        deck+=control(work,'loading_'+name,'ac lin 1 1G 1G','imag(i(VPADP)) imag(i(VPADN))')
        row=np.atleast_2d(run_spice(work,'loading_'+name,deck))[0]
        loading[name]=dict(frequency_hz=1e9,common_mode_v=1.65,
            odd_mode_effective_capacitance_f_per_leg=[float(-row[1]/(2*np.pi*1e9*.5)),float(row[2]/(2*np.pi*1e9*.5))],
            budget_f_per_leg=circuit.requirements['electrical_parameters']['capacitance_f_per_leg'])
    power_off={}
    for stale in (False,True):
        deck=fixture({'FS_HIGH_P':3.3,'PULLUP_N':3.3} if stale else {})
        deck=deck.replace('VDD VDD 0 3.3','VDD VDD 0 0').replace('VHS_PBIAS HS_PBIAS 0 3.3','VHS_PBIAS HS_PBIAS 0 0')
        deck+='VPADP PAD_P 0 3.3\nVPADN PAD_N 0 3.3\n'
        name='power_off_stale' if stale else 'power_off_safe'
        deck+=control(work,name,'op','i(VDD) i(VPADP) i(VPADN)')
        row=np.atleast_2d(run_spice(work,name,deck))[0]
        power_off[name]=dict(supply_backfeed_a=float(row[1]),pad_p_current_a=float(row[2]),pad_n_current_a=float(row[3]))
    target=architecture['blocks']['usbhs']['parameters']['drive_current_a']
    deck=fixture({'HS_P':3.3})+'VPADP PAD_P 0 .4\nVPADN PAD_N 0 .4\n'
    deck+=control(work,'hs_bias','dc VHS_PBIAS 0 3.3 .01','i(VPADP)')
    data=run_spice(work,'hs_bias',deck);index=int(np.argmin(abs(data[:,1]-target)))
    bias=float(data[index,0]);calibration=dict(bias_v=bias,current_a=float(data[index,1]),target_a=target)
    def pwl(points):return 'PWL('+' '.join(f'{t}n {v}' for t,v in points)+')'
    deck=header(circuit,pdk,physical)+receive_core.model(physical)
    deck+='VDD VDD 0 '+pwl([(0,3.3),(36,3.3),(37,0),(48,0),(49,1.5),(60,1.5),(61,3.3),(100,3.3)])+'\n'
    spans={'DIFF_ENABLE':(16,24),'DIV_ENABLE':(4,12),'BYPASS_ENABLE':(16,24),'TERM_ENABLE':(66,74),
           'FS_HIGH_P':(78,86),'FS_LOW_N':(78,86),'PULLUP_P':(90,96),'PULLDOWN_N':(90,96),
           'HS_P':(66,74)}
    for port in controls:
        if port=='HS_PBIAS':deck+=f'B{port} {port} 0 V=V(VDD)-{3.3-bias}*V(E_HS_P)\n';continue
        if port=='TERM_VCM':deck+=f'V{port} {port} 0 0\n';continue
        a,b=spans.get(port,(102,104))
        deck+=f'VE_{port} E_{port} 0 '+pwl([(0,0),(a,0),(a+.2,1),(b,1),(b+.2,0)])+'\n'
        deck+=f'B{port} {port} 0 V=V(VDD)*V(E_{port})\n'
    for leg in ('P','N'):
        deck+=f'VEXT_{leg} EXT_{leg} 0 3.3\nRPULL_{leg} EXT_{leg} BOARD_{leg} 1500\n'
        deck+=f'RLOAD_{leg} BOARD_{leg} 0 15000\nCBOARD_{leg} BOARD_{leg} 0 10p\n'
        deck+=f'RBOND_{leg} BOARD_{leg} BOND_{leg} 1\nLBOND_{leg} BOND_{leg} PAD_{leg} 1n\n'
    deck+=receive_core.loads(physical)
    raw_lifecycle_network=deck
    deck=attach_control_guard(deck,
        pwl([(0,0),(31,0),(31.2,3.3),(35,3.3),(35.2,0),(100,0)]),'3.3')
    deck+=control(work,'lifecycle','tran 20p 100n','v(PAD_P) v(PAD_N) v(RX_P) v(RX_N) i(VDD)')
    data=run_spice(work,'lifecycle',deck)
    if data[-1,0]<99.99e-9 or not np.isfinite(data).all():raise ValueError('RX/USB lifecycle incomplete or nonfinite')
    states={}
    for name,(a,b) in dict(active_divider=(6,11),active_bypass=(18,23),disabled=(27,30),reset=(32,35),
                           unpowered=(40,47),brownout=(52,59),reconfiguration=(64,68),
                           active_hs=(70,73),active_fs=(82,85),active_pulls=(93,95)).items():
        x=data[(data[:,0]>=a*1e-9)&(data[:,0]<=b*1e-9)]
        states[name]=dict(pad_min_v=float(x[:,1:3].min()),pad_max_v=float(x[:,1:3].max()),
            receiver_min_v=float(x[:,3:5].min()),receiver_max_v=float(x[:,3:5].max()),
            peak_supply_backfeed_a=float(max(0,x[:,5].max())))
    # Same retained board/load network, now keep high-side requests asserted
    # through actual power collapse. This tests the local devices rather than
    # relying on supply-scaled ideal enable sources to turn the switches off.
    adverse=(raw_lifecycle_network+control(work,'stale_lifecycle','tran 20p 100n',
        'v(PAD_P) v(PAD_N) v(RX_P) v(RX_N) i(VDD)')).replace('BFS_HIGH_P FS_HIGH_P 0 V=V(VDD)*V(E_FS_HIGH_P)',
                         'BFS_HIGH_P FS_HIGH_P 0 V=3.3')
    adverse=adverse.replace('BPULLUP_N PULLUP_N 0 V=V(VDD)*V(E_PULLUP_N)',
                            'BPULLUP_N PULLUP_N 0 V=3.3')
    adverse=adverse.replace(str(work/'lifecycle.dat'),str(work/'stale_lifecycle.dat'))
    rows=run_spice(work,'stale_lifecycle',adverse)
    if rows[-1,0]<99.99e-9 or not np.isfinite(rows).all():raise ValueError('RX/USB stale-enable lifecycle incomplete or nonfinite')
    off=rows[(rows[:,0]>=37e-9)&(rows[:,0]<=48e-9)]
    settled=rows[(rows[:,0]>=45e-9)&(rows[:,0]<=48e-9)]
    retained_stale=dict(transient_complete=True,last_time_s=float(rows[-1,0]),peak_unpowered_supply_backfeed_a=float(max(0,off[:,5].max())),
        late_unpowered_supply_backfeed_a=float(max(0,settled[:,5].max())),
        positive_charge_into_supply_c=float(np.trapezoid(np.maximum(off[:,5],0),off[:,0])),
        scope='Deliberate control-guard bypass: high-side requests held at3.3V through the same retained network and supply trajectory; tests raw pad devices, includes displacement current.')
    # Retain the lifecycle network and inject only a wrong TERM_VCM while
    # the ordinary FS-low request remains asserted. Stored charge is retained.
    qualified=deck.split('.control')[0]
    original_bias='VTERM_VCM TERM_VCM 0 0'
    if qualified.count(original_bias)!=1:raise ValueError('Expected one termination bias source')
    qualified=qualified.replace(original_bias,'VTERM_VCM TERM_VCM 0 '+pwl(
        [(0,0),(79,0),(79.2,1.65),(85.8,1.65),(86,0),(100,0)]))
    qualified+=control(work,'bias_qualification_retained','tran 20p 100n',
        f'v(PAD_N) v(TERM_VCM) v({probe_prefix}.VCM_LOW_OK) v({probe_prefix}.TERM_GATE_N) i(VTERM_VCM)')
    q=run_spice(work,'bias_qualification_retained',qualified)
    bad=q[(q[:,0]>=83e-9)&(q[:,0]<=85e-9)]
    transition=q[(q[:,0]>=79e-9)&(q[:,0]<=86.5e-9)]
    if q[-1,0]<99.99e-9 or len(bad)<2:raise ValueError('Bias qualification did not complete retained lifecycle')
    high=q[(q[:,0]>=79.2e-9)&(q[:,0]<=85.8e-9)]
    above=np.flatnonzero(high[:,4]>.33)
    delay=(float(high[above[-1]+1,0]-79.2e-9) if len(above) and above[-1]+1<len(high) else 0. if not len(above) else None)
    bias_qualification['retained_fault']=dict(gate_low_threshold_v=.33,gate_low_settling_delay_after_bias_rise_s=delay,
        transient_complete=True,last_time_s=float(q[-1,0]),
        settled_wrong_bias_gate_max_v=float(bad[:,4].max()),
        settled_wrong_bias_source_current_a=float(np.maximum(-bad[:,5],0).max()),
        transition_peak_bias_source_current_a=float(np.maximum(-transition[:,5],0).max()),
        transition_peak_bias_sink_current_a=float(np.maximum(transition[:,5],0).max()),
        scope='Only TERM_VCM trajectory differs from normal retained lifecycle. A lone FS-low request is still high; asynchronous detector delay and stored-charge current remain visible. Not a complete mode interlock or stress qualification.')
    # Adversarial requests pass through the same guard and physical network.
    conflict_deck=deck.split('.control')[0]
    original='BFS_LOW_P REQ_FS_LOW_P 0 V=V(VDD)*V(E_FS_LOW_P)'
    assert conflict_deck.count(original)==1
    conflict_deck=conflict_deck.replace(original,
        'BFS_LOW_P REQ_FS_LOW_P 0 V=V(VDD)*V(E_FS_HIGH_P)')
    conflict_deck+=control(work,'control_conflict','tran 20p 100n',
        'v(PAD_CONFLICT) v(FS_HIGH_P) v(FS_LOW_P) v(PAD_RESET) v(DIV_ENABLE)')
    checked=run_spice(work,'control_conflict',conflict_deck)
    active_conflict=checked[(checked[:,0]>=82e-9)&(checked[:,0]<=85e-9)]
    assert checked[-1,0]>=99.99e-9 and np.isfinite(checked).all()
    assert np.allclose(active_conflict[:,1],1) and np.allclose(active_conflict[:,2:4],0)
    control_guard=dict(integrated_in_lifecycle=True,conflict_transient_complete=True,
        same_leg_high_low_requests_inhibited=True,
        scope='Behavioral electrical exclusions and local supply/reset gating. QUALIFIED is assumed asserted; no sticky fault/requalification timing or transistor control implementation. Raw branch and stale-bypass diagnostics intentionally bypass the guard.')
    report=dict(status='candidate_branch_and_retained_state_screen_not_protocol_qualification',
        transient_complete=True,transient_last_time_s=float(data[-1,0]),
        branch_dc=measured,hs_calibration=calibration,lifecycle_states=states,control_guard=control_guard,
        loading=loading,shared_low_controls=shared_low_controls,bias_qualification=bias_qualification,differential_termination=differential,power_off_dc=power_off,retained_stale_enable=retained_stale,
        physical_capacitance_included=physical is not None,attached_receiver_core=receive_core.evidence(physical),
        assumptions=dict(external_pullup_ohm=1500,external_pulldown_ohm=15000,external_supply_v=3.3,
            board_capacitance_f=10e-12,bond_inductance_h=1e-9,bond_resistance_ohm=1,core_capacitance_f=core_cap),
        limitations=circuit.limitations+['Retained external pullups are an adverse powered-peer fixture, not a USB HS 45ohm receiver.',
            'Lifecycle includes behavioral control exclusion and a reset input; QUALIFIED is prescribed, not implemented supervisor readiness. Raw branch diagnostics deliberately bypass the guard.',
            'DC resistance is a local slope, not a broadband impedance or compliance verdict.'],
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [Path(__file__),Path(receive_core.__file__),receive_core.PRIMITIVE,receive_core.LAYOUT,Path(__file__).with_name('receive_controls.py'),Path(__file__).with_name('wired_receive.py'),Path(__file__).with_name('circuits.py'),
             Path(__file__).with_name('screen.py'),PROJECT/'spec/analog-architecture.json',
             pdk/'design.ngspice',pdk/'sm141064.ngspice',pdk/'sm141064.spice']+([physical] if physical else [])})
    (work/'screen-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(branch_dc=measured,hs_calibration=calibration),indent=2))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--pdk-model-dir',type=Path,required=True);p.add_argument('--physical',type=Path)
    a=p.parse_args();screen(a.output_dir.resolve(),a.pdk_model_dir.resolve(),a.physical.resolve() if a.physical else None)
