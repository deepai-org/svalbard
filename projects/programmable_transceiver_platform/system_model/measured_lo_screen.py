"""Measured zero-input LO spur injected at baseband; scoped sensitivity only."""
import hashlib,json
from pathlib import Path
import numpy as np
from fast_screen import convert
P=Path(__file__).resolve().parents[1]
paths=[P/'evidence/lo-second-stage.json',P/'evidence/lo-second-stage-half.json']
a,b=[json.loads(p.read_text()) for p in paths]
assert a['completed'] and b['completed'] and a['baseline']==b['baseline']
models={'baseline':a['baseline']['baseband'],'doubled':a['candidate']['baseband'],'halved':b['candidate']['baseband']}
rows=[]
for name,bb in models.items():
    for fs in [20e6,40e6]:
        t=np.arange(4096)/fs
        for signal_peak in [.008,.25]:
            ideal=signal_peak*np.exp(2j*np.pi*3e6*t)
            for phase in [0,np.pi/2,np.pi,3*np.pi/2]:
                # Only amplitudes are available here; relative I/Q phase is swept.
                spur=bb['i']['reference_fundamental_peak_v']*np.cos(2*np.pi*19.53125e6*t)
                spur=spur+1j*bb['q']['reference_fundamental_peak_v']*np.cos(2*np.pi*19.53125e6*t+phase)
                offset=bb['i']['mean_v']+1j*bb['q']['mean_v']
                y=ideal+spur+offset
                out=convert(y.real,1)+1j*convert(y.imag,1)
                # Report uncorrected error and DC-removed error; no hidden spur cancellation.
                error=out-ideal
                alias=abs((19.53125e6+fs/2)%fs-fs/2)
                rows.append(dict(model=name,fs=fs,signal_peak_v=signal_peak,iq_spur_phase_rad=phase,
                    alias_hz=alias,uncorrected_error_ratio=float(np.linalg.norm(error)/np.linalg.norm(ideal)),
                    dc_removed_error_ratio=float(np.linalg.norm(error-error.mean())/np.linalg.norm(ideal)),
                    clipping_fraction=float(np.mean((abs(y.real)>=.5)|(abs(y.imag)>=.5)))))
assert rows[0]['alias_hz']==468750
report=dict(status='measured_disturbance_sensitivity_not_calibrated_receiver',cases=rows,
    source_hashes={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths+[Path(__file__),P/'system_model/fast_screen.py']},
    limitations=['LO amplitudes/DC are from zero-RF seeded replay at its specific load and bias.',
    'Ideal signal is hypothetical; linear superposition under driven RF is unverified.',
    'Only fundamental/DC retained; higher harmonics, missing pulses and noise omitted.',
    'Spur phase swept because measured summaries do not retain relative phase.',
    'Ideal uniform8-bit1V ADC, no sampling aperture/filter/reference dynamics.',
    'No Wi-Fi or whole-chip qualification; this model cannot predict transistor sizing.'])
(P/'evidence/fast-measured-lo.json').write_text(json.dumps(report,indent=2)+'\n')
for name in models:
 for peak in [.008,.25]:
  v=[r['dc_removed_error_ratio'] for r in rows if r['model']==name and r['signal_peak_v']==peak]
  print(name,peak,round(min(v),4),round(max(v),4))
