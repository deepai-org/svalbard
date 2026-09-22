"""Exact switched-mixer oracle for a fixed 50-tone QPSK RF envelope."""
import hashlib,json,math,sys
from pathlib import Path
import numpy as np
from scipy.signal import lfilter, butter, residue
P=Path(__file__).resolve().parents[1]
F=P/'system_model/architecture_fast';sys.path.insert(0,str(F))
from lo_drive import square_fixture,iq_sidebands

def run(period,subdivision=1):
    carrier=2.4e9;cutoff=9157407.055691985
    numerator,denominator=butter(5,1.,analog=True)
    residues,roots,_=residue(numerator,denominator)
    poles=-roots*2*np.pi*cutoff;weights=residues/(-roots)
    duration=3.2e-6;dt=1/(4*carrier*subdivision)
    t=np.arange(1,round(duration/dt)+1)*dt;a=t-dt
    rng=np.random.default_rng(804)
    frequencies=np.r_[np.arange(-25,0),np.arange(1,26)]*312500.
    amplitudes=.035*np.exp(1j*(np.pi/4+np.pi/2*rng.integers(0,4,50)))
    # Repeat the piecewise-constant switching fixture; divide intervals only to
    # independently check observation-grid and recursion invariance.
    edges,iv,qv=square_fixture(carrier,period,period)
    drive=np.tile(np.repeat(np.asarray(iv)+1j*np.asarray(qv),subdivision),
                  int(np.ceil(len(t)/(len(iv)*subdivision))))[:len(t)]/(4/np.pi)
    truth=np.zeros(len(t),complex)
    for pole,weight in zip(poles,weights):
        decay=np.exp(-pole*dt);injection=np.zeros(len(t),complex)
        for amplitude,frequency in zip(amplitudes,frequencies):
            rate=2j*np.pi*(frequency-carrier)
            for amp,r in ((amplitude,rate),(amplitude.conjugate(),rate.conjugate())):
                injection+=drive*amp*pole/(pole+r)*(np.exp(r*t)-decay*np.exp(r*a))
        truth+=weight*lfilter([1.],[1.,-decay],injection)
    select=t>=.4e-6;scale=np.sqrt(np.mean(abs(truth[select])**2))
    rows=[]
    for count in (0,3,period-1):
        terms=iq_sidebands(edges,iv,qv,carrier,[k*carrier/period for k in range(-count,count+1)])
        estimated=np.zeros(len(t),complex)
        for offset,d,i in terms:
            for amp,f in zip(amplitudes,frequencies):
                for value,frequency in ((d*amp,offset+f),(i*amp.conjugate(),offset-f)):
                    rate=2j*np.pi*frequency
                    for pole,weight in zip(poles,weights):
                        estimated+=weight*value*pole/(pole+rate)*(np.exp(rate*t)-np.exp(-pole*t))
        error=np.sqrt(np.mean(abs(estimated[select]-truth[select])**2))/scale
        rows.append(dict(sidebands_each_side=count,relative_rms_error=float(error)))
    assert rows[-1]['relative_rms_error']<rows[0]['relative_rms_error']
    return dict(missing_i_period=period,subdivision=subdivision,truncations=rows,approximation_budget=.003,
                approximation_screen_pass=rows[-1]['relative_rms_error']<.003),truth

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    files=[Path(__file__),F/'lo_drive.py']
    hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    cases=[]
    for period in (8,):
        coarse,y=run(period);fine,z=run(period,2)
        error=float(np.max(abs(y-z[1::2])))
        assert error<1e-10
        cases.append(dict(coarse=coarse,fine=fine,subdivision_max_error=error))
    assert all(c[g]['approximation_screen_pass'] for c in cases for g in ('coarse','fine'))
    result=dict(status='completed',numerical_checks='passed',approximation_screen_pass=all(
                    c[grid]['approximation_screen_pass'] for c in cases for grid in ('coarse','fine')),source_sha256=hashes,cases=cases,carrier_hz=2.4e9,cutoff_hz=9157407.055691985,filter_order=5,
                tone_count=50,tone_spacing_hz=312500,seed=804,duration_s=3.2e-6,physical_qualification=False,
                limitations=['Fixed multitone symbol, not changing OFDM symbols or Wi-Fi compliance.',
                'Fifth-order Butterworth filter, normalized switching drive; no gate-voltage mapping.',
                'Errors measure envelope truncation, not total RF quality or noise.'])
    (P/'evidence/lo-multipole-truncation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(cases,indent=2))
if __name__=='__main__':main()
