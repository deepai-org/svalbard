import json, sys
# loads at 60 mA: two banks 26 mA each (MAIN + POST), ser8d + aux 5 mA, mux logic 3 mA
d, ties, out = sys.argv[1], json.loads(sys.argv[2]), sys.argv[3]
scale = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
corner = sys.argv[5] if len(sys.argv) > 5 else 'nom'
VS = [282.9 + 34.5 * p for p in range(9)]          # mux VSS straps (9 um), y 236.12..341.27
VD = [293.4 + 34.5 * p for p in range(8)]          # mux logic VDD straps (5 um), y 236.12..311.67
tails = [dict(name=f'tail_strap{p}', layer='m5', mA=(3.25 if p in (0, 8) else 6.5) * scale, boxes=[[x - 4.5, 236.12, x + 4.5, 341.27]]) for p, x in enumerate(VS)]
loads = dict(VSS=tails + [dict(name='ser8d_logic', layer='m1', mA=5.0 * scale, boxes=[[0, 0, 744.12, 197.68]]),
                          dict(name='mux_logic', layer='m5', mA=3.0 * scale, boxes=[[x - 4.5, 236.12, x + 4.5, 341.27] for x in VS])],
             VDD=[dict(name='header_MAIN', layer='m5', mA=26.0 * scale, boxes=[[382.0, 392.0, 430.0, 400.56]]),
                  dict(name='header_POST', layer='m5', mA=26.0 * scale, boxes=[[430.0, 392.0, 478.0, 400.56]]),
                  dict(name='ser8d_logic', layer='m1', mA=5.0 * scale, boxes=[[0, 0, 744.12, 197.68]]),
                  dict(name='mux_logic', layer='m5', mA=3.0 * scale, boxes=[[x - 2.5, 236.12, x + 2.5, 311.67] for x in VD])])
json.dump(dict(dir=d, nets=['VDD', 'VSS'], loads=loads, ties=ties, corner=corner), open(out, 'w'), indent=0)
