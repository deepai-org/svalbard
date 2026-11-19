import sys,re
from pathlib import Path
def inl(p,seen):
    p=Path(p).resolve(); out=[]
    for l in p.read_text().splitlines():
        m=re.match(r'\s*\.include\s+(\S+)',l,re.I)
        if m:
            q=(p.parent/m.group(1)).resolve()
            if q not in seen: seen.add(q); out+=inl(q,seen)
        else: out.append(l)
    return out
print('\n'.join(inl(sys.argv[1],set())))
