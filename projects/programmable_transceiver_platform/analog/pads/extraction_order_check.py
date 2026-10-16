"""Verify that two exports differ only by capacitor names, order or orientation.

All other lines must match exactly. This permits retaining tested SPICE bytes
when a repeated extractor emits the same capacitor graph in another order.
"""
import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path


def check(first,second,output):
    def signature(path):
        rest=[];caps=Counter()
        for line in path.read_text().splitlines():
            if re.match(r'^C[0-9]+\s',line):
                fields=line.split()
                if len(fields)<4 or (len(fields)>4 and fields[4]!='$'):raise ValueError('Unexpected capacitor syntax')
                caps[(*sorted(fields[1:3]),*fields[3:])]+=1
            else:rest.append(line)
        return rest,caps
    a,ac=signature(first);b,bc=signature(second)
    report={'status':'strict_capacitor_order_equivalence','noncapacitor_lines_identical':a==b,'capacitor_graph_identical':ac==bc,'capacitor_count':sum(ac.values()),'scope':'Only capacitor identifiers, ordering and terminal orientation may differ; component values must retain identical literal spelling. No ignored device, source, subcircuit or model change.','source_sha256':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [first,second,Path(__file__)]}}
    output.write_text(json.dumps(report,indent=2)+'\n')
    if a!=b or ac!=bc:raise ValueError('Exports differ electrically or require a broader audit')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['first','second','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(check(a.first.resolve(),a.second.resolve(),a.output.resolve()),indent=2))
