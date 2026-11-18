#!/usr/bin/env python3
"""Liberty comparison ignoring comments and whitespace.  lib_compare.py <old lib dir> <new lib dir>
Per file: identical after removing /* */ comments and all whitespace, or the list of cells whose text differs."""
import hashlib, os, re, sys
def norm(p):
    t = re.sub(r'/\*.*?\*/', '', open(p, errors='replace').read(), flags=re.S)
    cells = {}
    parts = re.split(r'\n\s*cell\s*\(\s*"?([\w$]+)"?\s*\)', t)
    cells['_header'] = re.sub(r'\s+', '', parts[0])
    for i in range(1, len(parts), 2): cells[parts[i]] = re.sub(r'\s+', '', parts[i + 1])
    return cells
o, n = sys.argv[1:3]; tot = 0
for f in sorted(set(os.listdir(o)) | set(os.listdir(n))):
    if not f.endswith('.lib'): continue
    if not (os.path.exists(f'{o}/{f}') and os.path.exists(f'{n}/{f}')): print(f, 'ONLY IN ONE'); continue
    a, b = norm(f'{o}/{f}'), norm(f'{n}/{f}')
    d = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k)); tot += len(d)
    print(f, 'cells', len(a) - 1, 'IDENTICAL (comments/whitespace only)' if not d else f'DIFFERENT in {len(d)}: {d[:40]}')
print('total differing cells', tot)
