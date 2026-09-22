"""Connected fast-model oscillator noise sensitivity with independent TX probe."""
import hashlib
import json
import time
from pathlib import Path
import run as architecture
from oscillator_noise import FrequencyNoise
from rf_quality_screen import quality
P=architecture.P
Original=architecture.ObservedChip

class NoisyChip(Original):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.rf_pll.set_noise(0,FrequencyNoise.seeded(20000.,seed=839))

    def make_serializer(self,time):
        serializer=super().make_serializer(time)
        self.wire_pll.set_noise(time,FrequencyNoise.seeded(20000.,seed=840))
        return serializer


def main():
    start=time.monotonic()
    files=list(architecture.D.glob('*.py'))+[Path(__file__),Path(architecture.__file__),P/'verification/stream_codec.py']
    hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    result=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        noise= dict(rms_frequency_hz=20000,rf_seed=839,wire_seed=840,lines=8,spacing_hz=250000),
        limitations=['Assumed finite RF and wired oscillator frequency-noise spectra, not transistor characterization.',
                     'Nominal host rate, positive analog impairment sign, independent RF input.',
                     'Does not close the complete clock-noise budget.'])
    output=P/'evidence/fast-whole-chip-clock-noise.json'
    def save():output.write_text(json.dumps(result,indent=2)+'\n')
    save()
    try:
        for mode in (0,1):
            architecture.ObservedChip=Original
            _,rx0,tx0,t0,_=architecture.simulate(mode,0,True)
            architecture.ObservedChip=NoisyChip
            traffic,rx,tx,t,recovery=architecture.simulate(mode,1,True)
            assert t==t0
            rxq=quality(rx0,rx);txq=quality(tx0,tx)
            result['cases'].append(dict(mode=mode,rx_quality=rxq,tx_quality=txq,traffic=traffic,recovery=recovery))
            save();print(mode,rxq['corrected_relative_rms'],txq['corrected_relative_rms'],flush=True)
            assert rxq['screen_pass'] and txq['screen_pass']
        assert all(hashlib.sha256((P/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        result.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        result.update(status='failed',error=repr(exc));raise
    finally:
        architecture.ObservedChip=Original;save()

if __name__=='__main__':main()
