"""Full-band custom QPSK multicarrier fixture through simultaneous four-path traffic."""
import hashlib,json,math
import numpy as np
from chip_model import P
from rf_quality_screen import simulate,quality
from rf_selectivity_screen import butterworth_order


class Multicarrier:
    def __init__(self,seed=804):self.seed=seed;self.metadata=None
    def __call__(self,count,fs):
        if fs not in (20e6,40e6):raise ValueError('Unsupported multicarrier sample rate')
        n=int(fs/312500);prefix=n//4
        bins=np.array(list(range(-25,0))+list(range(1,26)))
        rng=np.random.default_rng(self.seed);values=[];blocks=0
        first=None;first_spectrum=None
        while len(values)<count:
            symbols=((2*rng.integers(0,2,50)-1)+1j*(2*rng.integers(0,2,50)-1))/math.sqrt(2)
            spectrum=np.zeros(n,dtype=complex);spectrum[bins%n]=.035*symbols
            block=np.fft.ifft(spectrum)*n
            if first is None:first=block;first_spectrum=spectrum
            values.extend(block[-prefix:]);values.extend(block);blocks+=1
        values=np.array(values[:count]);peak=float(np.max(abs(values)))
        assert peak<.9  # Fixed source amplitude; never normalize a failing waveform after the fact.
        recovered=np.fft.fft(first)/n
        assert np.max(abs(recovered-first_spectrum))<1e-15
        assert abs(first_spectrum[25])>.034 and abs(first_spectrum[-25])>.034
        self.metadata=dict(seed=self.seed,fft_size=n,cyclic_prefix_samples=prefix,
            active_subcarriers=50,spacing_hz=312500,edge_hz=7812500,
            useful_symbol_s=n/fs,prefix_s=prefix/fs,generated_blocks=blocks,
            sample_count=count,peak_envelope=peak,rms_envelope=float(np.sqrt(np.mean(abs(values)**2))),
            waveform_sha256=hashlib.sha256(values.astype('<c16').tobytes()).hexdigest())
        return list(values)


def controls():
    a=Multicarrier();b=Multicarrier();c=Multicarrier(seed=805)
    x=a(640,20e6);assert x==b(640,20e6) and x!=c(640,20e6)
    y=Multicarrier()(1280,40e6)
    assert np.max(abs(np.array(x)-np.array(y)[::2]))<1e-15


def main():
    controls();order,cutoff=butterworth_order(8e6,20e6,1,30);rows=[]
    for mode in (0,1):
        ideal_wave=Multicarrier();actual_wave=Multicarrier()
        baseline,t,reference=simulate(mode,1,'ideal',rx_filter=(order,cutoff),waveform=ideal_wave)
        traffic,times,values=simulate(mode,1,'combined',(20e6,30e6),rx_filter=(order,cutoff),waveform=actual_wave)
        assert t==times and ideal_wave.metadata==actual_wave.metadata
        rows.append(dict(mode=mode,waveform=actual_wave.metadata,quality=quality(reference,values),
            reference_adc_sha256=baseline['adc_sha256'],traffic=traffic))
    report=dict(status='passed',cases=rows,complete_architecture=False,physical_qualification=False,
        limitations=['Custom50-carrier QPSK fixture is not an IEEE802.11 packet or a compliant Wi-Fi modem.',
        'Useful-symbol carriers extend to+/-7.8125MHz; finite symbol boundaries and DAC images are not strictly bandlimited.',
        'Waveform error uses a matched filter/quantizer reference, not total constellation EVM or decoded packet error.',
        'First-quarter fixed scalar calibration cannot compensate time-varying LO error; no adaptive external FPGA receiver is modeled here.',
        'Positive-sign combined assumptions and one seed do not bound component/process variation or all possible data.'])
    (P/'evidence/connected-rf-modulated-quality.json').write_text(json.dumps(report,indent=2)+'\n')
    for row in rows:print(row['mode'],row['waveform'],row['quality'])

if __name__=='__main__':main()
