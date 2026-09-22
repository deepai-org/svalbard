"""Candidate transistor-level GPIO data/clock pair; ideal supplies, lumped load."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np

PDK = Path('/foss/pdks/gf180mcuD')
TECH = PDK/'libs.tech/ngspice'
PAD = PDK/'libs.ref/gf180mcu_fd_io/spice/gf180mcu_fd_io.spice'
UI = 3.2e-9
START = 20e-9
SLEW = .5e-9
N = 32


def stimulus(pattern, voltage):
    state = 0x5d
    bits = []
    for n in range(N):
        bits.append(n % 2 if pattern == 'alternating' else state & 1)
        state = ((state << 1) | (((state >> 6) ^ (state >> 5)) & 1)) & 127
    points = [(0,0)]
    previous = 0
    for n,bit in enumerate(bits):
        t = START+n*UI
        points.extend([(t,previous*voltage),(t+SLEW,bit*voltage)])
        previous = bit
    points.append((START+(N+8)*UI,previous*voltage))
    return bits, ' '.join(f'{t:.12g} {v:.12g}' for t,v in points)


def crossing(t, y, threshold):
    indices = np.nonzero((y[:-1] < threshold) != (y[1:] < threshold))[0]
    return t[indices]+(threshold-y[indices])*(t[indices+1]-t[indices])/(y[indices+1]-y[indices])


def output_instance(instance, source, pad, output, drive_ma, dvss='0'):
    if drive_ma == 24:
        return f'{instance} {source} 0 DVDD {dvss} 0 VDD {pad} 0 0 0 VDD 0 {output} gf180mcu_fd_io__bi_24t'
    if drive_ma not in (4, 8, 12, 16):
        raise ValueError('unsupported native drive strength')
    code = drive_ma // 4 - 1
    pdrv0 = 'VDD' if code & 1 else '0'
    pdrv1 = 'VDD' if code & 2 else '0'
    return f'{instance} {source} 0 DVDD {dvss} 0 VDD {pad} 0 {pdrv0} {pdrv1} 0 0 VDD 0 {output} gf180mcu_fd_io__bi_t'


def run_case(work, corner, voltage, temp, load, pattern, replay=False, drive_ma=24, signal_path=None, supply_path=None, integration=None, max_step_ps=20):
    name = f'{corner}_{temp}_{load}_{pattern}' + (f'_drive{drive_ma}' if drive_ma != 24 else '')
    network = ''
    data_pad, clock_pad = 'D', 'C'
    if signal_path is not None:
        r_ohm, ld_nh, lc_nh = signal_path
        if not all(np.isfinite(v) and v > 0 for v in signal_path):
            raise ValueError('signal path R/L must be finite and positive')
        name += f'_r{r_ohm}_ld{ld_nh}_lc{lc_nh}'
        data_pad, clock_pad = 'DPAD', 'CPAD'
        network = (f'RD DPAD DMID {r_ohm}\nLD DMID D {ld_nh}n\n'
                   f'RC CPAD CMID {r_ohm}\nLC CMID C {lc_nh}n\n')
    supply = f'VD DVDD 0 {voltage}'
    dvss = '0'
    if supply_path is not None:
        r_ohm, l_nh = supply_path
        if not all(np.isfinite(v) and v > 0 for v in supply_path):
            raise ValueError('supply path R/L must be finite and positive')
        name += f'_sr{r_ohm}_sl{l_nh}'
        dvss = 'DVSS'
        supply = (f'VD BOARD 0 {voltage}\nRVP BOARD VP_MID {r_ohm}\n'
                  f'LVP VP_MID DVDD {l_nh}n\nRG DVSS VG_MID {r_ohm}\n'
                  f'LG VG_MID 0 {l_nh}n')
    solver_options = ''
    transient = f'tran 20p {START+(N+8)*UI:.12g}'
    if integration is not None:
        if integration not in ('gear', 'trapezoidal') or not np.isfinite(max_step_ps) or max_step_ps <= 0:
            raise ValueError('invalid integration or maximum step')
        name += f'_{integration}{max_step_ps}ps'
        solver_options = f'.options method={integration} maxord=2\n'
        transient += f' 0 {max_step_ps}p'
    path=work/name
    if not replay:
        path.mkdir()
        (path/'.spiceinit').write_text('set ngbehavior=hs\n')
    elif (path/'.spiceinit').read_text() != 'set ngbehavior=hs\n':
        raise ValueError('replay init mismatch')
    rail_write = f'wrdata {path}/rails.txt v(DVDD) v(DVSS)\n' if supply_path else ''
    bits,pwl=stimulus(pattern,voltage)
    resistor = 'res_typical' if corner=='typical' else 'res_'+corner
    decks=[f'.include {TECH}/design.ngspice']
    decks += [f'.lib {TECH}/sm141064.ngspice {section}' for section in [corner,resistor,'diode_typical','moscap_typical']]
    deck='* Candidate native GPIO pair\n'+'\n'.join(decks)+f'''
{solver_options}.include {PAD}
.temp {temp}
{supply}
VC VDD 0 {voltage}
VA A 0 PWL({pwl})
VK K 0 PULSE(0 {voltage} {START+UI/2:.12g} {SLEW:.12g} {SLEW:.12g} {UI-SLEW:.12g} {2*UI:.12g})
{output_instance('XD', 'A', data_pad, 'YD', drive_ma, dvss)}
{output_instance('XK', 'K', clock_pad, 'YK', drive_ma, dvss)}
{network}CD D 0 {load}p
CC C 0 {load}p
CYD YD 0 1f
CYK YK 0 1f
.control
set noaskquit
set wr_singlescale
set wr_vecnames
{transient}
wrdata {path}/wave.txt v(a) v(k) v(d) v(c) i(VD) i(VC)
{rail_write}quit
.endc
.end
'''
    if replay:
        if (path/'tb.spice').read_text() != deck:
            raise ValueError('replay deck mismatch')
        log=(path/'run.log').read_text()
        if 'ngspice-' not in log or not (path/'wave.txt').exists():
            raise ValueError('incomplete replay artifacts')
    else:
        (path/'tb.spice').write_text(deck)
        with (path/'run.log').open('w') as output:
            run=subprocess.run(['ngspice','-b','tb.spice'],cwd=path,stdout=output,stderr=subprocess.STDOUT,text=True,timeout=90)
        log=(path/'run.log').read_text()
        if run.returncode or not (path/'wave.txt').exists():
            raise RuntimeError(name+' simulation failed: '+log[-2500:])
    wave=np.loadtxt(path/'wave.txt',skiprows=1)
    t,a,k,d,c,ivd,ivc=wave.T
    cin=crossing(t,k,voltage/2);cout=crossing(t,c,voltage/2)
    # Require one output edge per input edge, never select a passing latency.
    required = sum(ti < START+(N-4)*UI for ti in cin)
    if len(cout) < required: raise RuntimeError(name+' clock edges lost in measured interval')
    cout,cin=cout[:min(len(cin),len(cout))],cin[:min(len(cin),len(cout))]
    margins=[]; failures=0; used=0
    for index,(ti,to) in enumerate(zip(cin,cout)):
        sample=int(np.floor((ti-START)/UI))
        if not 8<=sample<N-4: continue
        expected=bits[sample]
        values=np.interp([to-.2e-9,to,to+.2e-9],t,d)
        margin=float(min(values-.7*voltage) if expected else min(.3*voltage-values))
        margins.append(margin);failures+=margin<0;used+=1
    if used != N-12:
        raise RuntimeError(name+' unexpected aperture sample count: '+str(used))
    region=(t>=START+8*UI)&(t<=START+(N-4)*UI)
    average=lambda current:float(np.sum(-(current[region][1:]+current[region][:-1])*.5*np.diff(t[region]))/(t[region][-1]-t[region][0]))
    return {'case':name,'mos_corner':corner,'passive_corners':[resistor,'diode_typical','moscap_typical'],
      'integration':integration or 'default','maximum_step_ps':max_step_ps if integration else None,'supply_path_r_ohm_l_nh_per_rail':supply_path,'signal_path_r_ohm_ld_nh_lc_nh':signal_path,'drive_strength_ma':drive_ma,'vdd_v':voltage,'temperature_c':temp,'external_lumped_capacitance_pf_per_output':load,'pattern':pattern,
      'sampled_bits':used,'aperture_ns':.4,'thresholds_fraction':[.3,.7],
      'minimum_aperture_voltage_margin_v':min(margins),'threshold_failures':failures,
      'clock_edge_delay_min_ns':float(min(cout-cin)*1e9),'clock_edge_delay_max_ns':float(max(cout-cin)*1e9),
      'two_pad_dvdd_average_a':average(ivd),'two_pad_core_vdd_average_a':average(ivc),
      'deck_sha256':hashlib.sha256(deck.encode()).hexdigest(),
      'waveform_sha256':hashlib.sha256((path/'wave.txt').read_bytes()).hexdigest(),
      'log_sha256':hashlib.sha256(log.encode()).hexdigest()}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--replay',action='store_true');args=parser.parse_args()
    matrix=[(corner,v,temp,load,pattern) for corner,v,temp in [('typical',3.3,25),('ss',2.97,125)] for load in [5] for pattern in ['alternating','prbs7']]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda case:run_case(args.work,*case,replay=args.replay),matrix))
    sources=[PAD,TECH/'design.ngspice',TECH/'sm141064.ngspice',TECH/'sm141064.spice']
    report={'scope':'transistor-level candidate pair, not extracted/package/SSO or FPGA qualification',
      'image':'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305',
      'simulator':subprocess.check_output(['ngspice','--version'],text=True),
      'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'input_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
      'ngspice_init':'set ngbehavior=hs',
      'execution':'reanalysis of existing waveforms with exact deck/init match' if args.replay else 'fresh simulation',
      'case_count':len(results),'results':results,
      'limitations':['Ideal supplies and no package/interconnect.', 'Assumed 0.3/0.7 receiver levels and +/-0.2 ns aperture, not a selected FPGA specification.',
       'Ideal 0.5 ns core drive and 1.6 ns forwarded-clock phase offset.', 'No H2D receiver, full-bank SSO, jitter, mismatch, ESD signoff or model qualification.',
       'Diode/MOS-cap corners remain typical; this is not full PVT/passive closure.']}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'cases':len(results),'cases_with_threshold_failures':sum(r['threshold_failures']>0 for r in results),'worst_voltage_margin_v':min(r['minimum_aperture_voltage_margin_v'] for r in results)}))

if __name__=='__main__':main()
