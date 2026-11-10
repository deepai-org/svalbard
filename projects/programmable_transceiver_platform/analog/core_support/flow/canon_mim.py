#!/usr/bin/env python3
"""Canonical MIM-capacitor orientation for LVS netlists.

usage: canon_mim.py IN OUT

Magic reports c_width/c_length of a MIM capacitor in the orientation of the
extraction (a rotated cap_mim paramcell reads 5u x 23u hierarchically and
23u x 5u flat), and netgen's GF180 setup compares the two properties
independently, so the same drawn capacitor becomes a property error depending
on how it was extracted.  Both comparison netlists are rewritten so that
c_width >= c_length on every cap_mim_* instance.  Area and perimeter (and so
the capacitance) are unchanged; every other value is still compared.  Only an
exact swap is made; nothing is merged or dropped.  Prints the number of
instances reordered.
"""
import re
import sys

UNITS = {'f': 1e-15, 'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3, '': 1.0}


def value(text):
    m = re.fullmatch(r'([-+0-9.eE]+?)([fpnum]?)', text)
    return float(m[1]) * UNITS[m[2]]


def canon(text):
    """Rewrite only cap_mim instance lines; all other text is kept verbatim
    (continuation lines included).  A cap line split over continuations is
    joined into one line."""
    count = 0
    physical = text.split('\n')
    out, i = [], 0
    while i < len(physical):
        group = [physical[i]]
        while i + len(group) < len(physical) and physical[i + len(group)].startswith('+'):
            group.append(physical[i + len(group)])
        i += len(group)
        line = ' '.join([group[0]] + [g[1:].strip() for g in group[1:]])
        w = re.search(r'\bc_width=(\S+)', line)
        l = re.search(r'\bc_length=(\S+)', line)
        if (re.match(r'^[Xx]\S*\s.*\bcap_mim_\S+', line) and w and l and value(w[1]) < value(l[1])):
            line = line.replace(w[0], 'c_width=@L@').replace(l[0], 'c_length=@W@')
            out.append(line.replace('@L@', l[1]).replace('@W@', w[1]))
            count += 1
        else:
            out.extend(group)
    return '\n'.join(out), count


if __name__ == '__main__':
    text, count = canon(open(sys.argv[1]).read())
    open(sys.argv[2], 'w').write(text)
    print('canon_mim', sys.argv[1], count)
