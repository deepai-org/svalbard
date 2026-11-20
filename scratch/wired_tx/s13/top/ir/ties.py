import json, sys
g = json.load(open(sys.argv[1])); t = g['ties']; Yt = g['size_um'][1]
edge = lambda b, side: {'top': [b[0], b[3] - 1.0, b[1], b[3]], 'left': [b[0], b[2], b[0] + 1.0, b[3]], 'right': [b[1] - 1.0, b[2], b[1], b[3]]}[side]
ties = dict(VDD=[dict(layer='m5', box=edge(v, 'top')) for v in t['VDD'].values()],
            VSS=[dict(layer='m5', box=edge(t['VSS']['bar_left'], 'left')), dict(layer='m5', box=edge(t['VSS']['bar_right'], 'right'))] +
                [dict(layer='m5', box=edge(v, 'top')) for k, v in t['VSS'].items() if k.startswith('corner')])
print(json.dumps(ties))
