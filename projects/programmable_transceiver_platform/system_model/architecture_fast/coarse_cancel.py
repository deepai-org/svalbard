"""Coarse counter cancellation at each acquisition phase and reference restart."""
import hashlib,json,time
from pathlib import Path
from coarse_chip import CoarseTransceiverChip
from shared_tx_traffic import scenario


def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P;start=time.monotonic()
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Exact scheduler boundaries, not arbitrary SPI/CDC races.',
                     'Startup cancellation only; successful warm retune needs analog recentering.'])
    output=p/'evidence/fast-coarse-cancel.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for state in ('settle','start_wait','measure','end_wait','commit'):
            c=CoarseTransceiverChip(watchdog_s=1e-3)
            c.execute_management('rf_coarse_start',2500000000,c.time)
            while c.coarse.state!=state:
                assert c.coarse.next_event is not None
                c.advance(c.coarse.next_event)
            phase=c.rf_pll.output_phase_cycles;frequency=c.rf_pll.frequency_hz
            generation=c.coarse.generation;hold=c.rf_pll.hold_voltage
            c.set_reference(False,c.time)
            assert c.coarse.state=='cancelled' and not c.coarse.qualified
            assert c.coarse.snapshot_pending is None and c.coarse.next_event is None
            assert c.coarse.generation>generation
            assert c.rf_pll.output_phase_cycles==phase
            assert abs(c.rf_pll.frequency_hz-frequency)<1e-6
            c.advance(c.time+3e-6)
            c.set_reference(True,c.time)
            assert c.rf_pll.hold_voltage==hold,'Reference return changed held fine voltage'
            assert not c.rf_pll.present and not c.coarse.qualified
            c.execute_management('rf_coarse_start',2500000000,c.time)
            c.advance(c.time+35e-6)
            assert c.coarse.qualified and c.rf_pll.locked
            assert abs(c.rf_pll.control())<.8
            report['cases'].append(dict(cancelled_state=state,generation=c.coarse.generation,
                bank_code=c.rf_pll.bank_code,fine_control_v=c.rf_pll.control(),restarted=True));save()
            print(state,'passed',flush=True)
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:save()

if __name__=='__main__':main()
