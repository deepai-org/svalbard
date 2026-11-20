"""Staged tank spiral with a smaller outer diameter (range fix: L about -7 %).  Same method as lcvco/spiral.py main('all')
(closed form + FastHenry of the drawn polyline + Magic layout), written here, published files untouched.
usage: mk.py <dout_um>   -> spiral.json, spiral.spice, layout/pt_spiral_ind.{gds,mag}, fasthenry/"""
import sys, json, re
from pathlib import Path
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing/lcvco')
import spiral as s
H = Path(__file__).resolve().parent
d = float(sys.argv[1])
G = dict(s.G, dout_um=d)
fh = s.fasthenry(G, work=H / 'fasthenry')
p = s.interp(fh['points'], G['f_hz'])
a = s.analytic(G)
ratio = p['L_nH'] / a['L_nH']
# nominal L = the FastHenry value (as the published model: L_NOM = FastHenry / Mohan at 300 um = 0.91)
s.L_NOM = ratio
V = {'pt_spiral': ('nominal', 1.0, ratio), 'pt_spiral_lowq': ('worst', 1.5, ratio),
     'pt_spiral_lhi': ('nominal', 1.0, ratio * 1.10), 'pt_spiral_llo': ('nominal', 1.0, ratio * 0.90),
     'pt_spiral_lhi_lowq': ('worst', 1.5, ratio * 1.10), 'pt_spiral_llo_lowq': ('worst', 1.5, ratio * 0.90)}
rec = dict(geometry=G, fasthenry=fh, fasthenry_vs_model=dict(L_ratio=ratio, R_ratio=p['R_ohm'] / a['Rs_ohm'], fasthenry_at_f=p),
           variants={k: s.analytic(G, *v) for k, v in V.items()})
sp = ['* Tank inductor models, STAGED (scratch/lo-ap4/sp290/mk.py), dout %g um; method as lcvco/spiral.py.' % d, '']
for k, v in V.items():
    sp.append(s.subckt(k, s.analytic(G, *v), f'variant {v}'))
(H / 'spiral.spice').write_text('\n'.join(sp))
lay = H / 'layout'; lay.mkdir(exist_ok=True)
(lay / 'spiral.tcl').write_text(s.layout_tcl(G))
import subprocess
subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '6g', '--user', '1000:1000', '--entrypoint', '/bin/sh',
                '--mount', f'type=bind,src={lay},dst=/work', '-w', '/work', s.DIGITAL_IMAGE, '-c',
                'magic -dnull -noconsole -rcfile /pdk/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc /work/spiral.tcl > magic.log 2>&1'],
               capture_output=True, text=True, timeout=3600)
rec['layout'] = dict(drc=(lay / 'drc.txt').read_text()[:300] if (lay / 'drc.txt').exists() else 'missing', gds=(lay / 'pt_spiral_ind.gds').exists())
(H / 'spiral.json').write_text(json.dumps(rec, indent=1, default=str))
print(json.dumps(dict(L_fh=p, ratio=ratio, nom=rec['variants']['pt_spiral']['L_nH'], q=rec['variants']['pt_spiral']['Q_eff'],
                      q_lowq=rec['variants']['pt_spiral_lowq']['Q_eff'], layout=rec['layout']), default=str))
