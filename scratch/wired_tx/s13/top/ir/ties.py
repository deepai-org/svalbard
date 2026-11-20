import json, os, sys
# PHASE (env, default E): which grid axes carry VSS straps (block x 23.5 + 35 k; E = k even, O = k odd).  VSS ties of
# that phase: the channel tabs (chanE_* / chanO_*) and the grid landings (grid_tie_*) on such axes; the others sit under
# grid VDD straps and are not tied.
ph = os.environ.get('PHASE', 'E')
g = json.load(open(sys.argv[1])); t = g['ties']; Yt = g['size_um'][1]
edge = lambda b, side: {'top': [b[0], b[3] - 1.0, b[1], b[3]], 'bottom': [b[0], b[2], b[1], b[2] + 1.0], 'left': [b[0], b[2], b[0] + 1.0, b[3]], 'right': [b[1] - 1.0, b[2], b[1], b[3]]}[side]
par = lambda b: 'EO'[round(((b[0] + b[1]) / 2 - 23.5) / 35.0) % 2]
ties = dict(VDD=[dict(layer='m5', box=edge(v, 'top')) for v in t['VDD'].values()],
            VSS=[dict(layer='m5', box=edge(t['VSS']['bar_left'], 'left')), dict(layer='m5', box=edge(t['VSS']['bar_right'], 'right'))] +
                [dict(layer='m5', box=edge(v, 'top')) for k, v in t['VSS'].items() if k.startswith('corner')] +
                [dict(layer='m5', box=edge(v, 'bottom')) for k, v in t['VSS'].items() if k.startswith('bottom') or (k.startswith('chan') and par(v) == ph)] +
                [dict(layer='m5', box=edge(v, 'top')) for k, v in t['VSS'].items() if k.startswith('grid_tie') and par(v) == ph])
print(json.dumps(ties))
