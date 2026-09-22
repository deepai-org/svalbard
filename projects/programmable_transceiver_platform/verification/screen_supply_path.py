"""Shared output supply/return R/L sensitivity; core supply remains ideal."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import numpy as np
from run_gpio_transient import run_case, PAD, START, UI, N
from screen_weak_drive import host_margin

work=Path('/work')
matrix=[20,10]  # Same physical PRBS case; test timestep sensitivity first.
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(lambda case:run_case(work,'typical',3.3,25,10,'prbs7',drive_ma=8,
                                               signal_path=(1,2,1),supply_path=(0.25,2),integration='gear',max_step_ps=case),matrix))
for r in results:
    case=work/r['case']
    try:
        r['host_threshold_screen']=host_margin(case,r['pattern'])
    except ValueError as error:
        r['host_threshold_screen']={'measurement_rejected':str(error),'qualified':False}
    rail=case/'rails.txt'
    t,vdd,vss=np.loadtxt(rail,skiprows=1).T
    region=(t>=START+8*UI)&(t<=START+(N-4)*UI)
    r['rails_waveform_sha256']=hashlib.sha256(rail.read_bytes()).hexdigest()
    r['rail_voltage_extrema_v']={name:{'min':float(min(v[region])),'max':float(max(v[region]))}
                                 for name,v in [('vdd_to_board_ground',vdd),('vss_to_board_ground',vss),
                                                ('local_supply_span',vdd-vss)]}
report={'scope':'two-pad shared supply/return sensitivity, not full-bank power or package qualification',
        'execution_note':'Initial default-trapezoidal four-case run timed out before stimulus. These are fresh Gear-2 timestep-comparison runs of one physical PRBS case.',
        'results':results,'input_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
          [PAD,Path(__file__),Path('/src/verification/run_gpio_transient.py'),Path('/src/verification/screen_weak_drive.py')]},
        'assumptions':['R/L on both supply and return: 0.25 ohm/2 nH per rail; Gear-2 with 20/10 ps maximum steps.',
                       'Selected stress values; no actual assembly impedance or PDN extraction.',
                       'Native pad capacitors only; no added ideal on-die decoupling.',
                       'Core supply/return and stimulus remain ideal; no full-bank, clamp-ring, H2D or substrate model.',
                       'Signal paths retain 1 ohm each, data 2 nH, clock 1 nH; receiver load 10 pF.',
                       'Typical process, 3.3 V board supply, 25 C, assumed receiver timing aperture.']}
(work/'supply-path.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
