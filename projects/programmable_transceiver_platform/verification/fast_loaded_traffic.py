"""Loaded pad, monitor and loopback under calibrated simultaneous four-path traffic."""
import hashlib,json,time
from pathlib import Path
from fast_loaded_output import LoadedOutputChip,P
from continuous_duplex import PreparedChip
from continuous_four_path import run

class PreparedLoadedChip(PreparedChip,LoadedOutputChip):
    def __init__(self,**kwargs):
        super().__init__(tx_relative_gain=True,**kwargs)
        self.tx_probe.clear();self.probe_times.clear()

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    files=list((P/'system_model/connected').glob('*.py'))+list((P/'system_model/architecture_fast').glob('*.py'))+[Path(__file__),P/'verification/fast_loaded_output.py',P/'verification/stream_codec.py']
    hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Transport and event alignment only; loaded RF waveform quality and calibration accuracy remain unqualified.',
                     'Assumed passive output network; no nonlinear current limit or output supply feedback.'])
    output=P/'evidence/fast-loaded-traffic.json';start=time.monotonic()
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for mode in (0,1):
            chips=[]
            def factory(**kwargs):
                c=PreparedLoadedChip(**kwargs);chips.append(c);return c
            traffic=run(mode,True,True,chip_factory=factory)
            c=chips[0]
            assert c.output_network.time==c.tx_detector.time==c.tx.time==c.time
            assert not c.output_network.output_on and c.output_network.dummy_on
            assert len(c.tx_probe)>128 and max(abs(v) for v in c.tx_probe)>1e-3
            assert c.tx_adc_samples==9
            report['cases'].append(dict(mode=mode,traffic=traffic,pad_samples=len(c.tx_probe),
                peak_pad_envelope=max(abs(v) for v in c.tx_probe),shared_calibration_samples=c.tx_adc_samples,
                stopped_output_isolated=True,analog_clocks_aligned=True));save()
            print(mode,'passed',flush=True)
        assert all(hashlib.sha256((P/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()
if __name__=='__main__':main()
