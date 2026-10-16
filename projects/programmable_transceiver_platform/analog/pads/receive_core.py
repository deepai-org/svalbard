"""Attached receiver input load with a physical passive discharge primitive.

The resistor has standalone generated layout; placement and connecting routes
inside the receiver core are not yet implemented. Never count its parasitics
as part of the pad-only GDS or hide it inside the ideal core capacitance budget.
"""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from design import PROJECT

PRIMITIVE = Path(__file__).with_name('generated')/'receiver-core-discharge'/'physical.spice'
LAYOUT = PRIMITIVE.with_name('layout.json')


def embedded_in(physical):
    if physical is None:
        return False
    from extract_audit import key
    # A protected pad also contains diode/MIM instances and a wrapper. Inspect
    # only the exact discharge model; the whole graph is audited at export.
    bleeds=Counter()
    def microns(value):
        match=re.fullmatch(r'([+-]?(?:[0-9.]+)(?:[eE][+-]?[0-9]+)?)([munp]?)',value)
        if not match:raise ValueError('Unknown resistor dimension '+value)
        return float(match[1])*{'':1e6,'m':1e3,'u':1.,'n':1e-3,'p':1e-6}[match[2]]
    for line in physical.read_text().splitlines():
        fields=line.split()
        if len(fields)<5 or not fields[0].startswith('X') or fields[4]!='ppolyf_u_1k_6p0':continue
        if set(fields[1:3])=={'ESD_RAIL','VSS'} and fields[3]=='VSS':continue
        dimensions=dict(item.split('=',1) for item in fields[5:] if '=' in item)
        bleeds[key(fields[4],fields[1:4],microns(dimensions['r_width']),microns(dimensions['r_length']))]+=1
    if not bleeds:
        return False
    expected = {key('ppolyf_u_1k_6p0', ('RX_'+leg, 'VSS', 'VSS'), 1., 319.54): 1
                for leg in ('P', 'N')}
    if bleeds != expected:
        raise ValueError('Unexpected embedded receiver discharge topology or dimensions')
    return True


def model(physical=None):
    if embedded_in(physical):
        return ''
    layout = json.loads(LAYOUT.read_text())
    physical = PRIMITIVE.read_text()
    if hashlib.sha256(physical.encode()).hexdigest() != layout['physical_sha256']:
        raise ValueError('Receiver discharge primitive differs from checked layout')
    if layout['drc_count'] or not layout['extracted_resistor_body_connectivity_checked']:
        raise ValueError('Receiver discharge primitive lacks layout checks')
    for source, digest in layout['source_sha256'].items():
        if hashlib.sha256(Path(source).read_bytes()).hexdigest() != digest:
            raise ValueError('Stale receiver discharge layout source: '+source)
    return physical


def loads(physical=None):
    capacitance = json.loads((PROJECT/'spec/analog-architecture.json').read_text())['blocks']['rxlevel']['parameters']['output_cap_budget_f_per_leg']
    return (''.join(f'CCORE_{leg} RX_{leg} VSS {capacitance}\n' for leg in ('P','N')) +
            ('' if embedded_in(physical) else 'XCORE_DISCHARGE RX_P RX_N VSS receiver_core_flat\n'))


def evidence(physical=None):
    if embedded_in(physical):
        return dict(physical_discharge_included=True,embedded_in_pad=True,
                    scope='Discharge resistors and connecting capacitance are inside the exact extracted pad. Only the shared ideal receiver input capacitance is added externally; distributed route resistance remains absent.')
    layout = json.loads(LAYOUT.read_text())
    return dict(physical_discharge_included=True,
                connected_macro_area_um2=layout['geometry']['area_envelope_um2'],
                scope='Connected two-resistor macro including extracted local return routing, in addition to shared core capacitance. Core placement and pad-to-macro routes, distributed resistance, noise and stress qualification remain open.')
