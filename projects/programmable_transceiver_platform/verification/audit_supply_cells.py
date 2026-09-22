"""Record native power-cell formal pins; not a rail connectivity/ESD proof."""
import hashlib
import json
import re
from pathlib import Path
p=Path('/foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_io/spice/gf180mcu_fd_io.spice')
raw=p.read_bytes();text=raw.decode()
expected={'dvdd':['DVDD','DVSS','VSS'],'dvss':['DVDD','DVSS','VDD'],'brk2':['VSS'],'brk5':['VSS']}
cells={}
for short,pins in expected.items():
    name='gf180mcu_fd_io__'+short
    match=re.search(r'^\.SUBCKT '+re.escape(name)+r' (.*)$',text,re.M)
    if not match or match.group(1).split()!=pins:raise ValueError('unexpected formal pins: '+name)
    cells[name]=pins
print(json.dumps({'scope':'native supply/breaker formal-pin audit only','image_id':'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305','source':str(p),'source_sha256':hashlib.sha256(raw).hexdigest(),'cells':cells,'limitations':['No GDS/LEF rail continuity, current sharing, clamp response or ESD verification.']},indent=2))
