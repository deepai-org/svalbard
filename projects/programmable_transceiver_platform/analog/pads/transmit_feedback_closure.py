"""Verify a sampled feedback fixed point without repeating identical analog work.

Feed a completed detector report back through actual RTL and compare every
emitted control event with the events that drove that completed analog run.
Identical controls imply the same deterministic analog problem. Raw detector
samples in unused states may differ, so they remain reported separately.
"""
import argparse,hashlib,json,subprocess
from pathlib import Path
from design import PROJECT
from transmit_sequence_connected import feedback_tb


def events(text):
    result=[]
    for line in text.splitlines():
        if not line.startswith('TRACE '):continue
        fields=line.split()[1:]
        if any(v.lower() in ('x','z') for v in fields):
            if float(fields[0])>.1:raise ValueError('Unknown RTL control after initialization')
            continue
        result.append([float(fields[0])]+[int(v) for v in fields[1:]])
    if not result or result[0][0]>.1:raise ValueError('Missing initialized control events')
    return result


def verify(work,completed):
    work.mkdir(parents=True,exist_ok=False)
    report_path=completed/'screen.json';report=json.loads(report_path.read_text())
    if not report.get('transient_complete'):raise ValueError('Incomplete analog run')
    for name,digest in report['source_sha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Stale completed-run source: '+name)
    rtl=PROJECT/'rtl/pt_tx_pad_sequence.sv'
    text,_,_=feedback_tb(report_path,report['scenario'])
    tb=work/'replay.sv';tb.write_text(text)
    subprocess.run(['iverilog','-g2012','-s','replay','-o',str(work/'replay.vvp'),str(rtl),str(tb)],check=True,capture_output=True,text=True)
    simulation=subprocess.run(['vvp',str(work/'replay.vvp')],check=True,capture_output=True,text=True)
    (work/'rtl.log').write_text(simulation.stdout)
    prior=events((completed/'rtl.log').read_text());current=events(simulation.stdout)
    same=prior==current
    coverage=(not report['busy_commit_events'] and 'BUSY_COMMIT' not in simulation.stdout and report['disabled_end_observed']
        and all(c['qualified'] and c['traffic_ready'] for c in report['mode_coverage'].values()))
    result=dict(status='identical_RTL_controls_prove_sampled_feedback_closure' if same else 'feedback_changes_controls_requires_new_analog_run',
        controls_identical=same,previous_event_count=len(prior),updated_event_count=len(current),
        raw_feedback_sample_mismatches=report['feedback_sample_mismatches'],
        complete_mode_coverage=coverage,
        loaded_traffic_ready_without_detector_ready_s=report['loaded_traffic_ready_without_detector_ready_s'],
        lifecycle_gate_pass=bool(same and coverage and report['loaded_traffic_ready_without_detector_ready_s']==0),
        scope=__doc__+' Only this nominal deterministic fixture and sampled RTL feedback; not physical detectors, sustained data, PVT or protection acceptance.',
        source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [Path(__file__),Path(__file__).with_name('transmit_sequence_connected.py'),report_path,completed/'rtl.log',completed/'connected.spice',rtl,tb,work/'rtl.log']})
    (work/'closure.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--completed-dir',type=Path,required=True)
    a=p.parse_args();r=verify(a.output_dir.resolve(),a.completed_dir.resolve());print(json.dumps(r,indent=2))
    if not r['controls_identical']:raise SystemExit(2)
