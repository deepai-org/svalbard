#!/usr/bin/env python3
"""Rewrite one top-level .subckt so that net FROM is renamed to net TO.

Used only for the diagnostic "common-ground" LVS of the biasgen: the die has a
single ground net, and the layout joins avss/dvss through the substrate, so the
comparison ties dvss to avss in both netlists before matching.
usage: tie_nets.py IN OUT SUBCKT FROM TO
"""
import re
import sys

src, dst, top, frm, to = sys.argv[1:6]
lines = open(src).read().split('\n')
# join continuation lines so the .subckt header is a single logical line
logical = []
for line in lines:
    if line.startswith('+') and logical:
        logical[-1] += ' ' + line[1:]
    else:
        logical.append(line)
out, inside = [], False
word = re.compile(r'(?<![\w\[\]/.#])' + re.escape(frm) + r'(?![\w\[\]/.#])')
for line in logical:
    low = line.lower()
    if low.startswith('.subckt') and line.split()[1] == top:
        inside = True
        toks = line.split()
        ports, seen = [], set()
        for t in toks[2:]:
            t = to if t == frm else t
            if t not in seen:
                seen.add(t)
                ports.append(t)
        out.append(' '.join(toks[:2] + ports))
        continue
    if inside and low.startswith('.ends'):
        inside = False
    out.append(word.sub(to, line) if inside else line)
open(dst, 'w').write('\n'.join(out))
