#!/usr/bin/env python3
"""Read-back LVS of a published converter GDS, with negative controls (MANDATE 4 / 4a).

  python3 lvs_readback.py <block> [--gds PATH] [--ref PATH] [--out generated/<block>-lvs-readback.json]

1. Magic 8.3.678 (analog image) reads the GDS from disk, extracts it flat-per-cell (`extract all`, `ext2spice lvs`).
2. Netgen 1.5.316 (gf180mcuD_setup.tcl, device parameters compared) against the reference
   `generated/<block>.lvs_ref.spice` (schematic + antenna diodes) with the PDK standard-cell netlist prepended.
3. Negative controls, each must FAIL: (a) one MOS width in the read-back netlist changed by +50 %; (b) the gate and
   drain nets of one MOS swapped.
Verdicts are parsed from netgen's report text ('Circuits match uniquely' on the top cell and no 'property errors'),
never from exit codes.  The record binds the GDS by sha256.  Exit 0 only if the real run matches and both controls fail.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'lib'))
import convkit as ck  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('block')
ap.add_argument('--gds')
ap.add_argument('--ref')
ap.add_argument('--out')
a = ap.parse_args()
top = f'pt_{a.block}'
gds = Path(a.gds or HERE / 'generated' / f'{a.block}.gds').resolve()
ref = Path(a.ref or HERE / 'generated' / f'{a.block}.lvs_ref.spice').resolve()
out = Path(a.out or HERE / 'generated' / f'{a.block}-lvs-readback.json')
work = HERE.parents[3] / 'scratch' / 'converters' / f'lvs_readback_{a.block}'
if work.exists():
    shutil.rmtree(work)
work.mkdir(parents=True)
shutil.copy(gds, work / f'{top}.gds')
(work / 'rb.tcl').write_text(f"""crashbackups stop
drc off
gds read {top}.gds
load {top}
select top cell
extract all
ext2spice lvs
ext2spice -o {top}.rb.spice
quit -noprompt
""")
r = ck.docker(ck.ANALOG_IMAGE, work, 'export PATH=/foss/tools/bin:$PATH; magic -dnull -noconsole -rcfile '
              '/foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc /work/rb.tcl > rb.log 2>&1', timeout=7200)
rb = work / f'{top}.rb.spice'
assert rb.exists(), (work / 'rb.log').read_text()[-2000:]
std = work / 'std.spice'
r = ck.docker(ck.DIGITAL_IMAGE, work, f'cp {ck.PDK}/libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice /work/std.spice')
(work / 'ref.spice').write_text(std.read_text() + '\n' + ref.read_text())


def verdict(name, layout):
    res = ck.lvs(work, layout, top, 'ref.spice', top, out=f'{name}.txt')   # its match_unique needs a phrase netgen
    # does not print for hierarchical read-backs ('Netlists match with N symmetries'), so the verdict is parsed here
    text = (work / f'{name}.txt').read_text() if (work / f'{name}.txt').exists() else ''
    log = (work / f'{name}.txt.log').read_text()
    prop_err = 'property errors' in (text + log).lower()
    final = res['final'] or ''
    # netgen's own verdict: the last 'Final result' line; symmetries resolved by property value still end in
    # 'Circuits match uniquely.'  Property (W/L/area) differences print 'Property errors were found.'
    return dict(final=final, property_errors=prop_err, does_not_match='do not match' in (text + log),
                passed=bool(final.startswith('Circuits match uniquely') and not prop_err and 'do not match' not in (text + log)))


real = verdict('lvs_real', rb.name)
lines = rb.read_text().splitlines()
mos = [i for i, line in enumerate(lines) if re.match(r'^X\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+[np]fet_03v3\b.*\bw=', line)]
# control (a): +50 % width on a device in the middle of the list (not a macro cell)
i = mos[len(mos) // 2]
la = list(lines)
la[i] = re.sub(r'\bw=([0-9.]+)u', lambda m: f'w={float(m.group(1)) * 1.5:.3f}u', la[i], count=1)
(work / 'neg_w.spice').write_text('\n'.join(la) + '\n')
# control (b): swap gate and drain of another device whose gate and drain differ
j = next(k for k in mos[len(mos) // 3:] if lines[k].split()[1] != lines[k].split()[2])
lb = list(lines)
t = lb[j].split()
t[1], t[2] = t[2], t[1]
lb[j] = ' '.join(t)
(work / 'neg_swap.spice').write_text('\n'.join(lb) + '\n')
neg_w = verdict('lvs_neg_w', 'neg_w.spice')
neg_swap = verdict('lvs_neg_swap', 'neg_swap.spice')
rec = dict(block=a.block, top=top, gds=str(gds.relative_to(HERE)) if gds.is_relative_to(HERE) else str(gds),
           gds_sha256=ck.sha256(gds), reference=ref.name, reference_sha256=ck.sha256(ref),
           extractor='magic (analog image) gds read -> extract all -> ext2spice lvs', lvs='netgen gf180mcuD_setup.tcl',
           images={'analog': ck.ANALOG_IMAGE, 'digital': ck.DIGITAL_IMAGE},
           readback_devices=len(mos), real=real,
           negative_controls={'width_x1.5': dict(neg_w, line=la[i][:120]), 'gate_drain_swap': dict(neg_swap, line=lb[j][:120])})
rec['pass'] = bool(real['passed'] and not neg_w['passed'] and not neg_swap['passed'])
out.write_text(json.dumps(rec, indent=1) + '\n')
print(a.block, 'readback', real['final'], '| neg_w', neg_w['final'], '| neg_swap', neg_swap['final'], '| PASS' if rec['pass'] else '| FAIL')
sys.exit(0 if rec['pass'] else 1)
