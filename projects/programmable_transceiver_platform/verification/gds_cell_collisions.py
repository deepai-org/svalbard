#!/usr/bin/env python3
"""Fail on cell-name collisions across the chip's block GDS inputs.

Full-chip assembly reads every block GDS into one layout; two different cells that share a name
(e.g. a layout kit's generic `prim_0`) are silently merged, so one block ends up with another
block's device.  This check hashes every cell's own geometry (shapes per layer, plus its child
instances by name and transform) in each GDS of kl_block_drc_blocks.json (plus --gds extras)
and fails when one name maps to differing content in two inputs.  Identical copies (the same
PDK PCell or IO cell in two blocks) are fine.

  gds_cell_collisions.py [--gds extra.gds ...] [--json OUT]
"""
import argparse, json, os, pathlib, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
IMAGE = "sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305"

INNER = r'''
import pya, hashlib, json, sys
out = {}
for path in json.load(open('/w/inputs.json')):
    ly = pya.Layout(); ly.read('/r/' + path)
    cells = {}
    for c in ly.each_cell():
        h = hashlib.sha256()
        for li in ly.layer_indexes():
            info = ly.get_info(li)
            items = sorted(str(s.polygon if s.is_polygon() or s.is_box() or s.is_path() else s)
                           for s in c.shapes(li).each() if not s.is_text())
            if items:
                h.update(f'{info.layer}/{info.datatype}:'.encode()); h.update('|'.join(items).encode())
        for inst in sorted(f'{ly.cell(i.cell_index).name}@{i.cplx_trans}x{i.size()}' for i in c.each_inst()):
            h.update(inst.encode())
        cells[c.name] = h.hexdigest()[:16]
    out[path] = cells
json.dump(out, open('/w/hashes.json', 'w'))
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gds', action='append', default=[])
    ap.add_argument('--json')
    a = ap.parse_args()
    reg = json.loads((HERE / 'kl_block_drc_blocks.json').read_text())['blocks']
    paths = []
    for b in reg.values():
        p = pathlib.Path(b['gds'])
        p = p if p.is_absolute() else REPO / p
        if p.exists() and str(p) not in paths:
            paths.append(str(p))
    paths += [str(pathlib.Path(g).resolve()) for g in a.gds]
    rel = [os.path.relpath(p, REPO) for p in paths]
    with tempfile.TemporaryDirectory(dir=REPO / 'scratch') as w:
        pathlib.Path(w, 'inputs.json').write_text(json.dumps(rel))
        pathlib.Path(w, 'inner.py').write_text(INNER)
        r = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--user', f'{os.getuid()}:{os.getgid()}',
                            '-v', f'{REPO}:/r:ro', '-v', f'{w}:/w', '--entrypoint', '/foss/tools/klayout/klayout',
                            IMAGE, '-b', '-r', '/w/inner.py'], capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stdout[-2000:] + r.stderr[-2000:])
        hashes = json.loads(pathlib.Path(w, 'hashes.json').read_text())
    by_name = {}
    for path, cells in hashes.items():
        for name, h in cells.items():
            by_name.setdefault(name, {}).setdefault(h, []).append(path)
    bad = {n: v for n, v in by_name.items() if len(v) > 1}
    for n, v in sorted(bad.items()):
        print(f'COLLISION {n}: ' + '; '.join(f'{h}: {", ".join(ps)}' for h, ps in v.items()))
    print(f'{len(hashes)} GDS inputs, {len(by_name)} cell names, {len(bad)} names with differing content')
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(dict(inputs=rel, collisions=bad), indent=1) + '\n')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
