"""Analytical output-stage controls and frozen full-chip trace sensitivity."""
import hashlib,json,math
from pathlib import Path
import numpy as np
from chip_model import P
from tx_output_stage import output_envelope
from tx_envelope_observer import spectrum
from rf_quality_screen import quality

def main():
    theta=2*np.pi*np.arange(4096)/4096
    tone=np.exp(1j*theta);unit=np.ones_like(tone)
    assert np.array_equal(output_envelope(tone,unit),tone)
    # Exact wanted/image decomposition for a quadrature gain/phase error.
    db=.5;phi=math.radians(2);g=10**(db/40)
    a=(g+np.exp(1j*phi)/g)/2;b=(g-np.exp(1j*phi)/g)/2
    measured=output_envelope(tone,unit,gain_imbalance_db=db,phase_error_deg=2)
    error=float(np.max(abs(measured-(a*tone+b*tone.conjugate()))))
    assert error<1e-14
    leak=.01+.02j
    assert np.allclose(output_envelope(tone,unit,lo_feedthrough=leak).mean(),leak,atol=1e-14)
    assert np.allclose(output_envelope(.5*tone,unit,cubic=.2),.5*tone*.95,atol=1e-14)
    # Two-tone third-order products: z=A(e^jwt+e^j2wt), products at DC and 3w.
    amp=.1;k=.2;two=amp*(tone+tone**2)
    out=output_envelope(two,unit,cubic=k)
    assert abs(out.mean()+k*amp**3)<1e-14
    assert abs(np.mean(out*tone.conjugate()**3)+k*amp**3)<1e-14
    rejected=0
    for kwargs in ({'cubic':-1},{'cubic':1},{'phase_error_deg':float('nan')}):
        try:output_envelope(tone,unit,**kwargs)
        except ValueError:rejected+=1
    assert rejected==3
    rows=[]
    for mode in (0,1):
        path=P/'evidence'/f'connected-reconstructed-duplex-quality-mode{mode}-traces.npz'
        d=np.load(path);z=d['actual_baseband'];r=d['actual_rotation'];ref=d['ideal_tx']
        rms=float(np.sqrt(np.mean(abs(z)**2)));peak=float(max(abs(z)))
        cases=[]
        settings=[('identity',{})]
        for db in (.1,.25,.5,1.):settings.append((f'gain_{db}_dB',dict(gain_imbalance_db=db)))
        for deg in (1.,2.,5.):settings.append((f'phase_{deg}_deg',dict(phase_error_deg=deg)))
        for dbc in (-50,-40,-30):settings.append((f'LO_{dbc}_dBc',dict(lo_feedthrough=rms*10**(dbc/20))))
        for loss in (.01,.03,.1):settings.append((f'peak_compression_{loss}',dict(cubic=loss/peak**2)))
        settings.append(('combined_trial',dict(gain_imbalance_db=.25,phase_error_deg=2.,lo_feedthrough=rms*.01,cubic=.03/peak**2)))
        for name,kwargs in settings:
            y=output_envelope(z,r,**kwargs)
            if name=='identity':assert np.max(abs(y-d['actual_tx']))<1e-15
            serial={k:([v.real,v.imag] if isinstance(v,complex) else v) for k,v in kwargs.items()}
            cases.append(dict(name=name,parameters=serial,quality=quality(list(ref),list(y)),spectrum=spectrum(d['time_s'],y)))
        rows.append(dict(mode=mode,trace=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),cases=cases))
    report=dict(status='passed',scope='Analytical controls pass; sensitivity results include failures. Frozen output-only replay, not a coupled full-chip qualification.',
        analytical_max_error=error,cases=rows,physical_qualification=False)
    (P/'evidence'/'connected-tx-output-stage.json').write_text(json.dumps(report,indent=2,default=lambda v:v.item())+'\n')
    for row in rows:
        print(row['mode'],[(c['name'],round(100*c['quality']['corrected_relative_rms'],3),c['quality']['screen_pass']) for c in row['cases']])
if __name__=='__main__':main()
