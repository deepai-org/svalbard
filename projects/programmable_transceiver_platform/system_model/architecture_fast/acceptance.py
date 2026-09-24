"""Fresh selected-scope common-chip acceptance with source/result provenance."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
P=Path(__file__).resolve().parents[2]
D=Path(__file__).parent
CASES={
 'continuous_four_path.py':'fast-continuous-four-path.json',
 'continuous_quality.py':'fast-continuous-quality.json',
 'shared_tx_recovery.py':'fast-shared-tx-recovery.json',
 'diagnostics.py':'fast-diagnostics.json',
 'receiver_detect.py':'fast-receiver-detect-supply.json',
 'continuous_rx.py':'fast-continuous-rx.json',
 'lo_mixer_check.py':'fast-lo-mixer.json',
 'lo_sideband_check.py':'fast-lo-sidebands.json',
 'output_loopback_check.py':'fast-output-loopback.json',
 'wideband_loopback_quality.py':'fast-wideband-loopback-quality.json',
 'local_mode_check.py':'fast-local-mode.json',
 'warm_chip_check.py':'fast-warm-chip.json',
}

def extended_main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    start=time.monotonic()
    files=list((P/'system_model/connected').glob('*.py'))+list(D.glob('*.py'))+[P/'verification/stream_codec.py']
    hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    result=dict(status='running',model='chip.TransceiverChip',source_sha256=hashes,checks=[],
        complete_architecture=False,physical_qualification=False,
        remaining=['Full supported configuration/route and carrier envelopes.',
                   'Pin-level SPI and management/RTL reconciliation (transaction-level local operation tested).',
                   'General clock/service bounds and lossless stopping.',
                   'Complete noise, loaded output/package and physical parameter qualification; nonlinear loopback tested.',
                   'Full connected transistor schematic before layout.'])
    output=P/'evidence/fast-common-acceptance.json'
    def save():output.write_text(json.dumps(result,indent=2)+'\n')
    def run(script):
        env=dict(os.environ,OPENBLAS_NUM_THREADS='1')
        proc=subprocess.run([sys.executable,str(D/script)],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
        log=P/'evidence'/('acceptance-'+Path(script).stem+'.log');log.write_text(proc.stdout)
        if proc.returncode:raise RuntimeError(f'{script} exited {proc.returncode}; see {log}')
        evidence=P/'evidence'/CASES[script];r=json.loads(evidence.read_text())
        assert r['status']=='passed',script
        assert r['source_sha256']==hashes,script
        return dict(script=script,evidence=evidence.name,case_count=len(r['cases']),
                    result_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest())
    save()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures={pool.submit(run,script):script for script in CASES}
            for future in concurrent.futures.as_completed(futures):
                row=future.result();result['checks'].append(row);save();print(row['script'],'passed',flush=True)
        assert all(hashlib.sha256((P/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        result.update(status='passed',elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        result.update(status='failed',error=repr(exc));raise
    finally:save()

def iteration_main():
    """Bounded architecture loop; detailed coupled physics is a separate check."""
    commands=[
        ('protocol_and_signal_paths',P/'verification/protocol_model_check.py',[]),
        ('generic_configuration',P/'verification/test_resource_configuration.py',[]),
        ('transport_records',P/'verification/test_bit_event_codec.py',[]),
        ('converter_clock',P/'system_model/connected/reference_sample_clock.py',[]),
        ('converter_transport',P/'system_model/connected/reference_sample_clock.py',['--payload-controls']),
        ('calibration_bounds',P/'verification/calibration_observation_budget.py',['--bounded-controls']),
        ('independent_rf_reference',P/'verification/fast_loaded_loopback_quality.py',['--coupled-reference-controls']),
    ]
    start=time.monotonic();budget=30.
    output=P/'evidence/architecture-iteration.json'
    sources=list((P/'system_model').rglob('*.py'))+list((P/'verification').glob('*.py'))+[P/'spec/contract.json']
    hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sources}
    report=dict(status='running',scope='Reduced architecture and block contracts; not detailed full-chip qualification',
        wall_budget_s=budget,checks=[],source_sha256=hashes,full_chip_closure=False,
        physical_qualification=False,omitted=['Coupled RF/rail cold acquisition and long transient integration.',
            'Sustained independently modulated traffic and all-protocol peer interoperability.',
            'Transistor, package and layout qualification.'])
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        for name,script,args in commands:
            remaining=budget-(time.monotonic()-start)
            if remaining<=0:raise TimeoutError('Architecture iteration exceeded 30-second budget')
            before=time.monotonic()
            result=subprocess.run([sys.executable,str(script),*args],
                env=dict(os.environ,OPENBLAS_NUM_THREADS='1'),text=True,
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=min(15.,remaining))
            row=dict(name=name,elapsed_s=time.monotonic()-before,returncode=result.returncode)
            if result.returncode:
                row['diagnostic']=result.stdout[-4000:]
            report['checks'].append(row);save()
            if result.returncode:raise RuntimeError(name+' failed: '+result.stdout[-2000:])
            print(name,'passed',round(row['elapsed_s'],3),'s',flush=True)
        assert all(hashlib.sha256((P/f).read_bytes()).hexdigest()==h for f,h in hashes.items())
        report['status']='passed'
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:
        report['elapsed_s']=time.monotonic()-start;save()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extended',action='store_true',help='Historical common-chip suite, capped at 60 seconds per runner')
    args=parser.parse_args()
    if args.extended:extended_main()
    else:iteration_main()
