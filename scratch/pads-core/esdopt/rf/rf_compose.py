#!/usr/bin/env python3
"""Option-A composer for the rf-shell families (pad_rf_pair, pad_rftxpad, pad_single_leg). KLayout python (pad image).

    python3 rf_compose.py <family> <pin-variant.gds> <out.gds> '<site opt JSON>'

Input = the pin-move variant (../pins/b/<family>.gds: published cell + top-edge pins, nothing removed).
1. Ring stack: the shell ties VSS to the ring with a 2 x 2 um Metal2..Metal5 stack per site at (9-11, 77.3-79.3)
   (and (220-222, ...) on the pair). Its Via3 / Via4 are off the provider rail via grid (SO-1). With the site primaries
   VSS lands on ring Metal3 through their Via2 landings, so the stack keeps Metal2 / Via2 / Metal3 and loses
   Via3 / Via4 / Metal4 / Metal5 (as hs_pad_compose.py --site-primary).
2. Site primaries (pad_site_primary.draw) at site x0 = 0 (PAD_P) and 211 (PAD_N, pairs only). rf shell neck: Metal2
   x 25.5-49.5 (24 um), VSS strip x 6-14.
3. Labels: DVDD on each site's Metal3 landing (ring landing port), only if the site has up-diodes.
Writes <out.gds> and <out>.json (counts, site info).
"""
import sys, json
import klayout.db as k
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
import pad_site_primary as sp

PRIM = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads/generated/protection-primitives'
SITES = {'rf_pair': [(0., 'PAD_P'), (211., 'PAD_N')], 'rftxpad': [(0., 'PAD_P'), (211., 'PAD_N')], 'single_leg': [(0., 'PAD_P')]}
BASE = dict(neck=(25.5, 49.5), vss_strip=(6., 14.))


def main(fam, src, dst, optjson):
    L = k.Layout(); L.read(src); top = L.top_cell()
    opt = dict(sp.OPT, **BASE); opt.update(json.loads(optjson or '{}'))
    # 1. ring stacks
    removed = {}
    for x0, _ in SITES[fam]:
        w = k.DBox(x0 + 8.9, 77.2, x0 + 11.1, 79.4)
        for ln in (40, 41, 46, 81):
            li = L.find_layer(ln, 0)
            it = top.begin_shapes_rec_touching(li, w)
            hits = []
            while not it.at_end():
                bb = it.shape().dbbox().transformed(it.dtrans())
                if w.contains(bb.p1) and w.contains(bb.p2): hits.append(it.shape())
                it.next()
            for s in hits: s.delete()
            removed[f'{x0:g}/{ln}'] = len(hits)
            it = top.begin_shapes_rec_touching(li, w)
            if not it.at_end() and ln in (40, 41):
                raise SystemExit(f'ring stack cut left at site {x0} layer {ln}')
    # 1b. (opt 'pin_vias') the PAD trunk Metal4 -> Metal5 hand-over to the top pin is ONE Via4 cut per leg (netres r1: 100 % of the
    #     bond -> pin current, 4.5 / 15 ohm of 13.3 / 27.7): replace it by an array over the existing Metal4 x Metal5 overlap (no new metal)
    vias = {}
    if opt.pop('pin_vias', False):
        for x0, pad in SITES[fam]:
            bx = (282., 410., 294., 422.) if pad == 'PAD_P' else (298., 426., 310., 438.)
            w = k.DBox(*bx); li = L.find_layer(41, 0); hits = []
            it = top.begin_shapes_rec_touching(li, w)
            while not it.at_end(): hits.append(it.shape()); it.next()
            if len(hits) != 1: raise SystemExit(f'pin_vias: expected one Via4 in {bx}, found {len(hits)}')
            hits[0].delete(); n = 0
            x, y = bx[0] + .6, bx[1] + .6
            while x <= bx[2] - .6 + 1e-9:
                y = bx[1] + .6
                while y <= bx[3] - .6 + 1e-9:
                    top.shapes(L.layer(41, 0)).insert(k.DBox(x - .13, y - .13, x + .13, y + .13)); n += 1; y += .7
                x += .7
            vias[pad] = n
    # 2. site primaries
    sp.load_primitives(L, PRIM)
    sites = {}
    for x0, pad in SITES[fam]:
        info = sp.draw(L, top, x0, opt)
        if opt['n_up'] or opt.get('n_up_left', 0):
            top.shapes(L.layer(42, 10)).insert(k.DText('DVDD', k.DTrans(*info['dvdd_label'])))
        sites[pad] = info
    L.write(dst)
    json.dump(dict(family=fam, src=src, opt=opt, ring_stack_removed=removed, pin_vias=vias, sites=sites), open(dst[:-4] + '.json', 'w'), indent=1)
    print('removed', removed)


if __name__ == '__main__':
    main(*sys.argv[1:5])
