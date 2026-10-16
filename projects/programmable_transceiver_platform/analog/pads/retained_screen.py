"""Retained host/control and supply pads in one connected lifecycle fixture.

Reuses the existing native-GPIO instance helper and the shared host requirements.
The nominal package R/L and board load are explicit probes, not extracted values.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import numpy as np
from design import PROJECT
from retained import binding
sys.path.insert(0,str(PROJECT/'verification'))
from run_gpio_transient import output_instance


def screen(work,pdk,library,regularization_ohm=None,peer_supply='common_board',native_loading_report=None):
    if peer_supply not in ('common_board','independent'):
        raise ValueError('Unknown host peer supply arrangement')
    if work.exists() and any(work.iterdir()):
        raise FileExistsError("Use an empty output directory; stale transient files must not become evidence")
    work.mkdir(parents=True,exist_ok=True)
    native_loading=None
    if native_loading_report is not None:
        native_loading=json.loads(native_loading_report.read_text())
        if hashlib.sha256(library.read_bytes()).hexdigest()!=native_loading['augmented_library_sha256']:
            raise ValueError('Native loading report does not match supplied library')
        for source,digest in native_loading['source_sha256'].items():
            if hashlib.sha256(Path(source).read_bytes()).hexdigest()!=digest:
                raise ValueError('Stale native loading source '+source)
    selected=binding();host=selected['host_output'];voltage=host['voltage_v'];load=host['full_rate_external_load_target_f']
    ui=1/host['maximum_word_rate_hz']
    power_parameters=json.loads((PROJECT/'spec/analog-architecture.json').read_text())['blocks']['power']['parameters']
    pdn=power_parameters['reduced_pdn_model']['network']
    if any(not np.isfinite(pdn[k]) or pdn[k]<=0 for k in
           ('feed_r','feed_l','board_c','board_esr','board_esl','die_c','die_esr','die_esl')):
        raise ValueError('Shared PDN elements must be finite and positive')
    # Interpret every native cell's published port order, rather than assuming
    # core and IO supply pins are interchangeable on every library cell.
    declarations={m.group(1):m.group(2).split() for m in re.finditer(r'^\.SUBCKT\s+(\S+)\s+([^\n]+)',library.read_text(),re.M|re.I)}
    def instance(name,cell,connections):
        ports=declarations[cell]
        if set(ports)!=set(connections):raise ValueError('Incomplete native cell connection '+cell)
        return name+' '+' '.join(connections[p] for p in ports)+' '+cell+'\n'
    def pwl(points):return 'PWL('+' '.join(f'{t}n {v}' for t,v in points)+')'
    header='Retained IO and supply lifecycle\n'+f'.include {pdk}/design.ngspice\n'
    header+=''.join(f'.lib {pdk}/sm141064.ngspice {s}\n' for s in ('typical','res_typical','diode_typical','moscap_typical'))
    header+=f'.include {library}\n.temp 27\n.options method=gear maxord=2 reltol=.003 itl4=100 gmin=1e-10\n'
    if regularization_ohm is not None:
        if not np.isfinite(regularization_ohm) or regularization_ohm<=0:raise ValueError('Invalid numerical shunt')
        header+=f'.options rshunt={regularization_ohm}\n'
    # Template ties the foundry core/IO supply nets; finite parallel bond paths
    # follow all eighteen retained power/ground sites, not an invented pin count.
    network=''
    for i,site in enumerate(selected['supply_sites']):
        power=site.startswith(('dvdd_pads[','vdd_pads['))
        cell='gf180mcu_fd_io__dvdd' if power else 'gf180mcu_fd_io__dvss'
        mapping={'DVDD':'RAIL','DVSS':'RETURN',('VSS' if power else 'VDD'):('RETURN' if power else 'RAIL')}
        network+=instance(f'XPWR{i}',cell,mapping)
        a,b=('BOARD_VDD','RAIL') if power else ('RETURN','0')
        network+=f'RB{i} {a} BOND{i} .1\nLB{i} BOND{i} {b} {power_parameters["bond_l_h"]}\n'
    # Keep board and local storage attached in every state. The shared reduced
    # package resistor is not added: explicit parallel bond paths replace it.
    network+=f'RFEED SOURCE_VDD FEED_L {pdn["feed_r"]}\nLFEED FEED_L BOARD_VDD {pdn["feed_l"]}\n'
    network+=f'RBOARD_C BOARD_VDD BOARD_CR {pdn["board_esr"]}\nLBOARD_C BOARD_CR BOARD_CL {pdn["board_esl"]}\nCBOARD BOARD_CL 0 {pdn["board_c"]}\n'
    network+=f'RDIE_C RAIL DIE_CR {pdn["die_esr"]}\nLDIE_C DIE_CR DIE_CL {pdn["die_esl"]}\nCDIE DIE_CL RETURN {pdn["die_c"]}\n'
    network+='RDISCHARGE RAIL RETURN 100k\n'
    # Existing helper supplies PDRV01/SL0. Replace only its explicit control
    # and supply bindings; assert the expected port before changing it.
    output=output_instance('XOUT','DATA','PAD_OUT','UNUSED',selected['drive_ma'],'RETURN').split()
    if output[6]!='VDD':raise ValueError('Native output helper port order changed')
    output[6]='OE'
    output=['RAIL' if t in ('VDD','DVDD') else 'RETURN' if t=='0' else t for t in output]
    network+=' '.join(output)+'\nCUNUSED UNUSED RETURN 1f\n'
    network+=instance('XIN','gf180mcu_fd_io__bi_24t',dict(A='RETURN',CS='RETURN',DVDD='RAIL',DVSS='RETURN',IE='RAIL',OE='RETURN',PAD='PAD_IN',PD='RETURN',PU='RETURN',SL='RETURN',VDD='RAIL',VSS='RETURN',Y='IN_Y'))
    network+=instance('XRESET','gf180mcu_fd_io__in_c',dict(DVDD='RAIL',DVSS='RETURN',PAD='PAD_RESET',PD='RETURN',PU='RETURN',VDD='RAIL',VSS='RETURN',Y='RESET_Y'))
    for name in ('IN_Y','RESET_Y'):network+=f'C{name} {name} RETURN 20f\n'
    network+=f'RS_OUT PAD_OUT BOND_OUT 1\nLS_OUT BOND_OUT BOARD_OUT 2n\nCLOAD BOARD_OUT 0 {load}\nRPEER_OUT BOARD_OUT PEER 10000\n'
    for name in ('IN','RESET'):
        network+=f'RS_{name} PEER BOND_{name} 50\nLS_{name} BOND_{name} PAD_{name} 2n\n'
    stimuli='VBOARD SOURCE_VDD 0 '+pwl([(0,voltage),(800,voltage),(900,0),(1400,0),(1500,1.5),(1800,1.5),(2000,voltage),(3000,voltage)])+'\n'
    peer_current='EPEER' if peer_supply=='common_board' else 'VPEER'
    stimuli+=('EPEER PEER 0 SOURCE_VDD 0 1\n' if peer_supply=='common_board' else f'VPEER PEER 0 {voltage}\n')
    stimuli+=f'VBIT BIT 0 PULSE(0 1 10n .5n .5n {ui-.5e-9} {2*ui})\n'
    stimuli+='BDATA DATA RETURN V=V(RAIL,RETURN)*V(BIT)*V(ACTIVE)\n'
    stimuli+='VACTIVE ACTIVE 0 '+pwl([(0,1),(40,1),(41,0),(2940,0),(2941,1),(3000,1)])+'\n'
    stimuli+='BOE OE RETURN V=V(RAIL,RETURN)*V(ACTIVE)\n'
    deck=header+network+stimuli
    deck+='''.control
set noaskquit
set wr_singlescale
set wr_vecnames
tran 250p 3u 0 250p
'''+f'wrdata {work}/lifecycle.dat v(RAIL) v(RETURN) v(BOARD_OUT) v(IN_Y) v(RESET_Y) i(VBOARD) i({peer_current})\nquit\n.endc\n.end\n'
    (work/'.spiceinit').write_text('set ngbehavior=hs\n')
    (work/'lifecycle.spice').write_text(deck)
    result=subprocess.run(['ngspice','-b','lifecycle.spice'],cwd=work,capture_output=True,text=True,timeout=180)
    (work/'lifecycle.log').write_text(result.stdout+result.stderr);result.check_returncode()
    data=np.loadtxt(work/'lifecycle.dat',skiprows=1)
    if data.ndim!=2:raise RuntimeError('Malformed native pad transient output')
    transient_complete=bool(data[-1,0]>=2999.99e-9)
    states={}
    for name,(start,end) in dict(active=(20,39),disabled=(45,60),reset=(65,79),unpowered=(1200,1390),brownout=(1700,1790),reconfiguration=(1950,2200),recovered_active=(2960,2990)).items():
        x=data[(data[:,0]>=start*1e-9)&(data[:,0]<=end*1e-9)]
        if len(x)<2 or data[-1,0]<end*1e-9:
            states[name]=dict(status='not_reached_by_transient',samples=len(x));continue
        states[name]=dict(status='window_reached_not_acceptance',samples=len(x),local_supply_min_v=float((x[:,1]-x[:,2]).min()),local_supply_max_v=float((x[:,1]-x[:,2]).max()),
            return_min_v=float(x[:,2].min()),return_max_v=float(x[:,2].max()),
            output_min_v=float(x[:,3].min()),output_max_v=float(x[:,3].max()),
            input_y_min_v=float(x[:,4].min()),input_y_max_v=float(x[:,4].max()),
            peak_board_supply_backfeed_a=float(max(0,x[:,6].max())),mean_peer_source_current_a=float(-x[:,7].mean()))
    dc_states={}
    for name,rail,enabled in [('active',voltage,1),('disabled',voltage,0),('reset',voltage,0),('unpowered',0,0),('brownout',1.5,0),('reconfigured',voltage,1)]:
        dc=header+network+f'VBOARD SOURCE_VDD 0 {rail}\nVPEER PEER 0 {rail if peer_supply=="common_board" else voltage}\n'
        dc+=f'BDATA DATA RETURN V=V(RAIL,RETURN)*{enabled}\nBOE OE RETURN V=V(RAIL,RETURN)*{enabled}\n'
        dc+='.control\nset wr_singlescale\nset wr_vecnames\nop\n'+f'wrdata {work}/dc_{name}.dat v(RAIL) v(RETURN) v(BOARD_OUT) i(VBOARD) i(VPEER)\nquit\n.endc\n.end\n'
        path=work/f'dc_{name}.spice';path.write_text(dc)
        run=subprocess.run(['ngspice','-b',path.name],cwd=work,capture_output=True,text=True,timeout=30)
        (work/f'dc_{name}.log').write_text(run.stdout+run.stderr);run.check_returncode()
        row=np.atleast_2d(np.loadtxt(work/f'dc_{name}.dat',skiprows=1))[0]
        dc_states[name]=dict(local_supply_v=float(row[1]-row[2]),output_v=float(row[3]),
            board_supply_backfeed_a=float(max(0,row[4])),peer_source_current_a=float(-row[5]))
    # Isolate the native clamp with exactly the same supply trajectory. This
    # diagnostic deliberately removes bonds and host peers; it cannot fill any
    # missing combined-state window or qualify the integrated candidate.
    single=header+instance('XCLAMP','gf180mcu_fd_io__dvdd',dict(DVDD='RAIL',DVSS='0',VSS='0'))
    single+=next(line for line in stimuli.splitlines() if line.startswith('VBOARD ')).replace('SOURCE_VDD','RAIL')+'\n'
    single+='.control\nset wr_singlescale\nset wr_vecnames\ntran 250p 3u 0 250p\n'
    single+=f'wrdata {work}/isolated_clamp.dat v(RAIL) v(xclamp.n6) v(xclamp.n7) v(xclamp.n8) v(xclamp.n4) i(VBOARD)\nquit\n.endc\n.end\n'
    (work/'isolated_clamp.spice').write_text(single)
    isolated_run=subprocess.run(['ngspice','-b','isolated_clamp.spice'],cwd=work,capture_output=True,text=True,timeout=30)
    (work/'isolated_clamp.log').write_text(isolated_run.stdout+isolated_run.stderr);isolated_run.check_returncode()
    isolated_data=np.atleast_2d(np.loadtxt(work/'isolated_clamp.dat',skiprows=1))
    isolated=dict(transient_complete=bool(isolated_data[-1,0]>=2999.99e-9),last_time_s=float(isolated_data[-1,0]),
        scope='One unchanged native supply clamp driven directly by the same supply trajectory, without bonds or host peers. Diagnostic only; does not substitute for missing combined transient windows.')
    report=dict(native_layout_loading=native_loading,peer_supply_policy=peer_supply,status='retained_host_and_supply_candidate_screen_not_host_or_power_signoff' if transient_complete else 'incomplete_native_supply_pad_transient',binding=selected,
        isolated_native_clamp=isolated,
        transient_complete=transient_complete,transient_last_time_s=float(data[-1,0]),
        numerical_failure_excerpt=result.stderr[-1200:] if not transient_complete else None,
        independent_dc_operating_points=dc_states,
        lifecycle_states=states,assumptions=dict(numerical_node_shunt_ohm=regularization_ohm,integration='gear_order2',relative_tolerance=.003,transient_iteration_limit=100,gmin_s=1e-10,maximum_step_s=250e-12,supply_v=voltage,word_rate_hz=host['maximum_word_rate_hz'],external_output_load_f=load,
            supply_bond_r_ohm_per_pin=.1,supply_bond_l_h_per_pin=power_parameters['bond_l_h'],signal_bond_r_ohm=1,signal_bond_l_h=2e-9,
            peer_source_r_ohm=50,output_peer_pullup_ohm=10000,core_output_load_f=20e-15,
            shared_pdn_network={k:pdn[k] for k in ('feed_r','feed_l','board_c','board_esr','board_esl','die_c','die_esr','die_esl')},
            package_reduction='Explicit parallel supply/ground bond paths replace reduced package_r; do not count both.',
            active_windows_ns=[[0,40],[2941,3000]]),
        limitations=selected['limitations']+['Only representative output/input/reset cells, not full-bank simultaneous switching.',
            'Starts from a powered DC operating point; initial cold startup and slow clamp settling are not established.',
            'Reset/disabled are commanded OE-low states; no implemented supervisor is hidden in the bench.',
            'Shared board/local decoupling stays attached; supply transitions use 3us total duration, not the old 300ns diagnostic.',
            ('Host output-high voltage tracks the common upstream board source; transceiver feed/bond/decoupling lag remains. This is a board connection requirement, not autonomous on-chip power-off tolerance.' if peer_supply=='common_board' else 'Independent host peer remains powered and high through all transitions; this is an adverse power arrangement.'),
            'Ideal board sources can sink current; actual regulator/bank behavior is not qualified.',
            'Full-rate drive stimulus is not a capture-eye or protocol-throughput verdict.',
            'DC operating points discard stored charge and cannot replace missing retained transient windows.',
            ('Selected native clamp wire capacitances are included with checked node mapping; remaining native capacitance, distributed resistance and full-ring coupling are absent.' if native_loading else 'Native transistor hierarchy includes pad devices; extra physical pad capacitance and distributed ring impedance are not added or extracted here.')],
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [Path(__file__),Path(__file__).with_name('retained.py'),PROJECT/'spec/contract.json',PROJECT/'spec/analog-architecture.json',
             PROJECT/'verification/run_gpio_transient.py',library,pdk/'design.ngspice',pdk/'sm141064.ngspice',pdk/'sm141064.spice']+([native_loading_report] if native_loading_report else [])})
    (work/'retained-screen.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(transient_complete=transient_complete,states=states,dc_states=dc_states),indent=2))
    return transient_complete


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--pdk-model-dir',type=Path,required=True);p.add_argument('--library',type=Path,required=True)
    p.add_argument('--regularization-ohm',type=float)
    p.add_argument('--native-loading-report',type=Path)
    p.add_argument('--peer-supply',choices=('common_board','independent'),default='common_board')
    a=p.parse_args();complete=screen(a.output_dir.resolve(),a.pdk_model_dir.resolve(),a.library.resolve(),a.regularization_ohm,a.peer_supply,
        a.native_loading_report.resolve() if a.native_loading_report else None)
    sys.exit(0 if complete else 1)
