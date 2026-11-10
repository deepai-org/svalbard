#!/usr/bin/env python3
"""Build the device-level LVS reference for the routed core-bias assembly.

Non-circular by construction: nothing here is read from the routed layout or
from any extraction of it.

* Top-level connectivity: the generated ``pt_core_bias`` top cell
  (integration/core_bias.py output, frozen as the routing flow's input).
* Leaf masters: their SCHEMATIC netlists, the same sources each master was
  separately LVS-qualified against (patched biasgen and bandgap xschem
  netlists from the core-support clean flow, published to
  analog/core_support/lvs_reference/, the generated pt_bias_* sources
  and the bringup_and/bringup_inv schematic). The extracted master models in
  pt_core_bias.spice are used only for their port order, so that the top
  cell's instance lines can be re-expressed by pin name.

Clean-up applied to the reference (and only these):
* parasitic capacitors: the extracted models carried 9128 C elements; leaf
  schematics are used instead, so no parasitic element enters the reference.
  Real MIM capacitors (biasgen C3/C2, bandgap C1) remain as devices.
* pin layout: every instance is re-emitted in the schematic subckt's pin
  order by pin NAME; extraction-only private ports (e.g. bringup_and
  ``a_278_230#``) are dropped.
* biasgen ``avss``: absent from the extracted model (merged into dvss there).
  Design intent (integration/core_bias.py: the biasgen sits on core VDD/VSS)
  binds it to VSS. It is not taken from the layout terminal map.
* PNP naming is a LAYOUT-side Magic recognition alias handled in
  device_lvs.sh (pnp_10p00x00p42 -> pnp_05p00x05p00, same as the qualified
  core-support bandgap LVS); the count is reported and bounded there.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT.parents[1]
DIST = PROJECT/'analog/core_support/distribution/generated'
# Tracked schematic references published by run_core_support.sh (tapeout step)
# from the clean flow's xschem regeneration; hashes checked against SHA256SUMS.
LVS_REFERENCE = PROJECT/'analog/core_support/lvs_reference'
SCHEMATICS = {
    'gf180mcu_ocd_ip__biasgen': LVS_REFERENCE/'gf180mcu_ocd_ip__biasgen_patched.sch.spice',
    'gf180mcu_ocd_ip__bandgap': LVS_REFERENCE/'gf180mcu_ocd_ip__bandgap.sch.spice',
    'pt_bias_root': DIST/'pt_bias_root.spice',
    'pt_bias_vref': DIST/'pt_bias_vref.spice',
    'pt_bias_bank3': DIST/'pt_bias_bank3.spice',
    'pt_bias_bank4': DIST/'pt_bias_bank4.spice',
    'pt_bias_bank5': DIST/'pt_bias_bank5.spice',
    'pt_bias_bank8': DIST/'pt_bias_bank8.spice',
    'bringup_and': PROJECT/'analog/bringup_control/generated/schematic.spice',
}
# Schematic pins that the extracted model does not expose, bound by design
# intent (never from layout). Anything else missing is an error.
INTENT = {('gf180mcu_ocd_ip__biasgen', 'avss'): 'VSS'}


def unfold(text):
    return re.sub(r'\n\+\s*', ' ', text)


def subckts(text):
    text = unfold(text)
    found = {}
    for m in re.finditer(r'^\.subckt\s+(\S+)\s*([^\n]*)\n(.*?)^\.ends', text, re.M | re.S | re.I):
        found[m[1]] = (m[2].split(), m[3])
    return found


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def closure(name, library, seen):
    """Subckt definitions reachable from ``name`` inside one schematic file."""
    if name in seen or name not in library:
        return []
    seen.add(name)
    pins, body = library[name]
    out = []
    for line in body.splitlines():
        if line[:1].lower() == 'x':
            fields = [f for f in line.split() if '=' not in f]
            out += closure(fields[-1], library, seen)
    return out+[f'.subckt {name} '+' '.join(pins)+'\n'+body+'.ends\n']


def check_published():
    sums = dict(reversed(l.split()) for l in (LVS_REFERENCE/'SHA256SUMS').read_text().splitlines() if l.strip())
    for path in SCHEMATICS.values():
        if path.parent == LVS_REFERENCE:
            assert sums.get(path.name) == sha(path), ('LVS reference does not match SHA256SUMS', path)


def build(extracted_path, output, mutate=None):
    check_published()
    extracted = subckts(Path(extracted_path).read_text())
    top_pins, top_body = extracted['pt_core_bias']
    text, sources, schematic_pins, emitted = [], {}, {}, set()
    text.append('* Device-level LVS reference for pt_core_bias (see device_lvs_reference.py)')
    for master, path in SCHEMATICS.items():
        sources[str(path)] = sha(path)
        library = subckts(path.read_text())
        assert master in library, (master, path)
        schematic_pins[master] = library[master][0]
        for block in closure(master, library, emitted):
            # No parasitic elements may enter: schematic C elements are real
            # MIM devices instantiated as X...cap_mim subckts, never bare C.
            assert not re.search(r'^C', block, re.M), (master, 'bare C element in schematic')
            text.append(block)
    lines, dropped, intent_bound, instances = [], 0, [], 0
    for line in top_body.splitlines():
        if not line.strip() or line.startswith('*'):
            continue
        fields = line.split()
        assert fields[0][0] in 'Xx', ('unexpected top-level element', line)
        master, nets = fields[-1], fields[1:-1]
        model_pins = extracted[master][0]
        assert len(model_pins) == len(nets), line
        by_pin = dict(zip(model_pins, nets))
        ordered = []
        for pin in schematic_pins[master]:
            if pin in by_pin:
                ordered.append(by_pin.pop(pin))
            else:
                assert (master, pin) in INTENT, (fields[0], master, 'schematic pin unbound', pin)
                ordered.append(INTENT[(master, pin)])
                intent_bound.append(f'{fields[0]}.{pin}={INTENT[(master, pin)]}')
        for pin, net in by_pin.items():
            # Only extraction-exported private nodes may be dropped: Magic
            # a_x_y# names, or ports core_bias.py bound to a per-instance
            # '<label>_private_<n>' net that nothing else touches.
            assert '#' in pin or '_private_' in net, (fields[0], master, 'model pin absent from schematic', pin)
            assert sum(net in l.split() for l in top_body.splitlines()) == 1, (fields[0], pin, net, 'private net shared')
            dropped += 1
        lines.append(' '.join([fields[0]]+ordered+[master]))
        instances += 1
    if mutate:
        # Negative control: swap two nets on one instance; LVS must fail.
        index = next(i for i, l in enumerate(lines) if l.startswith(mutate['instance']+' '))
        f = lines[index].split()
        a, b = f.index(mutate['a']), f.index(mutate['b'])
        f[a], f[b] = f[b], f[a]
        lines[index] = ' '.join(f)
    text.append('.subckt pt_core_bias '+' '.join(top_pins)+'\n'+'\n'.join(lines)+'\n.ends\n')
    Path(output).write_text('\n'.join(text)+'\n')
    return dict(instances=instances, dropped_private_ports=dropped, intent_bound_pins=intent_bound,
                schematic_sources=sources, extracted_port_source=dict(path=str(extracted_path), sha256=sha(extracted_path)),
                parasitic_capacitors_in_extracted_models=len(re.findall(r'^C', unfold(Path(extracted_path).read_text()), re.M)),
                mutation=mutate)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--extracted', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--mutate', help='JSON {"instance":..., "a":net, "b":net} for a negative control')
    a = ap.parse_args()
    print(json.dumps(build(a.extracted, a.output, json.loads(a.mutate) if a.mutate else None), indent=1))
