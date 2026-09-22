"""Coupled traffic regression with repeated, explicitly unqualified calibration."""
import hashlib,json,sys,traceback
from pathlib import Path
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'system_model/connected'))
from limited_rail_budget_pad_quality import main
from statistical_three_cap_chip import StatisticalThreeCapChip

POLICY=dict(planned_samples=64,confidence=.999,noise_sigma_v=.001,
    systematic_bound_v=None,gain_interval=None,assumptions_validated=False)
class RepeatedObservationChip(StatisticalThreeCapChip):
    def __init__(self,**kwargs):
        super().__init__(calibration_statistics=POLICY,**kwargs)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--mode',type=int,choices=(0,1),default=1)
    args=parser.parse_args()
    hashes={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (P/'system_model/connected').glob('*.py')}
    report=dict(status='running',mode=args.mode,policy=POLICY,source_sha256=hashes,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations=['Repeated observation integration test; uncertainty budget intentionally unverified.',
                     'Unchanged provisional RF-quality gates; not full-chip or transistor closure.'])
    path=P/f'evidence/statistical-three-cap-quality-mode{args.mode}-launch.json'
    path.write_text(json.dumps(report,indent=2)+'\n')
    try:
        main(args.mode,True,actual_chip_class=RepeatedObservationChip,experiment_tag='three-cap-repeated-cal')
        result_path=P/f'evidence/connected-limited-rail20-pad-quality-mode{args.mode}-three-cap-repeated-cal-phase-diagnostic.json'
        result=json.loads(result_path.read_text())
        assert result['status']=='passed'
        cal=result['traffic']['reference_metrics']['calibration']
        assert cal['maintenance']==dict(sampled=128,completed=128,cancelled=0,pending=0)
        assert len(cal['records'])==2
        for record in cal['records']:
            assessment=record['result']
            assert assessment['samples']==64 and not assessment['valid'] and not assessment['statistical_pass']
            assert assessment['accuracy']=='unverified'
        report.update(status='passed',calibration=cal,
            result_sha256=hashlib.sha256(result_path.read_bytes()).hexdigest())
    except BaseException as error:
        report.update(status='failed',error=repr(error),traceback=traceback.format_exc())
        raise
    finally:
        report['source_hashes_match']=all(hashlib.sha256((P/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        if not report['source_hashes_match']:report['status']='invalid_source_change'
        path.write_text(json.dumps(report,indent=2)+'\n')
