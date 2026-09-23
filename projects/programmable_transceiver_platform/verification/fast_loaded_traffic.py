"""Loaded pad, monitor and loopback under calibrated simultaneous four-path traffic."""
import argparse,hashlib,json,time
from pathlib import Path
from fast_loaded_output import LoadedOutputChip,P
from continuous_duplex import PreparedChip
from continuous_four_path import run
from continuous_duplex import run as run_rf
from fast_exclusive_engine import ExclusiveEngineChip,PoweredExclusiveChip

class PreparedLoadedChip(PreparedChip,LoadedOutputChip):
    def __init__(self,**kwargs):
        super().__init__(tx_relative_gain=True,**kwargs)
        self.tx_probe.clear();self.probe_times.clear()

class SelectedRFChip(ExclusiveEngineChip):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.select_engine('rf')

class PreparedExclusiveChip(PreparedChip,SelectedRFChip):
    def __init__(self,**kwargs):
        super().__init__(tx_relative_gain=True,**kwargs)
        self.tx_probe.clear();self.probe_times.clear()

class PreparedPoweredChip(PreparedExclusiveChip,PoweredExclusiveChip):
    def __init__(self,**kwargs):
        self.off_clock_checks=0;self.off_wire_phase=None
        super().__init__(**kwargs)
    def advance(self,time):
        super().advance(time)
        if self.wire_pll is not None:
            assert not self.wire_pll.powered and self.wire_pll.frequency_hz==0
            phase=self.wire_pll.output_phase_cycles
            if self.off_wire_phase is not None:assert abs(phase-self.off_wire_phase)<1e-8
            self.off_wire_phase=phase;self.off_clock_checks+=1

def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    parser=argparse.ArgumentParser();parser.add_argument('--exclusive',action='store_true')
    parser.add_argument('--power-gated',action='store_true')
    args=parser.parse_args()
    if args.power_gated:args.exclusive=True
    files=list((P/'system_model/connected').glob('*.py'))+list((P/'system_model/architecture_fast').glob('*.py'))+[Path(__file__),P/'verification/fast_loaded_output.py',P/'verification/stream_codec.py',P/'verification/fast_exclusive_engine.py']
    hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',power_gated=args.power_gated,exclusive_rf=args.exclusive,source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Transport and event alignment only; loaded RF waveform quality and calibration accuracy remain unqualified.',
                     'Assumed passive output network; no nonlinear current limit or output supply feedback.',
                     'Finite count-free stream with lossy stop; no indefinite service guarantee. Bias-current transients and physical shutdown behavior remain open; only --power-gated checks stopped oscillator state.'])
    output=P/('evidence/fast-powered-rf-traffic.json' if args.power_gated else 'evidence/fast-exclusive-rf-traffic.json' if args.exclusive else 'evidence/fast-loaded-traffic.json');start=time.monotonic()
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for mode in (0,1):
            chips=[]
            def factory(**kwargs):
                c=(PreparedPoweredChip if args.power_gated else PreparedExclusiveChip if args.exclusive else PreparedLoadedChip)(**kwargs);chips.append(c);return c
            traffic=(run_rf if args.exclusive else run)(mode,True,True,chip_factory=factory)
            c=chips[0]
            if args.exclusive:
                assert c.active_engine=='rf' and not c.session.enabled('wire')
                assert not c.wired_output and not c.host_wire and not c.wire_queue
                assert c.wire_accepted==0
            if args.power_gated:assert c.off_clock_checks>128
            assert c.output_network.time==c.tx_detector.time==c.tx.time==c.time
            assert not c.output_network.output_on and c.output_network.dummy_on
            assert len(c.tx_probe)>128 and max(abs(v) for v in c.tx_probe)>1e-3
            assert c.tx_adc_samples==9
            report['cases'].append(dict(mode=mode,traffic=traffic,pad_samples=len(c.tx_probe),
                peak_pad_envelope=max(abs(v) for v in c.tx_probe),shared_calibration_samples=c.tx_adc_samples,
                stopped_output_isolated=True,analog_clocks_aligned=True,
                off_clock_checks=c.off_clock_checks if args.power_gated else None));save()
            print(mode,'passed',flush=True)
        assert all(hashlib.sha256((P/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()
if __name__=='__main__':main()
