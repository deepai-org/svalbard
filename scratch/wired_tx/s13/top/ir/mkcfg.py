import json, sys
# loads at 60 mA: two banks 26 mA each (MAIN + POST), ser8d + aux 5 mA, mux logic 3 mA
d, ties, out = sys.argv[1], json.loads(sys.argv[2]), sys.argv[3]
scale = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
corner = sys.argv[5] if len(sys.argv) > 5 else 'nom'
# geometry from the block / mux reports (session 16: mux origin and load clusters moved)
B = json.load(open('../out/report.json')); MR = json.load(open('../../mux3/out/report.json'))
XM, YM = B['mux_origin']; YT = B['size_um'][1]; W = B['size_um'][0]; Y0 = B['seam_um'][0]
VS = [XM + 40.8 + 34.5 * p for p in range(9)]      # mux VSS straps (9 um), to the stack rail
VD = [XM + 51.3 + 34.5 * p for p in range(8)]      # mux logic VDD straps (5 um)
yn, yv = YM + 105.15, YM + 75.55
hb = lambda c: [XM + MR['clusters'][c][0] - MR['geo']['hdr_rail'][c]['width_um'] / 2, YT - 8.5, XM + MR['clusters'][c][0] + MR['geo']['hdr_rail'][c]['width_um'] / 2, YT]
tails = [dict(name=f'tail_strap{p}', layer='m5', mA=(3.25 if p in (0, 8) else 6.5) * scale, boxes=[[x - 4.5, YM, x + 4.5, yn]]) for p, x in enumerate(VS)]
loads = dict(VSS=tails + [dict(name='ser8d_logic', layer='m1', mA=5.0 * scale, boxes=[[0, 0, W, Y0]]),
                          dict(name='mux_logic', layer='m5', mA=3.0 * scale, boxes=[[x - 4.5, YM, x + 4.5, yn] for x in VS])],
             VDD=[dict(name='header_MAIN', layer='m5', mA=26.0 * scale, boxes=[hb('M')]),
                  dict(name='header_POST', layer='m5', mA=26.0 * scale, boxes=[hb('Q')]),
                  dict(name='ser8d_logic', layer='m1', mA=5.0 * scale, boxes=[[0, 0, W, Y0]]),
                  dict(name='mux_logic', layer='m5', mA=3.0 * scale, boxes=[[x - 2.5, YM, x + 2.5, yv] for x in VD])])
json.dump(dict(dir=d, nets=['VDD', 'VSS'], loads=loads, ties=ties, corner=corner), open(out, 'w'), indent=0)
