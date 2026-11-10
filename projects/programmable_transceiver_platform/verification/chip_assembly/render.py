"""SVG view of the floorplan (die, core, pad families, blocks, decap, PDN/buses)."""
import json
from pathlib import Path

COLOR = {'rf': '#d62728', 'conv': '#2ca02c', 'pll': '#9467bd', 'wired': '#1f77b4', 'debug': '#ff7f0e', 'core': '#7f7f7f'}


def svg(fp, extra=None, die=(3932, 5122)):
    s = 0.2
    W, H = die[0]*s, die[1]*s
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.0f} {H:.0f}">',
           '<rect width="100%" height="100%" fill="white"/>']

    def rect(r, fill, op=.6, stroke='none', label=None, fs=5):
        x, y = r[0]*s, H-r[3]*s
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{(r[2]-r[0])*s:.1f}" height="{(r[3]-r[1])*s:.1f}" '
                   f'fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="0.5"/>')
        if label:
            out.append(f'<text x="{x+1:.1f}" y="{y+fs+1:.1f}" font-size="{fs}" font-family="sans-serif">{label}</text>')
    rect((0, 0, die[0], die[1]), 'none', 0, 'black')
    rect((442, 442, 3490, 4680), 'none', 0, '#999')
    for f in fp['fixed']:
        rect(f['rect'], '#333' if f['kind'] == 'pad_family' else '#e8d44d', .35, 'black', f['name'], 6)
    for p in fp['placed']:
        rect(p['rect'], COLOR[p['island']], .65, 'black', None if p['name'].startswith('atb') else p['name'], 4)
    for d in fp['decaps']:
        rect(d['rect'], COLOR[d['island']], .2, COLOR[d['island']], d['name'], 5)
    for isl, r in (fp.get('island_regions') or {}).items():
        rect(r, 'none', 0, COLOR[isl])
    for item in (extra or []):
        rect(item['rect'], item.get('color', '#000'), item.get('opacity', .8))
    out.append('</svg>')
    return '\n'.join(out)


if __name__ == '__main__':
    import sys
    work = Path(sys.argv[1])
    fp = json.loads((work/'floorplan.json').read_text())
    extra = json.loads((work/'pdn-shapes.json').read_text()) if (work/'pdn-shapes.json').exists() else None
    (work/'floorplan.svg').write_text(svg(fp, extra))
