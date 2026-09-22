"""Same coupled traffic/quality test with the three-capacitor RF clock candidate."""
import hashlib,json,traceback
from pathlib import Path
from chip_model import P
from limited_rail_budget_pad_quality import main
from three_cap_managed_chip import ThreeCapManagedChip
from three_cap_retuning_clock import BALANCED_FILTER

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--mode',type=int,choices=(0,1),default=1)
    args=parser.parse_args()
    hashes={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    path=P/f'evidence/three-cap-pad-quality-mode{args.mode}-launch.json'
    report=dict(status='running',mode=args.mode,filter_values=BALANCED_FILTER,source_sha256=hashes,
        limitations=['Coupled mathematical candidate; not transistor or layout qualification.'])
    path.write_text(json.dumps(report,indent=2)+'\n')
    try:
        main(args.mode,True,actual_chip_class=ThreeCapManagedChip,experiment_tag='three-cap')
        report['status']='passed'
    except BaseException as error:
        report.update(status='failed',error=repr(error),traceback=traceback.format_exc())
        raise
    finally:
        report['source_hashes_match']=all(hashlib.sha256((P/f).read_bytes()).hexdigest()==h for f,h in hashes.items())
        path.write_text(json.dumps(report,indent=2)+'\n')
