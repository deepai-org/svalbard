#!/usr/bin/env python3
"""LVS reference netlists for the pad families whose simulation netlist carries a model-only device (SG-1, PC-14).

`physical.spice` of the wired/reference pad families is the SIMULATION netlist: the flat extracted cell plus one line
`DWELL_ARRAY VSS ESD_RAIL diode_nw2ps_06v0 ...` that `protection_network.py` appends as a model of the protection
array's n-well-to-substrate junction (Magic does not extract it as a device). That line is not a drawn device, so a
read-back LVS against `physical.spice` shows one extra device. This script writes, next to each `physical.spice`,
`lvs-reference.spice` = the flat cell subcircuit only (the wrapper is dropped), without the appended line; its pin
list is the flat cell's own, which includes the layout's ESD_RAIL pin.  `physical.spice` is not modified.

usage: lvs_reference.py [family_dir ...]      (default: the four families under generated/stress-safe-families)
"""
import re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
FAMILIES = ['reference', 'wired-receive-hs', 'wired-receive-usb', 'wired-transmit']


def write(d):
    d = Path(d)
    text = (d / 'physical.spice').read_text()
    subs = re.findall(r'(?ms)^\.subckt (\S+) .*?^\.ends[^\n]*\n?', text)
    blocks = {m.group(1): m.group(0) for m in re.finditer(r'(?ms)^\.subckt (\S+) .*?^\.ends[^\n]*\n?', text)}
    flat = [n for n in blocks if 'DWELL_ARRAY' in blocks[n]]
    if len(flat) != 1:
        raise SystemExit(f'{d}: expected exactly one subcircuit with the appended well diode, found {flat}')
    body, n = re.subn(r'(?m)^DWELL_ARRAY \S+ \S+ diode_nw2ps_06v0 [^\n]*\n', '', blocks[flat[0]])
    if n != 1:
        raise SystemExit(f'{d}: appended well-diode line not found exactly once')
    out = (f'* LVS reference for {flat[0]} (analog/pads/lvs_reference.py): physical.spice without the model-only\n'
           f'* DWELL_ARRAY n-well diode. Simulations keep using physical.spice.\n' + body)
    (d / 'lvs-reference.spice').write_text(out)
    pins = re.sub(r'\n\+', ' ', body).splitlines()[0].split()[2:]
    return flat[0], pins


if __name__ == '__main__':
    for f in sys.argv[1:] or [HERE / 'generated/stress-safe-families' / x for x in FAMILIES]:
        cell, pins = write(f)
        print(f, cell, len(pins), 'pins', 'ESD_RAIL' in pins)
