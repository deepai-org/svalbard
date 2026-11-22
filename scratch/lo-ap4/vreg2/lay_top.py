"""pt_lo_vreg top-level assembly (hand script): control cell (row engine) + 4 x M2 units + 2 x M1 units + bypass macro,
Metal4 buses (22 um), Metal5 links (20 um), gate rails / risers, ports.  Work dir lay_top/.  usage: lay_top.py [build|check]
Coordinates in um; control cell at the origin, power block above it."""
import sys, json, shutil
from pathlib import Path
T_ = '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing'
sys.path.insert(0, T_)
import layout_engine as le
ROOT = Path(__file__).resolve().parent; work = ROOT / 'lay_top'; TOP = 'pt_lo_vreg'
rep = json.loads((ROOT / 'lay_ctl/layout-report.json').read_text())
CW, T = rep['size_um']; TX = rep['trunk_x']; ST = rep['straps']
m2u = json.loads((ROOT / 'mac_m2/pt_lo_vreg_m2u.json').read_text()); m1u = json.loads((ROOT / 'mac_m1/pt_lo_vreg_m1u.json').read_text()); byp = json.loads((ROOT / 'mac_byp/pt_lo_vreg_byp.json').read_text())
YP = T + 26.0      # r2 (2026-11-22, ASM-8): +12 um channel for the control pins' Metal4 tracks to the west edge
BUS = dict(VOUTA=(0, 22), MID1=(129, 151), VOUTB=(154, 176), MID2=(283, 305), VIN=(412, 434))
ROWA, ROWB, ROW1 = 24.0, 178.0, 307.0
W2, W1 = m2u['size_um'][0], m1u['size_um'][0]; H = m2u['size_um'][1]
XU2 = [0.0, W2 + 6.0]; XU1 = [0.0, W1 + 6.0]; BW = XU2[1] + W2
BX, BY = 310.0, 396.5
L = le.Layout(); R = L.rect
place = []
def y(v): return YP + v
def bus(n): return y(BUS[n][0]), y(BUS[n][1])
def strap_to_bus(x0, sx, sw, y_from, n, up):
    """Metal3 extension of a macro strap into bus n (above if up) + Via3 array."""
    b1, b2 = bus(n); x1, x2 = x0 + sx - sw / 2, x0 + sx + sw / 2
    if up: R('metal3', x1, y_from - 0.5, x2, b2 - 1.0)
    else:  R('metal3', x1, b1 + 1.0, x2, y_from + 0.5)
    R('via3', x1 + 0.5, b1 + 1.5, x2 - 0.5, b2 - 1.5)
for n in BUS: R('metal4', 0, bus(n)[0], BW, bus(n)[1])
for y0, lo, hi in ((ROWA, 'VOUTA', 'MID1'), (ROWB, 'VOUTB', 'MID2')):
    for x0 in XU2:
        place.append(('pt_lo_vreg_m2u', x0, y(y0)))
        for sx in m2u['strap_x']:
            strap_to_bus(x0, sx, m2u['strap_w'], y(y0), lo, False); strap_to_bus(x0, sx, m2u['strap_w'], y(y0 + H), hi, True)
for x0 in XU1:
    place.append(('pt_lo_vreg_m1u', x0, y(ROW1)))
    for sx in m1u['strap_x']:
        strap_to_bus(x0, sx, m1u['strap_w'], y(ROW1), 'MID2', False); strap_to_bus(x0, sx, m1u['strap_w'], y(ROW1 + H), 'VIN', True)
place.append(('pt_lo_vreg_byp', BX, y(BY)))
BH = byp['size_um'][1]
for sx in byp['strap_x']:
    strap_to_bus(BX, sx, byp['strap_w'], y(BY + BH), 'VIN', True)
    R('metal3', BX + sx - 10, y(381), BX + sx + 10, y(BY) + 0.5); R('via3', BX + sx - 9.5, y(381.5), BX + sx + 9.5, y(393.5))
R('metal4', BX + 3, y(380), BX + 79, y(395))                       # bypass drain plate (VOUT)
def link(x1, x2, n1, n2, ytop=None):                               # Metal5 link between two buses (or up to a plate)
    a1, a2 = bus(n1); R('metal5', x1, a1 + 0.5, x2, (ytop if ytop else bus(n2)[1] - 0.5))
    R('via4', x1 + 0.6, a1 + 1.5, x2 - 0.6, a2 - 1.5)
    if ytop is None: R('via4', x1 + 0.6, bus(n2)[0] + 1.5, x2 - 0.6, bus(n2)[1] - 1.5)
link(60, 80, 'VOUTA', 'VOUTB'); link(250, 270, 'MID1', 'MID2'); link(340, 360, 'VOUTB', None, ytop=y(394.5))
R('via4', 340.6, y(381.5), 359.4, y(393.5))
# body ties: Metal1 from the guard rings to the VSS tie at x = -2.5
for y0, xu, w in ((ROWA, XU2, W2), (ROWB, XU2, W2), (ROW1, XU1, W1)):
    R('metal1', -3.0, y(y0) + 3.06, 0.28, y(y0) + 3.46); R('metal1', xu[0] + w - 0.28, y(y0) + 3.06, xu[1] + 0.28, y(y0) + 3.46)
xvss = next(sx for n, sx in ST if n == 'VSS') + 0.3; xvin = next(sx for n, sx in ST if n == 'VIN') + 0.3
R('metal1', -3.0, T + 2.8, -2.0, y(ROW1) + 3.46); L.hwire('metal1', -2.5, xvss, T + 3.0, 0.4)
L.vwire('metal5', xvss, T - 0.9, T + 3.0, 0.44); L.via(xvss, T + 3.0, 1, 5)
L.vwire('metal5', xvin, T - 0.9, y(423), 0.44); L.via(xvin, y(423), 4, 5)
xo = TX['VOUT']; L.vwire('metal5', xo, T - 0.9, y(11), 0.44); L.via(xo, y(11), 4, 5)
# gates: Metal5 stub -> Metal4 track -> Metal3 riser -> Metal2 rail -> macro gate stubs
def gate(net, ytrk, xr, rails):
    xp = TX[net]; L.vwire('metal5', xp, T - 0.9, T + ytrk, 0.44); L.via(xp, T + ytrk, 4, 5); L.hwire('metal4', xp, xr, T + ytrk, 0.4); L.via(xr, T + ytrk, 3, 4)
    ytop = max(r[0] for r in rails); L.vwire('metal3', xr, T + ytrk, ytop, 0.4)
    for yr, xs, ystub in rails:
        L.via(xr, yr, 2, 3); L.hwire('metal2', min(xs + [xr]), max(xs + [xr]), yr, 0.4)
        for x in xs: L.vwire('metal2', x, yr, ystub, 0.4)
g2x = [XU2[0] + m2u['pins']['G'][0], XU2[1] + m2u['pins']['G'][0]]; g1x = [XU1[0] + m1u['pins']['G'][0], XU1[1] + m1u['pins']['G'][0]]
gate('G2', 5.0, 202.08, [(y(ROWA) - 1.0, g2x, y(ROWA) + 0.3), (y(ROWB) - 1.0, g2x, y(ROWB) + 0.3)])
gate('G1', 7.0, 157.0, [(y(ROW1) - 1.0, g1x, y(ROW1) + 0.3)])
gate('BYPN', 9.0, 364.5, [(y(BY) - 1.0, [BX + byp['gate_x']], y(BY) + 0.3)])
cmds = ['crashbackups stop'] + [f'gds read /work/{m}.gds' for m in ('pt_lo_vreg_m2u', 'pt_lo_vreg_m1u', 'pt_lo_vreg_byp')]
cmds += [f'load {TOP}', 'units microns', 'snap internal', 'getcell pt_lo_vreg_ctl child 0 0 parent 0 0', 'identify XCTL']
for k, (m, x, yy) in enumerate(place):
    cmds += [f'getcell {m} child 0 0 parent {le.snap(x)} {le.snap(yy)}', f'identify XP{k}']
SMALL = ('VREF', 'EN', 'BYP', 'TRIM0', 'TRIM1', 'TRIM2', 'ATB_OUT', 'ATB_G')
YTRK = {p_: T + 12.0 + 1.4 * k for k, p_ in enumerate(SMALL)}     # r2: one Metal4 track per control pin, run to the west edge x = -3
for p_ in SMALL:
    R('metal5', TX[p_] - 0.22, T - 1.0, TX[p_] + 0.22, T - 0.5)
    L.vwire('metal5', TX[p_], T - 1.0, YTRK[p_], 0.44); L.via(TX[p_], YTRK[p_], 4, 5)
    L.hwire('metal4', -3.0, TX[p_], YTRK[p_], 0.44)
cmds += L.cmds
PORTS = ['VIN', 'VOUT', 'VSS', 'VREF', 'EN', 'BYP', 'TRIM0', 'TRIM1', 'TRIM2', 'ATB_OUT', 'ATB_G']
pp = dict(VIN=('metal4', BW - 0.5, y(423)), VOUT=('metal4', BW - 0.5, y(165)), VSS=('metal1', -2.5, T + 20))   # r2: VIN / VOUT at the east edge
for p in PORTS[3:]: pp[p] = ('metal4', -2.7, YTRK[p])                                                         # r2: west edge, Metal4
for i, p in enumerate(PORTS, 1):
    ly, x, yy = pp[p]; cmds += [f'box values {le.snap(x-0.15)} {le.snap(yy-0.15)} {le.snap(x+0.15)} {le.snap(yy+0.15)}', f'label {p} FreeSans 0.3 0 0 0 c {ly}', f'port make {i}']
cmds += ['save', 'writeall force', 'quit -noprompt']
info = dict(outline_um=[-3.0, 0.0, BW, y(434)], size_um=[round(BW + 3.0, 2), round(y(434), 2)], ports={p: [pp[p][0], round(pp[p][1], 2), round(pp[p][2], 2)] for p in PORTS},
            buses={n: [0, round(bus(n)[0], 2), round(BW, 2), round(bus(n)[1], 2)] for n in BUS}, ctl=[0, 0, CW, T])
if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'build'
    if mode == 'build':
        if work.exists(): shutil.rmtree(work)
        work.mkdir()
        for f in (ROOT / 'lay_ctl').glob('*.mag'): shutil.copy(f, work / f.name)
        for d, m in (('mac_m2', 'pt_lo_vreg_m2u'), ('mac_m1', 'pt_lo_vreg_m1u'), ('mac_byp', 'pt_lo_vreg_byp')): shutil.copy(ROOT / d / f'{m}.gds', work / f'{m}.gds')
        (work / 'layout.tcl').write_text('\n'.join(cmds) + '\n'); r = le.docker_magic(work, 'layout.tcl'); print('build rc', r.returncode)
        (ROOT / 'lay_top_info.json').write_text(json.dumps(info, indent=1))
    chk = ['crashbackups stop', f'load {TOP}', 'select top cell', 'drc euclidean on', 'drc style drc(full)', 'drc check', 'drc catchup',
           'set f [open drc-count.txt w]', 'puts $f [drc list count total]', 'close $f', 'set f [open drc-details.txt w]', 'puts $f [drc listall why]', 'close $f', 'quit -noprompt']
    (work / 'drc.tcl').write_text('\n'.join(chk) + '\n'); le.docker_magic(work, 'drc.tcl')
    print('drc', (work / 'drc-count.txt').read_text().strip(), (work / 'drc-details.txt').read_text()[:1500])
    print(json.dumps(info['size_um']))
