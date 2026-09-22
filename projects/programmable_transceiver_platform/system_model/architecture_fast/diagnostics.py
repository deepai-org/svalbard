"""Internal rail/reference diagnostic transport on the shared-TX composition."""
import hashlib
import json
import time
from pathlib import Path
from shared_tx_traffic import scenario
from chip import TransceiverChip as SharedOutputChip
import internal_monitor_screen as monitor


def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    p=scenario.architecture.P;start=time.monotonic();original=monitor.ProgrammableChip
    files=list(scenario.architecture.D.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))+[p/'verification/stream_codec.py']
    hashes={str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',source_sha256=hashes,cases=[],physical_qualification=False,
        limitations=['Ideal monitor buffer and assumed cadence; no peak capture guarantee.',
                     'Rail/reference diagnostic selection reserves ADC pair, precluding simultaneous RF RX.',
                     'Probe-pad monitor and arbitrary configuration races remain open.'])
    output=p/'evidence/fast-diagnostics.json'
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save();monitor.ProgrammableChip=SharedOutputChip
    try:
        for mode in (0,1):
            for route in (1,2):
                a=monitor.run(mode,route,1);b=monitor.run(mode,route,137)
                assert a['words']==b['words'] and a['updates']==b['updates']
                assert abs(a['voltage']-b['voltage'])<1e-12
                report['cases'].append(a);save()
                print(mode,route,'passed',flush=True)
        assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        report.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:monitor.ProgrammableChip=original;save()

if __name__=='__main__':main()
