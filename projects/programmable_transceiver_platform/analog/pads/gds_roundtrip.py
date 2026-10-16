"""Audit the actual exported pad GDS against the simulated physical device graph."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
from layout import magic
from extract_audit import converted_graph,extracted_graph


def check(root,gds,reference,cell):
    root.mkdir(parents=True,exist_ok=False)
    shutil.copy2(gds,root/'input.gds')
    (root/'extract.tcl').write_text(f'''crashbackups stop
gds read input.gds
load {cell}
select top cell
flatten roundtrip
load roundtrip
save
select top cell
expand
drc check
drc catchup
puts "ROUNDTRIP_DRC [drc list count total]"
extract all
quit -noprompt
''')
    output=magic(root,'extract.tcl');match=re.search(r'ROUNDTRIP_DRC (\d+)',output.stdout)
    expected=converted_graph(reference)
    try:
        actual=extracted_graph(root/'roundtrip.ext');error=None
    except ValueError as exception:
        actual=Counter();error=str(exception)
    missing=expected-actual;unexpected=actual-expected
    result=dict(drc_count=int(match[1]) if match else None,device_graph_match=not error and expected==actual,extraction_error=error,
        expected_models=dict(Counter({m:sum(v for k,v in expected.items() if k[0]==m) for m in {k[0] for k in expected}})),
        actual_models=dict(Counter({m:sum(v for k,v in actual.items() if k[0]==m) for m in {k[0] for k in actual}})),
        missing_devices=[dict(key=list(k),count=v) for k,v in missing.items()],unexpected_devices=[dict(key=list(k),count=v) for k,v in unexpected.items()],
        gds_sha256=hashlib.sha256(gds.read_bytes()).hexdigest(),reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest())
    (root/'gds-roundtrip.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def run(work,generated):
    work.mkdir(parents=True,exist_ok=False);results={}
    for family in ('wired-transmit','wired-receive-usb','reference-clock','rf-receive','rf-transmit'):
        meta=json.loads((generated/(family+'-layout.json')).read_text())
        results[family]=check(work/family,generated/(family+'.gds'),generated/(family+'-extracted-c.spice'),meta['flat_cell'])
    result=dict(status='exported_GDS_roundtrip_device_audit',all_device_graphs_match=all(r['device_graph_match'] for r in results.values()),families=results,limitations=['Device graph and ordinary DRC only; capacitance, routing resistance, ESD and assembly checks are separate.'],source_sha256={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(__file__).with_name('extract_audit.py'),Path(__file__).with_name('layout.py'))})
    (work/'gds-roundtrip.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:{x:v[x] for x in ('drc_count','device_graph_match','expected_models','actual_models','extraction_error')} for k,v in results.items()},indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--generated',type=Path,default=Path(__file__).with_name('generated'))
    a=p.parse_args();result=run(a.output_dir.resolve(),a.generated.resolve())
    if not result['all_device_graphs_match']:raise SystemExit(2)
