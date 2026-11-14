#!/usr/bin/env python3
"""PD21 low-C SATA/PCIe RX pad pair `pad_hspad` = protection shell + two pt_hs_leg blocks.

  shell : protection_pad_ss pair on network-gc-d2 (x2 up-diodes), escape 8 um, 12 um trunks, 4 um boundary pins
          (PAD_P x 286-290, PAD_N x 302-306 at y 912.91)
  legs  : pt_hs_leg (hs_leg_layout.py); P mirrored (M90) at x 285, N at x 326, bottom y 925
  straps: PAD_P straight up (M5 x 288) / PAD_N jog (M5 y 917 to x 323) into the legs' PAD trunks (M4, via4);
          shared leg nets joined by M5 straps above the legs; RAILPRE (precharge diode) down the N bank (M4 x 313.8)
          to the shell ATB_ESD_RAIL tap (M3 y 436.5 -> x 91.58); leg VSS down (M4 x 316) to the pad return
          (M3 y 428 -> M5 return vertical at x 138).
    python3 hs_pad_compose.py <work> <shell dir> <leg dir> <network dir> [--stacked]

  --stacked (area pass 4, 2026-11-13; RX pins co-located for review condition 2): same shell, same leg master, legs
          stacked BESIDE the shell instead of above it, so the cell keeps the 912.91 um shell depth (bbox 492 x 912.91
          instead of 478 x 1111.25, -0.088 mm2 of core). P leg (unmirrored) at x 340, y 440; N leg MIRRORED in y (M0) above
          it, so both legs' trunk ends (leg "top") face one 42 um channel between them and everything in the channel
          is mirror-symmetric about its midline.
          PAD_P: M5 at y 414-418 from the shell PAD_P trunk (M5 x 282-294, starts y 410) under the start of the PAD_N
          trunk (y 426: no P/N crossing), then up the P leg PAD trunk; PAD_N: M5 strap from the shell PAD_N trunk
          (x 298-310) to the N leg PAD trunk, plus an unconnected-end M5 balance stub that mirrors the PAD_P run over
          the bank (pad P/N C balance).
          Shared nets: the M4 trunks of the two legs are joined straight across the channel; every port net also gets
          a 1 um M5 strap to the side edge (x 492), 5 levels below and 4 above the RX pair.
          RX_P / RX_N: mirror-identical routes (M4 trunk extension 18 um, 0.6 um M5 strap) to ADJACENT side pins at
          x 492, 6 um apart, in the middle of the channel. RAILPRE / VSS down from the P-leg bank exactly as before.
"""
import json, re, shutil, subprocess, sys, hashlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
LEGX_P, LEGX_N, LEGY = 285., 326., 925.
SHARED = ['VSS', 'VDD', 'TERM_VCM', 'TERM_ENABLE', 'TERM_TRIM0', 'TERM_TRIM1', 'TERM_TRIM2', 'TERM_TRIM3', 'VBIAS', 'RAILPRE']
PORTS = ['PAD_P', 'PAD_N', 'RX_P', 'RX_N', 'VBIAS', 'TERM_VCM', 'TERM_ENABLE', 'TERM_TRIM0', 'TERM_TRIM1', 'TERM_TRIM2', 'TERM_TRIM3', 'VDD', 'VSS']


def assemble(work):
    import klayout.db as k
    cfg = json.loads((work / 'config.json').read_text())
    if cfg.get('stacked'):
        return assemble_stacked(work, cfg)
    tx = cfg['trunk_x']; ltop = cfg['leg_top']
    l = k.Layout(); l.read(str(work / 'shell.gds'))
    shell = l.cell('rf_protected_pad_pair')
    l.read(str(work / 'leg.gds')); leg = l.cell('pt_hs_leg')
    for c in l.each_cell():
        for ix in l.layer_indexes():
            for s in list(c.each_shape(ix)):
                if s.is_text(): s.delete()
    root = l.create_cell('pad_hspad')
    root.insert(k.DCellInstArray(shell.cell_index(), k.DTrans(0., 0.)))
    root.insert(k.DCellInstArray(leg.cell_index(), k.DTrans(k.DTrans.M90, LEGX_P, LEGY)))
    root.insert(k.DCellInstArray(leg.cell_index(), k.DTrans(LEGX_N, LEGY)))
    M = {1: 34, 2: 36, 3: 42, 4: 46, 5: 81}; V = {1: 35, 2: 38, 3: 40, 4: 41}
    def box(layer, x1, y1, x2, y2): root.shapes(l.layer(layer, 0)).insert(k.DBox(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
    def wire(m, a, b, w):
        h = w / 2; box(M[m], min(a[0], b[0]) - h, min(a[1], b[1]) - h, max(a[0], b[0]) + h, max(a[1], b[1]) + h)
    def stack(x, y, lo, hi, n=1):
        h = .4 + .3 * (n - 1)          # M5 pad >= 0.64 um2 (MT.4)
        for m in range(lo, hi + 1): box(M[m], x - h, y - h, x + h, y + h)
        for m in range(lo, hi):
            for i in range(n):
                for j in range(n):
                    cx = x + (i - (n - 1) / 2) * .6; cy = y + (j - (n - 1) / 2) * .6
                    box(V[m], cx - .13, cy - .13, cx + .13, cy + .13)
    px = lambda net: LEGX_P - tx[net]      # mirrored P leg
    nx = lambda net: LEGX_N + tx[net]
    yp = LEGY + cfg['pad_trunk_lo'] + 1.5  # inside the PAD trunk span, below the MIM row
    # PAD_P: shell pin (286-290) straight up on M5 to the P leg PAD trunk (x 288)
    wire(5, (288., 912.), (288., yp), 4.); stack(288., yp, 4, 5, 3)
    # PAD_N: shell pin (302-306) up to 917, jog right to x 323 (N leg PAD trunk), up into the trunk
    wire(5, (304., 912.), (304., 917.), 4.); wire(5, (302., 917.), (nx('PAD') + 2., 917.), 4.)
    wire(5, (nx('PAD'), 917.), (nx('PAD'), yp), 4.); stack(nx('PAD'), yp, 4, 5, 3)
    # shared nets: M4 trunk extensions above the legs + one M5 strap per net
    top = LEGY + ltop
    for i, net in enumerate(SHARED):
        y = top + 4. + 2.5 * i; w = 2. if net == 'VSS' else .5
        for x in (px(net), nx(net)):
            wire(4, (x, top - 1.), (x, y), w); stack(x, y, 4, 5)
        wire(5, (px(net), y), (nx(net), y), 1.)
    ymax = top + 4. + 2.5 * len(SHARED) + 2.
    for net, x in (('RX_P', px('RX')), ('RX_N', nx('RX'))):
        wire(4, (x, top - 1.), (x, ymax), 1.); stack(x, ymax - .5, 4, 5)
    # RAILPRE: N bank trunk (M4) down to y 436.5, M3 left to the ATB tap stub (91.58, 438.2)
    xr = nx('RAILPRE'); ylo = LEGY + cfg['railpre_lo'] + 1.
    wire(4, (xr, ylo), (xr, 436.5), .5); stack(xr, 436.5, 3, 4)
    wire(3, (xr, 436.5), (91.58, 436.5), .5); wire(3, (91.58, 436.25), (91.58, 438.4), .5)
    # VSS: N bank VSS trunk (M4, 2 um) down to y 428, M3 left to x 138, up to the pad return M5 (x 136-140, y 400-444)
    xv = nx('VSS'); yv = LEGY + cfg['vss_lo'] + 1.
    wire(4, (xv, yv), (xv, 428.), 2.); stack(xv, 428., 3, 4, 2)
    wire(3, (xv, 428.), (138., 428.), 1.); stack(138., 428., 3, 5, 2)
    T = lambda name, m, x, y: root.shapes(l.layer(M[m], 10)).insert(k.DText(name, k.DTrans(x, y)))
    for i, net in enumerate(SHARED):
        if net != 'RAILPRE': T(net, 5, (px(net) + nx(net)) / 2, top + 4. + 2.5 * i)
    T('RX_P', 5, px('RX'), ymax - .5); T('RX_N', 5, nx('RX'), ymax - .5)
    T('PAD_P', 5, 288., 905.); T('PAD_N', 5, 304., 905.)
    T('ESD_RAIL', 3, 130., 444.)   # internal rail named for the model wrapper / well audit (RAILPRE stays unlabelled: observed as an internal node)
    import marker_merge
    (work / 'marker-merge.json').write_text(json.dumps(marker_merge.merge(l, root), indent=1) + '\n')
    for c in l.each_cell():
        if c.cell_index() != root.cell_index() and not c.name.startswith('svhspad__'):
            c.name = 'svhspad__' + c.name
    o = k.SaveLayoutOptions(); o.add_cell(root.cell_index()); l.write(str(work / 'pad_hspad.gds'), o)
    b = root.dbbox(); (work / 'geometry.json').write_text(json.dumps(dict(bbox_um=[b.left, b.bottom, b.right, b.top], area_um2=b.width() * b.height())) + '\n')


def assemble_stacked(work, cfg):
    import klayout.db as k
    tx = cfg['trunk_x']; ltop = cfg['leg_top']; lright = cfg['leg_right']   # leg bbox top / right edge (leg-local)
    X, Y_PLEG = 340., 440.             # P leg origin (unmirrored); the cell's side edge is X + lright = 492
    EDGE, PITCH, RXSEP = 4., 2.5, 6.   # channel: leg edge / RX pair clearance, shared-strap pitch, RX_P-RX_N pin pitch
    LOW = ['TERM_TRIM0', 'TERM_TRIM1', 'TERM_TRIM2', 'TERM_TRIM3', 'VSS']   # straps between the P leg and RX_P
    HIGH = ['VDD', 'TERM_ENABLE', 'TERM_VCM', 'VBIAS', 'RAILPRE']           # straps between RX_N and the N leg
    if sorted(LOW + HIGH) != sorted(SHARED): raise ValueError('channel plan does not cover the shared nets')
    p_top = Y_PLEG + ltop                                   # P leg trunk ends
    level = {net: p_top + EDGE + PITCH * i for i, net in enumerate(LOW)}
    y_rxp = p_top + EDGE + PITCH * (len(LOW) - 1) + EDGE
    y_rxn = y_rxp + RXSEP
    level.update({net: y_rxn + EDGE + PITCH * i for i, net in enumerate(HIGH)})
    n_top = y_rxn + EDGE + PITCH * (len(HIGH) - 1) + EDGE   # N leg trunk ends (the mirrored leg's local top edge)
    Y_NLEG = n_top + ltop                                   # N leg origin; mirrored in y: global y = Y_NLEG - local y
    if abs((p_top + n_top) - (y_rxp + y_rxn)) > 1e-6: raise ValueError('channel is not symmetric about the RX pair')
    l = k.Layout(); l.read(str(work / 'shell.gds'))
    shell = l.cell('rf_protected_pad_pair')
    l.read(str(work / 'leg.gds')); leg = l.cell('pt_hs_leg')
    for c in l.each_cell():
        for ix in l.layer_indexes():
            for s in list(c.each_shape(ix)):
                if s.is_text(): s.delete()
    root = l.create_cell('pad_hspad')
    root.insert(k.DCellInstArray(shell.cell_index(), k.DTrans(0., 0.)))
    root.insert(k.DCellInstArray(leg.cell_index(), k.DTrans(X, Y_PLEG)))                  # lower leg = P
    root.insert(k.DCellInstArray(leg.cell_index(), k.DTrans(k.DTrans.M0, X, Y_NLEG)))     # upper leg = N (mirrored in y)
    M = {1: 34, 2: 36, 3: 42, 4: 46, 5: 81}; V = {1: 35, 2: 38, 3: 40, 4: 41}
    def box(layer, x1, y1, x2, y2): root.shapes(l.layer(layer, 0)).insert(k.DBox(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
    def wire(m, a, b, w):
        h = w / 2; box(M[m], min(a[0], b[0]) - h, min(a[1], b[1]) - h, max(a[0], b[0]) + h, max(a[1], b[1]) + h)
    def stack(x, y, lo, hi, n=1):
        h = .4 + .3 * (n - 1)
        for m in range(lo, hi + 1): box(M[m], x - h, y - h, x + h, y + h)
        for m in range(lo, hi):
            for i in range(n):
                for j in range(n):
                    cx = x + (i - (n - 1) / 2) * .6; cy = y + (j - (n - 1) / 2) * .6
                    box(V[m], cx - .13, cy - .13, cx + .13, cy + .13)
    T = lambda name, m, x, y: root.shapes(l.layer(M[m], 10)).insert(k.DText(name, k.DTrans(x, y)))
    tr = lambda net: X + tx[net]
    xpad = tr('PAD'); xedge = X + lright
    # P leg: shell PAD_P M5 trunk (x 282-294, from y 410) -> M5 at y 416, BELOW the PAD_N trunk start (y 426), so the
    # pair never crosses -> up over the P leg bank to the via stack on the P leg PAD trunk
    y_padp = Y_PLEG + cfg['pad_trunk_lo'] + 1.5
    box(M[5], 282., 414., xpad + 2., 418.); box(M[5], xpad - 2., 414., xpad + 2., y_padp); stack(xpad, y_padp, 4, 5, 3)
    # N leg: shell PAD_N M5 trunk (x 298-310) sideways into the N leg PAD trunk; the stub beyond the via stack mirrors
    # the PAD_P run over the bank (same length, same leg metal underneath) and ends open: P/N pad C balance only
    y_padn = Y_NLEG - (cfg['pad_trunk_lo'] + 1.5)
    box(M[5], 298., y_padn - 2., xpad + 2., y_padn + 2.); stack(xpad, y_padn, 4, 5, 3)
    box(M[5], xpad - 2., y_padn, xpad + 2., y_padn + (y_padp - 414.))
    # shared nets: the two legs' M4 trunks joined straight across the channel; port nets get an M5 strap to the side edge
    # (crossing at the leg trunk's own width for the current-carrying nets: TERM_VCM carries the differential
    # termination current between the legs, ~44 squares of M4 here)
    for net in SHARED:
        w = {'VSS': 2., 'TERM_VCM': 1.}.get(net, .5)
        wire(4, (tr(net), p_top - 1.), (tr(net), n_top + 1.), w)
        if net != 'RAILPRE':     # internal node: no strap, no label
            stack(tr(net), level[net], 4, 5)
            box(M[5], tr(net), level[net] - .5, xedge, level[net] + .5); T(net, 5, xedge - .5, level[net])
    # RX_P / RX_N: mirror-identical routes (P/N balance at the CTLE input): RX trunk -> 18 um M4 extension into the
    # channel -> 0.6 um M5 strap to the cell's side edge = adjacent side pins, RXSEP apart
    for y_leg, y, net in ((p_top - 1., y_rxp, 'RX_P'), (n_top + 1., y_rxn, 'RX_N')):
        wire(4, (tr('RX'), y_leg), (tr('RX'), y), 1.); stack(tr('RX'), y, 4, 5)
        box(M[5], tr('RX'), y - .3, xedge, y + .3); T(net, 5, xedge - .5, y)
    # RAILPRE / VSS: from the P-leg bank down to the shell exactly as the side-by-side build
    xr = tr('RAILPRE'); ylo = Y_PLEG + cfg['railpre_lo'] + 1.
    wire(4, (xr, ylo), (xr, 436.5), .5); stack(xr, 436.5, 3, 4)
    wire(3, (xr, 436.5), (91.58, 436.5), .5); wire(3, (91.58, 436.25), (91.58, 438.4), .5)
    xv = tr('VSS'); yv = Y_PLEG + cfg['vss_lo'] + 1.
    wire(4, (xv, yv), (xv, 428.), 2.); stack(xv, 428., 3, 4, 2)
    wire(3, (xv, 428.), (138., 428.), 1.); stack(138., 428., 3, 5, 2)
    T('PAD_P', 5, 288., 905.); T('PAD_N', 5, 304., 905.)
    T('ESD_RAIL', 3, 130., 444.)
    import marker_merge
    (work / 'marker-merge.json').write_text(json.dumps(marker_merge.merge(l, root), indent=1) + '\n')
    for c in l.each_cell():
        if c.cell_index() != root.cell_index() and not c.name.startswith('svhspad__'):
            c.name = 'svhspad__' + c.name
    o = k.SaveLayoutOptions(); o.add_cell(root.cell_index()); l.write(str(work / 'pad_hspad.gds'), o)
    b = root.dbbox(); (work / 'geometry.json').write_text(json.dumps(dict(bbox_um=[b.left, b.bottom, b.right, b.top], area_um2=b.width() * b.height())) + '\n')


def generate(work, shell, leg, network, stacked=False):
    sys.path.insert(0, str(HERE))
    from layout import magic, IMAGE
    from run_first_pass import lvs
    work.mkdir(parents=True, exist_ok=False)
    shutil.copy(shell / 'pad.gds', work / 'shell.gds'); shutil.copy(leg / 'pt_hs_leg.gds', work / 'leg.gds')
    for f in ('marker_merge.py',):
        shutil.copy(HERE / f, work / f)
    shutil.copy(Path(__file__), work / 'hs_pad_compose.py')
    # leg trunk geometry from its labels (convkit bank, x < 0)
    q = ('import klayout.db as k,json\nl=k.Layout();l.read("/work/leg.gds");t=l.top_cell();out={}\n'
         'for li in l.layer_indexes():\n for s in t.each_shape(li):\n  if s.is_text():out.setdefault(s.text_string,[]).append([s.dtext.x,s.dtext.y,l.get_info(li).datatype])\n'
         'b=t.dbbox();print(json.dumps(dict(labels=out,bbox=[b.left,b.bottom,b.right,b.top])))\n')
    (work / 'q.py').write_text(q)
    r = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python3', '--mount', f'type=bind,src={work},dst=/work', IMAGE, '/work/q.py'], capture_output=True, text=True, check=True)
    info = json.loads(r.stdout.strip().splitlines()[-1])
    lab = info['labels']
    tx = {n: v[0][0] for n, v in lab.items() if not n.startswith('TU')}
    lo = lambda n: min(p[1] for p in lab[n] if p[2] == 0)
    cfg = dict(trunk_x=tx, leg_top=info['bbox'][3], leg_right=info['bbox'][2], pad_trunk_lo=lo('PAD'), railpre_lo=lo('RAILPRE'), vss_lo=lo('VSS'), stacked=stacked)
    (work / 'config.json').write_text(json.dumps(cfg, indent=1))
    subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python3', '--mount', f'type=bind,src={work},dst=/work', IMAGE,
                    '/work/hs_pad_compose.py', '--inside', '/work'], check=True)
    (work / 'extract.tcl').write_text('crashbackups stop\ngds read pad_hspad.gds\nload pad_hspad\nselect top cell\nflatten pad_hspad_flat\nload pad_hspad_flat\nsave\nselect top cell\nexpand\n'
        'drc check\ndrc catchup\nputs "HS_DRC [drc list count total]"\nputs [drc listall why]\nextract all\next2spice lvs\next2spice cthresh 0\next2spice\nquit -noprompt\n')
    res = magic(work, 'extract.tcl')
    m = re.search(r'HS_DRC (\d+)', res.stdout)
    drc = int(m[1]) if m else None
    raw = (work / 'pad_hspad_flat.spice').read_text()
    ports = next(line.split()[2:] for line in re.sub(r'\n\+\s*', ' ', raw).splitlines() if line.startswith('.subckt'))
    shell_ref = (shell / 'reference.spice').read_text()
    leg_ref = (leg / 'pt_hs_leg.lvs_sch.spice').read_text()
    top = ('.subckt hs_reference ' + ' '.join(ports) + '\n'
           'XSH PAD_N PAD_P VSS ESD_RAIL RAILPRE pad_reference\n'
           'XLP PAD_P RX_P VBIAS TERM_VCM TERM_ENABLE TERM_TRIM0 TERM_TRIM1 TERM_TRIM2 TERM_TRIM3 VDD VSS RAILPRE pt_hs_leg\n'
           'XLN PAD_N RX_N VBIAS TERM_VCM TERM_ENABLE TERM_TRIM0 TERM_TRIM1 TERM_TRIM2 TERM_TRIM3 VDD VSS RAILPRE pt_hs_leg\n.ends hs_reference\n')
    strip = lambda t: '\n'.join(x for x in t.splitlines() if not x.startswith('C')) + '\n'
    (work / 'reference.spice').write_text(strip(shell_ref + leg_ref + top)); (work / 'actual.spice').write_text(strip(raw))
    ok = lvs(work, 'actual.spice', 'pad_hspad_flat', 'reference.spice', 'hs_reference', 'pad-lvs.txt')
    # simulation model: same array-well correction as the shell (network-with-well DWELL_ARRAY)
    manifest = json.loads((network / 'network-layout.json').read_text())
    corr = manifest['array_well_capacitance_removed_ff']; lines = raw.splitlines(); n = 0
    for i, line in enumerate(lines):
        t = line.split()
        if t and t[0].startswith('C') and set(t[1:3]) == {'VSS', 'ESD_RAIL'}:
            v = float(t[3][:-1]) * {'f': 1., 'p': 1000.}[t[3][-1]]
            if v <= corr: raise ValueError('well correction exceeds extracted C')
            lines[i] = ' '.join(t[:3]) + f' {v - corr:.9g}f'; n += 1
    well = next(x for x in (network / 'network-with-well.spice').read_text().splitlines() if x.startswith('DWELL_ARRAY')).replace(' RAIL ', ' ESD_RAIL ')
    physical = '\n'.join(lines).replace('.ends', well + '\n.ends') + '\n'
    public = [p for p in ports if p not in ('ESD_RAIL', 'RAILPRE')]
    wrapper = '.subckt hs_protected_pad ' + ' '.join(public) + '\nXPHYSICAL ' + ' '.join(ports) + ' pad_hspad_flat\n.ends hs_protected_pad\n'
    (work / 'physical.spice').write_text(wrapper + physical)
    from protection_device_audit import check
    aud = check(work / 'pad_hspad_flat.ext', work / 'physical.spice', work / 'independent-device-audit.json', work / 'pad_hspad_flat.spice')
    rep = dict(status='hs_pad_composed', drc_count=drc, lvs_match=bool(ok), well_corrections=n, independent_device_graph_match=aud['device_graph_matches'],
               ports=public, geometry=json.loads((work / 'geometry.json').read_text()), config=cfg,
               source_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), shell / 'pad.gds', leg / 'pt_hs_leg.gds', network / 'network-layout.json')})
    (work / 'layout-screen.json').write_text(json.dumps(rep, indent=1) + '\n')
    print(json.dumps({k: rep[k] for k in ('drc_count', 'lvs_match', 'well_corrections', 'independent_device_graph_match', 'geometry')}))


if __name__ == '__main__':
    if sys.argv[1] == '--inside':
        assemble(Path(sys.argv[2]))
    else:
        generate(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve(), Path(sys.argv[4]).resolve(),
                 stacked='--stacked' in sys.argv[5:])
