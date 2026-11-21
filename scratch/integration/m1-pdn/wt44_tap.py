#!/usr/bin/env python3
"""WT44: VDD drop + VSS rise at the pt_wiredtx8 tap (wtx_mux8 position of the assembly floorplan), pt_wired W, POST on, all
bonds, bond map as it stands (bidir[22] = VDD), per-region coverage as drawn with ME / SE >= 12 % on every net and layer,
nominal and pessimistic sets, worst currents with the digital macro at 81.8 mA. Block current BLK mA (WT44: 50-56, POST
included) replaces wiredtx8 + wtx_post; pad tail unchanged; the chip total stays 432 mA (difference added
to the raw-rail macro load). The strap from the switch to the tap is at its 15 mV
requirement (G5), included. Usage: PDN_ASSEMBLY=1 wt44_tap.py [blk=56] [rx=east|old] [tx=slot|ab]"""
import sys, json
import loads as LD
pb = LD.pb
D = dict(a.split('=', 1) for a in sys.argv[1:]); BLK = float(D.get('blk', 56))
for k, r in enumerate(pb.MEASURED):
    if r[0] == 'wiredtx8': pb.MEASURED[k] = (r[0], r[1], {**r[2], 'W': (BLK, BLK)}, *r[3:])
    if r[0] == 'wtx_post': pb.MEASURED[k] = (r[0], r[1], {'W': (0.0, 0.0)}, *r[3:])
import model as M, core as C, chipcfg as P2
P2.apply('wired')
P2.DIG['worst_unscaled'] += 84.0-BLK      # chip total kept at 432 mA: the difference to the 84 mA booked block goes on the raw rail (macro)
if D.get('rx') == 'old': r = M.RECTS['isw_wired_rx']; M.RECTS['isw_wired_rx'] = [3286.0, 740.0, 3286+r[2]-r[0], 740+r[3]-r[1]]
if D.get('blkxy'):                          # blkxy=x0,y0: move the pt_wiredtx8 block (lower-left corner)
    x0, y0 = map(float, D['blkxy'].split(',')); r = M.RECTS['wtx_mux8']; M.RECTS['wtx_mux8'] = [x0, y0, x0+r[2]-r[0], y0+r[3]-r[1]]
if D.get('tx') == 'ab': M.RECTS['isw_wired_tx'] = M.RECTS['isw_wired_tx_a']
elif D.get('tx', 'slot') != 'slot':         # tx=x,y: centre of the switch pair
    x, y = map(float, D['tx'].split(',')); M.RECTS['isw_wired_tx'] = [x-10, y-10, x+10, y+10]
REG = json.load(open(f'{M.ROOT}/scratch/integration/assembly-wired/place.json'))['pdn_regions_pct']
for it in D.get('set', 'ME:12;SE:12').split(';'):
    r, c = it.split(':'); REG[r] = {k: max(v, float(c)) for k, v in REG[r].items()}
def cov(x, y, net, layer):
    cx = min(2, int(3*(x-M.CORE[0])/(M.CORE[2]-M.CORE[0]))); cy = min(2, int(3*(y-M.CORE[1])/(M.CORE[3]-M.CORE[1])))
    return REG['SMN'[cy]+'WCE'[cx]][f'{net.upper()}_{layer}']/100.0
for s in ('nom', 'pess'):
    p = P2.pset(s, core_ring_w=14, ring_core_w=14); p['cov_region'] = cov
    n, info, ports, vict = C.full(p, decap=P2.plan(), x_feed=P2.X_FEED)
    d = C.dc(n, info, 'W', 'pd2u', x_feed=P2.X_FEED); v = d['blocks']['wiredtx8']
    print(f"{s:4s} rx={D.get('rx', 'east')} tx={D.get('tx', 'slot')} block {BLK:g} mA, chip {d['total_mA']:.0f} mA: tap drop {(3.267-v['rail'])*1e3:.1f} mV "
          f"(to switch {v['pre_switch_mV']:.1f}, switch {v['switch_mV']:.1f}, strap {v['strap_mV']:.1f}, VSS rise {v['vss_mV']:.1f})")
    x, y = M.centre('wtx_mux8'); sx, sy = M.centre('isw_wired_tx'); dist = abs(x-sx)+abs(y-sy)
    other = (3.267-v['rail'])*1e3-v['strap_mV']; allow = float(D.get('budget', 105.5))-other
    print(f"     switch-to-block {dist:.0f} um; for <= {D.get('budget', 105.5)} mV at the tap the strap may drop {allow:.1f} mV: Metal5 (0.070 ohm/sq) "
          + (f"{0.070*dist*BLK*1e-3/(allow*1e-3):.0f} um wide" if allow > 0 else 'impossible (rest alone exceeds the budget)'))
