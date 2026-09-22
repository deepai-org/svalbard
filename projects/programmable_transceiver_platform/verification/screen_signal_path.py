"""Explicit lumped signal-path sensitivity; no selected package model."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import numpy as np
from run_gpio_transient import run_case, PAD, START, UI, N
from screen_weak_drive import host_margin

work=Path('/work')
paths=[(1,1,1),(1,2,1)]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(lambda p:run_case(work,'typical',3.3,25,10,'prbs7',drive_ma=8,signal_path=p),paths))
for r in results:
    try:
        r['host_threshold_screen']=host_margin(work/r['case'],'prbs7')
    except ValueError as error:
        r['host_threshold_screen']={'measurement_rejected':str(error),'qualified':False}
    t,a,k,d,c,ivd,ivc=np.loadtxt(work/r['case']/'wave.txt',skiprows=1).T
    region=(t>=START+8*UI)&(t<=START+(N-4)*UI)
    r['receiver_voltage_extrema_v']={name:{'min':float(min(v[region])),'max':float(max(v[region]))}
                                    for name,v in [('data',d),('clock',c)]}
report={'scope':'lumped signal-path sensitivity, ideal supply/return, not package or host qualification',
        'results':results,
        'input_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                       [PAD,Path(__file__),Path('/src/verification/run_gpio_transient.py'),
                        Path('/src/verification/screen_weak_drive.py')]},
        'assumptions':['1 ohm per signal, 1 nH clock, 1 or 2 nH data are selected sensitivity points.',
                       '10 pF receiver load; no receiver clamp or transmission line model.',
                       'Ideal power and ground; no rail inductance, coupling, SSO or process variation.',
                       'Assumed +/-0.2 ns aperture; diagnostic clock intervals must remain 1.6 to 4.8 ns.']}
(work/'signal-path.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
