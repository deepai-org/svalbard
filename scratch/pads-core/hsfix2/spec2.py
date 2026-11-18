#!/usr/bin/env python3
"""spec2.py <build config.json> > spec.json : netres spec for the ESD paths of pad_hspad (extends ../hsfix/spec_hspad.py, which is not edited).
PAD_P / PAD_N: as spec_hspad.py plus survey from the bond pad (per-terminal R) and per-row diode groups.
VSS_ESD (label VSS, clipped to the shell): ring = the two Metal3 pads of the ring VSS stacks at (10, 78.3) / (221, 78.3);
   device terminals in the diode array (p+ taps = nd2ps anodes and pd2nw SUB rings) and in the clamp region.
ESD_RAIL: pd2nw cathodes (n+ in Nwell) of the array vs the clamp drains (nmos terminals in the clamp region)."""
import json, subprocess, sys, os
H = os.path.dirname(os.path.abspath(__file__))
base = json.loads(subprocess.run([sys.executable, H + '/../hsfix/spec_hspad.py', sys.argv[1]], capture_output=True, text=True, check=True).stdout)
ARR = [140, 440, 182, 680]; CL = [0, 440, 125, 735]; SH = [0, 735, 319, 805]    # diode array, canonical clamp, shunt clamp
row = lambda y: [140, y - 14, 182, y + 14]
nets = []
for n in base['nets']:
    if n['name'] in ('PAD_P', 'PAD_N'):
        rows = (460, 500, 620) if n['name'] == 'PAD_P' else (540, 580, 660)
        n['survey'] = 'bond'
        for y in rows: n['groups'][f'r{y}'] = dict(prefix='dio', window=row(y))
        n['groups']['up'] = dict(prefix='dio', kind='pdiode')
        n['pairs'] = [['bond', 'feed'], ['bond', 'heads'], ['bond', 'diodes'], ['feed', 'heads'], ['feed', 'diodes'], ['bond', 'up']] + [['bond', f'r{y}'] for y in rows]
        n['path_fraction'] = 0.5
        nets.append(n)
g = {f'v{y}': dict(prefix='a', window=row(y), kind='ptap') for y in (460, 500, 540, 580, 620, 660)}
g.update(vP=dict(prefix='a', window=[140, 446, 182, 474], kind='ptap'), vall=dict(prefix='a', kind='ptap'), clampS=dict(prefix='c', kind='nmos'), shuntS=dict(prefix='s', kind='nmos'))
nets.append(dict(name='VSS_ESD', seed=['M4', 136., 460.], clip=[-1, 60, 319, 912], max_step=0.5, min_cuts=4, min_width=2.0, terminals=[
    dict(name='ring', layer='M3', boxes=[[9, 77.3, 11, 79.3], [220, 77.3, 222, 79.3]]), dict(name='ringP', layer='M2', box=[6, 74.4, 14, 75.4]), dict(name='ringN', layer='M2', box=[217, 74.4, 225, 75.4]),
    dict(auto_contacts='a', window=ARR), dict(auto_contacts='c', window=CL), dict(auto_contacts='s', window=SH)],
    groups=g, pairs=[['ring', 'vall'], ['ring', 'shuntS'], ['ring', 'clampS'], ['vall', 'shuntS']] + [['ring', f'v{y}'] for y in (460, 500, 540, 580, 620, 660)]))
g = {f'k{y}': dict(prefix='k', window=row(y), kind='ntap') for y in (500, 580, 620, 660)}
g.update(kall=dict(prefix='k', kind='ntap'), kP=dict(prefix='k', kind='ntap', window=[140, 486, 182, 634]), drains=dict(prefix='d', kind='nmos'), shuntD=dict(prefix='s', kind='nmos'))
nets.append(dict(name='ESD_RAIL', clip=[-1, 396, 319, 912], max_step=0.5, min_cuts=4, min_width=2.0, terminals=[dict(auto_contacts='k', window=ARR), dict(auto_contacts='d', window=CL), dict(auto_contacts='s', window=SH)],
    groups=g, pairs=[['kall', 'shuntD'], ['kall', 'drains'], ['kP', 'shuntD']] + [[f'k{y}', 'shuntD'] for y in (500, 580, 620, 660)]))
print(json.dumps(dict(nets=nets), indent=1))
