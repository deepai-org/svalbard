import json, os, sys
# PHASE (env, default A): which channel tabs carry grid VSS (A = left channel of each pair, B = right); the others are VDD channels
ph = os.environ.get('PHASE', 'A')
g = json.load(open(sys.argv[1])); t = g['ties']; Yt = g['size_um'][1]
edge = lambda b, side: {'top': [b[0], b[3] - 1.0, b[1], b[3]], 'bottom': [b[0], b[2], b[1], b[2] + 1.0], 'left': [b[0], b[2], b[0] + 1.0, b[3]], 'right': [b[1] - 1.0, b[2], b[1], b[3]]}[side]
ties = dict(VDD=[dict(layer='m5', box=edge(v, 'top')) for v in t['VDD'].values()],
            VSS=[dict(layer='m5', box=edge(t['VSS']['bar_left'], 'left')), dict(layer='m5', box=edge(t['VSS']['bar_right'], 'right'))] +
                [dict(layer='m5', box=edge(v, 'top')) for k, v in t['VSS'].items() if k.startswith('corner')] +
                [dict(layer='m5', box=edge(v, 'bottom')) for k, v in t['VSS'].items() if k.startswith('bottom') or k.startswith(f'chan{ph}')])
print(json.dumps(ties))
