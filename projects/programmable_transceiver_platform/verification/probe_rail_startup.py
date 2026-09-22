"""One-nanosecond quiet-input diagnostic, not a communication or stability test."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
from run_gpio_transient import TECH, PAD, output_instance


def checkpoint_steps(values, expected):
    if values.ndim != 2 or len(values)<2 or not np.all(np.isfinite(values)):
        raise ValueError('not a finite transient trace')
    dt=np.diff(values[:,0])
    if np.any(dt<=0) or not np.isclose(values[-1,0],expected,rtol=1e-6,atol=1e-15):
        raise ValueError('invalid transient time axis')
    return {'min':float(min(dt)),'median':float(np.median(dt)),'max':float(max(dt))}


def probe(mode, checkpoints=False, solver=None, replay_root=None, rail_elements='rl', capacitor_only=False):
    if solver not in (None,'sparse','klu'):
        raise ValueError('unknown solver')
    if rail_elements not in ('r','l','rl'):raise ValueError('invalid rail elements')
    case=mode+(f'_{solver}' if solver else '')+(f'_{rail_elements}' if rail_elements!='rl' else '')+('_caps' if capacitor_only else '')
    path=(Path(replay_root) if replay_root else Path('/work'))/case
    if not replay_root:path.mkdir()
    init='set ngbehavior=hs\n'+('option klu\n' if solver=='klu' else '')
    if not replay_root:(path/'.spiceinit').write_text(init)
    elif (path/'.spiceinit').read_text()!=init:raise ValueError('replay init mismatch')
    positive=('RVP BOARD VP_MID 0.25\nLVP VP_MID DVDD 2n' if mode in ('supply_only','both')
              else 'VFEED BOARD DVDD 0')
    negative=('RG DVSS VG_MID 0.25\nLG VG_MID 0 2n' if mode in ('return_only','both')
              else 'VRETURN DVSS 0 0')
    if rail_elements=='r':
        positive=positive.replace('LVP VP_MID DVDD 2n','VLP VP_MID DVDD 0')
        negative=negative.replace('LG VG_MID 0 2n','VLG VG_MID 0 0')
    elif rail_elements=='l':
        positive=positive.replace('RVP BOARD VP_MID 0.25','VRP BOARD VP_MID 0')
        negative=negative.replace('RG DVSS VG_MID 0.25','VRG DVSS VG_MID 0')
    deck='* Quiet native-pad startup diagnostic\n'+f'.include {TECH}/design.ngspice\n'
    deck+=''.join(f'.lib {TECH}/sm141064.ngspice {s}\n' for s in ('typical','res_typical','diode_typical','moscap_typical'))
    deck+=f'''.include {PAD}
.temp 25
VD BOARD 0 3.3
{positive}
{negative}
VC VDD 0 3.3
VA A 0 0
VK K 0 0
{output_instance('XD','A','DPAD','YD',8,'DVSS')}
{output_instance('XK','K','CPAD','YK',8,'DVSS')}
RD DPAD DMID 1
LD DMID D 2n
RC CPAD CMID 1
LC CMID C 1n
CD D 0 10p
CC C 0 10p
CYD YD 0 1f
CYK YK 0 1f
.control
set noaskquit
set wr_singlescale
set wr_vecnames
op
wrdata {path}/op.txt v(DVDD) v(DVSS) v(D) v(C) i(VD)
tran 10p 1n 0 10p
wrdata {path}/wave.txt v(DVDD) v(DVSS) v(D) v(C) i(VD)
quit
.endc
.end
'''
    if capacitor_only:
        # Diagnostic extraction of the first two native MOS capacitors per pad.
        # The pad itself is removed; this cannot qualify the original pad.
        for instance, source, pad, output in [('XD','A','DPAD','YD'),('XK','K','CPAD','YK')]:
            caps=(f'{instance}C0 DVDD DVSS cap_nmos_06v0 m=4 c_length=3e-6 c_width=3e-6\n'
                  f'{instance}C1 DVDD DVSS cap_nmos_06v0 m=10 c_length=1.5e-6 c_width=5e-6\n'
                  f'V{instance}PAD {pad} 0 0\nV{instance}Y {output} 0 0')
            deck=deck.replace(output_instance(instance,source,pad,output,8,'DVSS'),caps)
    if checkpoints:
        # Breakpoints preserve the same transient state across each resume.
        control = 'set numdgt=16\n'
        control += ''.join(f'stop when time = {n}n\n' for n in (1,2,4,8))
        control += 'tran 10p 12n 0 10p\n'
        for n in (1,2,4,8,12):
            control += f'wrdata {path}/at{n}ns.txt v(DVDD) v(DVSS) v(D) v(C) i(VD)\n'
            if n != 12:
                control += 'resume\n'
        deck = deck.replace(f'tran 10p 1n 0 10p\nwrdata {path}/wave.txt v(DVDD) v(DVSS) v(D) v(C) i(VD)\n', control)
    status='completed'
    if replay_root:
        if (path/'tb.spice').read_text()!=deck.replace(str(path),'/work/'+case):
            raise ValueError('replay deck mismatch')
        # Caller supplies terminal timeout facts; absence of completed trace is
        # independently rejected below. Never rerun during replay.
    else:
        (path/'tb.spice').write_text(deck)
        with (path/'run.log').open('w') as log:
            try:
                result=subprocess.run(['ngspice','-b','tb.spice'],cwd=path,stdout=log,stderr=subprocess.STDOUT,timeout=60 if checkpoints else 30)
                if result.returncode:status='simulator_error'
            except subprocess.TimeoutExpired:
                status='timeout'
    log_text=(path/'run.log').read_text()
    if 'simulation(s) aborted' in log_text:
        status='simulator_error'
    observed=('klu' if 'Using KLU' in log_text else 'sparse' if 'Using SPARSE' in log_text else 'unknown')
    if solver and observed!=solver:
        status='solver_selection_mismatch'
    row={'case':case,'solver_requested':solver,'solver_observed':observed,
         'init_sha256':hashlib.sha256(init.encode()).hexdigest(),'execution_status':status,'deck_sha256':hashlib.sha256(deck.encode()).hexdigest(),
         'log_sha256':hashlib.sha256((path/'run.log').read_bytes()).hexdigest()}
    names = ('op','at1ns','at2ns','at4ns','at8ns','at12ns') if checkpoints else ('op','wave')
    for name in names:
        file=path/(name+'.txt')
        if not file.exists():continue
        row[name+'_sha256']=hashlib.sha256(file.read_bytes()).hexdigest()
        values=np.atleast_2d(np.loadtxt(file,skiprows=1))
        if checkpoints and name!='op':
            try:
                stats=checkpoint_steps(values,int(name[2:-2])*1e-9)
            except ValueError as error:
                row[name+'_rejected']=str(error)
                if row['execution_status']=='completed':row['execution_status']='invalid_transient_snapshot'
                continue
            row[name+'_time_steps_s']=stats
        row[name+'_rows']=len(values)
        row[name+'_extrema']={signal:{'min':float(min(values[:,i+1])),'max':float(max(values[:,i+1]))}
                              for i,signal in enumerate(('vdd_v','vss_v','data_v','clock_v','source_current_a'))}
        if name!='op':
            row['last_time_s']=float(values[-1,0])
    if row['execution_status']=='completed' and row.get('last_time_s',0)<(12e-9 if checkpoints else 1e-9)*.999:
        row['execution_status']='incomplete_waveform'
    return row

if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        rows=list(pool.map(probe,('ideal','supply_only','return_only','both')))
    report={'scope':'quiet-input operating point and 1 ns startup isolation; no signaling verdict',
            'results':rows,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'pad_spice_sha256':hashlib.sha256(PAD.read_bytes()).hexdigest(),
            'assumptions':['Default integration; 10 ps maximum step; 30 second per-case bound.',
                           'Quiet inputs are equivalent to prior stimulus only before its 20 ns start.',
                           'Zero and selected R/L isolate topology; they are not proven physical uncertainty bounds.']}
    Path('/work/rail-startup.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
