"""Minimal hierarchical SPICE reader/flattener for the timing family.

The block `.spice` files are the single source of truth: layout placement,
LVS reference and schematic simulation all read the same text.  Supported
syntax is intentionally small: `.subckt/.ends`, `X` instances of subcircuits
or of the GF180 primitives below, numeric `w= l= m=` (with `u`/`n` suffix) and
`*` comments.  `m=` on a primitive expands into separate physical instances so
that every schematic device has exactly one layout instance.
"""
from dataclasses import dataclass, field
from pathlib import Path
import re

PRIMITIVES = {
    'nfet_03v3': ('d', 'g', 's', 'b'),
    'pfet_03v3': ('d', 'g', 's', 'b'),
    'ppolyf_u_1k': ('p', 'n', 'b'),
}


# Compact fast cells (fastcells.py) are placed as macros: treated as leaf
# devices by the flattener and the layout engine.
MACROS = {}
_fast = Path(__file__).resolve().parent / 'generated' / 'fast'
if _fast.exists():
    import json as _json
    for _p in _fast.glob('*.pins.json'):
        MACROS[_p.name[:-len('.pins.json')]] = _json.loads(_p.read_text())['ports']


def value(text):
    text = text.strip().lower()
    scale = {'f': 1e-15, 'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3, 'k': 1e3}
    if text[-1] in scale:
        return float(text[:-1]) * scale[text[-1]]
    return float(text)


@dataclass
class Device:
    name: str
    model: str
    w: float  # microns (resistor: r_width)
    l: float  # microns (resistor: r_length)
    nodes: tuple

    @property
    def key(self):
        return (self.model, round(self.w, 4), round(self.l, 4))

    def spice(self):
        if self.model in MACROS:
            return f'X{self.name} {" ".join(self.nodes)} {self.model}'
        if self.model.startswith('ppolyf'):
            return f'X{self.name} {" ".join(self.nodes)} {self.model} r_width={self.w:g}u r_length={self.l:g}u'
        return f'X{self.name} {" ".join(self.nodes)} {self.model} w={self.w:g}u l={self.l:g}u'


@dataclass
class Subckt:
    name: str
    ports: list
    lines: list = field(default_factory=list)


def parse(text):
    subckts = {}
    current = None
    joined = []
    for raw in text.splitlines():
        line = raw.split(';')[0].rstrip()
        if not line.strip() or line.lstrip().startswith('*'):
            continue
        if line.startswith('+') and joined:
            joined[-1] += ' ' + line[1:]
        else:
            joined.append(line)
    for line in joined:
        tokens = line.split()
        head = tokens[0].lower()
        if head == '.subckt':
            current = Subckt(tokens[1], [t for t in tokens[2:] if '=' not in t])
            subckts[current.name] = current
        elif head == '.ends':
            current = None
        elif head.startswith('.'):
            continue
        elif current is not None:
            current.lines.append(tokens)
    return subckts


def flatten(subckts, top, prefix='', mapping=None, out=None):
    """Return a flat device list for subckt `top`. Internal nets get a
    hierarchical prefix; global 0 maps to VSS is not supported (use ports)."""
    sub = subckts[top]
    mapping = mapping if mapping is not None else {p: p for p in sub.ports}
    out = out if out is not None else []

    def net(n):
        if n in mapping:
            return mapping[n]
        return prefix + n

    for tokens in sub.lines:
        name = tokens[0]
        if name[0].upper() != 'X':
            raise ValueError(f'{top}: only X instances are supported: {tokens}')
        params = dict(t.split('=', 1) for t in tokens[1:] if '=' in t)
        args = [t for t in tokens[1:] if '=' not in t]
        cell = args[-1]
        conns = args[:-1]
        if cell in MACROS:
            if len(conns) != len(MACROS[cell]):
                raise ValueError(f'{top}/{name}: macro {cell} expects {len(MACROS[cell])} ports')
            out.append(Device((prefix + name[1:]).replace('.', '_'), cell, 0.0, 0.0, tuple(net(c) for c in conns)))
        elif cell in PRIMITIVES:
            if len(conns) != len(PRIMITIVES[cell]):
                raise ValueError(f'{top}/{name}: wrong terminal count')
            if cell.startswith('ppolyf'):
                w = value(params['r_width']) * 1e6
                l = value(params['r_length']) * 1e6
            else:
                w = value(params['w']) * 1e6
                l = value(params['l']) * 1e6
            m = int(params.get('m', '1'))
            for k in range(m):
                suffix = f'_{k}' if m > 1 else ''
                out.append(Device((prefix + name[1:] + suffix).replace('.', '_'), cell, w, l,
                                  tuple(net(c) for c in conns)))
        else:
            child = subckts[cell]
            if len(conns) != len(child.ports):
                raise ValueError(f'{top}/{name}: {cell} expects {len(child.ports)} ports')
            child_map = {p: net(c) for p, c in zip(child.ports, conns)}
            flatten(subckts, cell, prefix + name[1:] + '.', child_map, out)
    return out


def read_with_includes(path):
    path = Path(path)
    out = []
    for line in path.read_text().splitlines():
        if line.lower().startswith('.include'):
            out.append(read_with_includes(path.parent / line.split()[1].strip('"')))
        else:
            out.append(line)
    return '\n'.join(out)


def load(path, top):
    subckts = parse(read_with_includes(path))
    devices = flatten(subckts, top)
    names = [d.name for d in devices]
    if len(set(names)) != len(names):
        dup = sorted({n for n in names if names.count(n) > 1})
        raise ValueError(f'duplicate device name(s) after flattening: {dup[:5]}')
    return subckts[top].ports, devices


def flat_spice(ports, devices, name):
    lines = [f'.subckt {name} ' + ' '.join(ports)]
    lines += [d.spice() for d in devices]
    lines.append(f'.ends {name}')
    return '\n'.join(lines) + '\n'


def safe_net(n):
    return re.sub(r'[^A-Za-z0-9_]', '_', n)
