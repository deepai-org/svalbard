#!/usr/bin/env python3
"""pad_txpad a16 -> a16p: router-friendly core pins (assembly 2026-11-24; no device / netlist change).

    python3 tx_top_pins.py <a16.gds> <out.gds>          (KLayout python, e.g. inside the pad image)

a16 has seven Metal4 control-cell trunks ending on the top edge at 1 um pitch, 0.4 um wide (TERM_ENABLE 6.8,
PAD_P 7.8, PAD_N 8.8, DETECT_PBIAS 9.8, DETECT_ENABLE 10.8, VSS 12.5 (1 um), VDD 14.5 (1 um)); the router shorted
WIRE_TX_P/N there. This moves the five 0.4 um signal pins to 1.2 um Metal4 pins at 3.0 um pitch, x 16.6-29.8, and
cuts their trunks below the edge. VDD / VSS keep their 1 um pins. TERM_VCM's top Metal4 pad shrinks from x 25-75 to
30.4-75 (its Via4s under x < 30.4 go; the rest of the array and the Metal5 plate stay).

Fan-out (free space checked on a16 combined.gds: no Metal2/3 above y 697.56 for x < 30.4; no Metal3 above 695.56 for
x < 17.98; no Metal4 at x 15-30.4 above 697.56 except TERM_VCM's pad):
  DETECT_ENABLE : Metal3 y 696.90-697.40 -> pin x 16.6-17.8
  DETECT_PBIAS  : Metal3 y 697.95-698.45 -> pin x 19.6-20.8
  PAD_N         : Metal3 y 698.95-699.45 -> pin x 22.6-23.8
  PAD_P         : Metal2 y 697.95-698.45 -> pin x 25.6-26.8   (via2 + via3 stacks at both ends)
  TERM_ENABLE   : Metal2 y 698.95-699.45 -> pin x 28.6-29.8
"""
import sys
import klayout.db as k

TOP = 699.76
L = dict(m2=(36, 0), m3=(42, 0), m4=(46, 0), m5=(81, 0), v2=(38, 0), v3=(40, 0), v4=(41, 0), m4pin=(46, 10))
# net, trunk x, row layer, row y0, y1, pin x0, x1
NETS = [('DETECT_ENABLE', 10.8, 'm3', 696.90, 697.40, 16.6, 17.8),
        ('DETECT_PBIAS', 9.8, 'm3', 697.95, 698.45, 19.6, 20.8),
        ('PAD_N', 8.8, 'm3', 698.95, 699.45, 22.6, 23.8),
        ('PAD_P', 7.8, 'm2', 697.95, 698.45, 25.6, 26.8),
        ('TERM_ENABLE', 6.8, 'm2', 698.95, 699.45, 28.6, 29.8)]
VCM_X0 = 30.4


def main(src, dst):
    ly = k.Layout(); ly.read(src); top = ly.top_cell(); u = ly.dbu
    li = {n: ly.layer(*v) for n, v in L.items()}
    B = lambda x0, y0, x1, y1: k.Box(round(x0 / u), round(y0 / u), round(x1 / u), round(y1 / u))
    add = lambda n, x0, y0, x1, y1: top.shapes(li[n]).insert(B(x0, y0, x1, y1))

    def cut(layer, region_box, keep_below=None):
        """Clip the polygons of `layer` touching region_box (texts untouched); returns the number of clipped pieces."""
        sh = top.shapes(li[layer]); clip = k.Region(region_box)
        hit = [s for s in sh.each_touching(region_box) if not s.is_text() and (k.Region(s.polygon) & clip).count()]
        r = k.Region([s.polygon for s in hit]); n = (r & clip).count()
        for s in hit: sh.erase(s)
        sh.insert(r - clip)
        return n

    # 1. trunk tops: clip each moved trunk above its row top (Metal4 x trunk+-0.2)
    for net, xt, lay, y0, y1, px0, px1 in NETS:
        assert cut('m4', B(xt - .2, y1, xt + .2, TOP)) == 1, net
    # 2. TERM_VCM Metal4 pad x < 30.4 and its Via4s there
    assert cut('m4', B(24.9, 698.0, VCM_X0, TOP)) == 1
    v4 = top.shapes(li['v4']); keep = [s.box for s in v4.each() if not (s.box.bottom >= round(698.0 / u) and s.box.right <= round(VCM_X0 / u))]
    nv = v4.size() - len(keep); v4.clear(); [v4.insert(b) for b in keep]
    # 3. pins and their old labels
    for lay in ('m4pin', 'm4'):
        sh = top.shapes(li[lay]); drop = [s for s in sh.each() if s.is_text() and s.text_string in [n[0] for n in NETS]
                                         and s.text.y >= round(698.0 / u)]
        for s in drop: sh.erase(s)
    pins = top.shapes(li['m4pin'])
    for s in [s for s in pins.each() if not s.is_text() and s.bbox().bottom >= round(699.0 / u)
              and any(abs(s.bbox().center().x * u - n[1]) < .15 for n in NETS)]:
        pins.erase(s)
    xct = top.shapes(li['m4'])
    for s in list(xct.each()):
        if s.is_text() and s.text_string.startswith('XCTL.') and s.text_string[5:] in [n[0] for n in NETS] and s.text.y > round(699 / u):
            xct.erase(s)
    for net, xt, lay, y0, y1, px0, px1 in NETS:
        ym = (y0 + y1) / 2
        # trunk end via3 (Metal4 trunk -> Metal3), plus via2 down to Metal2 for Metal2 rows
        add('m3', xt - .2, y0, xt + .2 if lay == 'm2' else px1, y1)
        add('v3', xt - .13, ym - .13, xt + .13, ym + .13)
        if lay == 'm2':
            add('m2', xt - .2, y0, px1, y1); add('v2', xt - .13, ym - .13, xt + .13, ym + .13)
            add('m3', px0, y0, px1, y1)
            for xv in (px0 + .3, px1 - .3): add('v2', xv - .13, ym - .13, xv + .13, ym + .13)
        for xv in (px0 + .3, px1 - .3): add('v3', xv - .13, ym - .13, xv + .13, ym + .13)
        add('m4', px0, y0, px1, TOP)
        add('m4pin', px0, TOP - .5, px1, TOP)
        top.shapes(li['m4pin']).insert(k.Text(net, k.Trans(round((px0 + px1) / 2 / u), round((TOP - .25) / u))))
        top.shapes(li['m4']).insert(k.Text(net, k.Trans(round((px0 + px1) / 2 / u), round((TOP - .25) / u))))
    ly.write(dst)
    print(f'moved {len(NETS)} pins; TERM_VCM pad now x {VCM_X0}-75; via4 removed {nv}')


if __name__ == '__main__':
    main(*sys.argv[1:3])
