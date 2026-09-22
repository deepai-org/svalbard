#!/usr/bin/env python3
"""Inventory installed model entry files; presence is not validation or activation."""
from pathlib import Path
import hashlib,json,re
base=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice')
rows=[]
for name in ('design.ngspice','sm141064.ngspice','sm141064.spice'):
 p=base/name; s=p.read_text()
 sections=[line.strip() for line in s.splitlines() if line.strip().lower().startswith(('.lib ','.include '))]
 terms={term:len(re.findall(term,s,re.I)) for term in ('mismatch','monte','noimod','fnoi','tnoi','rgate','rbody')}
 rows.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),library_and_include_lines=sections,term_counts=terms))
r=dict(status='file_inventory_only',files=rows,
 limitations=['Not a recursive include manifest.','Term presence does not establish activated noise/mismatch models, RF characterization, or simulator support.',
 'Public documentation and installed simulator dialect may differ; Monte Carlo needs a demonstrably changing and correlated device test before yield claims.'])
Path('/work/model-inventory.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps([{k:v for k,v in row.items() if k!='library_and_include_lines'} for row in rows],indent=2))
