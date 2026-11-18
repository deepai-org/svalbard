#!/usr/bin/env python3
"""Negative control for block_drc.py: layouts that are known to violate, under the same four configurations.
  deck_negctl.py <outdir>
(a) the PDK's own unit layouts for the two rule files whose code changed between f6eeac7 and 792ef67
    (792ef67 drc/testing/unit/comp.gds with decks=comp, contact.gds with decks=contact; variant D, deep mode,
    so the counts are compared between configurations, not with the PDK's golden files, which are variant C flat);
(b) analog/converters/generated/adc_i.gds, which has 7 known antenna violations (signoff-gap finding 6b).
Result: <outdir>/negctl.json."""
import json, os, shutil, sys
import block_drc as B
out = os.path.abspath(sys.argv[1]); wd = os.path.join(out, 'work', 'negctl'); os.makedirs(wd, exist_ok=True)
unit = os.path.join(B.NEW, 'libs.tech/klayout/tech/drc/testing/unit')
B.DECKS.update({'comp': 'comp', 'contact': 'contact'})
jobs = [('unit_comp', os.path.join(unit, 'comp.gds'), None, 'comp'), ('unit_contact', os.path.join(unit, 'contact.gds'), None, 'contact'),
        ('adc_i', os.path.join(B.PROJ, 'analog/converters/generated/adc_i.gds'), 'pt_adc_i', 'antenna'), ('adc_i', None, 'pt_adc_i', 'main')]
R = {}; last = None
for name, src, top, deck in jobs:
    gds = os.path.join(wd, name + '.gds')
    if src: shutil.copyfile(src, gds)
    if top is None:                                   # unit layouts: single top cell, name read with the project KLayout
        import subprocess
        open(os.path.join(wd, 't.py'), 'w').write('import pya\nl=pya.Layout(); l.read("/in/in.gds"); print("TOP", l.top_cell().name)\n')
        p = subprocess.run(B.BASE + ['-v', f'{gds}:/in/in.gds:ro', '-v', f'{wd}:/wd', '--entrypoint', '/bin/bash', B.KL309, '-c',
                           'export PATH=$PATH:/foss/tools/klayout LD_LIBRARY_PATH=/foss/tools/klayout; klayout -b -zz -r /wd/t.py'], capture_output=True, text=True)
        top = [l.split()[1] for l in p.stdout.splitlines() if l.startswith('TOP')][0]
        R.setdefault(name, {})['_top'] = top
    for cfg in ('P', 'L', 'X1', 'X2'):
        R.setdefault(name, {}).setdefault(cfg, {})[deck] = B.kl(cfg, gds, top, deck, wd)
        json.dump(R, open(os.path.join(out, 'negctl.json'), 'w'), indent=1)
        print(name, cfg, deck, R[name][cfg][deck].get('total'), R[name][cfg][deck].get('error', ''), flush=True)
for name, top in (('unit_comp', None), ('adc_i', 'pt_adc_i')):      # Magic sees violations too (both versions)
    gds = os.path.join(wd, name + '.gds')
    if top is None: top = R[name].get('_top')
    for cfg in ('P', 'L'):
        R[name][cfg]['magic'] = B.magic(cfg, gds, top, wd); print(name, cfg, 'magic', R[name][cfg]['magic'].get('total'), flush=True)
json.dump(R, open(os.path.join(out, 'negctl.json'), 'w'), indent=1)
for f in os.listdir(wd):
    if f.endswith('.gds'): os.remove(os.path.join(wd, f))
