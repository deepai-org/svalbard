"""Deterministic full-chip floorplan on true GDS bounds.

Obstacles are the real extents of every fixed object: the core boundary of
the provider 1x1 template, every custom pad-family cell at its site transform,
and the digital macro outline. Movable masters are placed in island order at
the legal position closest to their seed; every block keeps a halo. MIM decap
arrays are placed per island after its blocks. Every rectangle is re-checked
pairwise afterwards (`legality`), independently of the occupancy grid.
"""
import json
import math

import numpy as np
import inventory as inv

from inventory import (CORE, CUSTOM_PADS, MIRRORED_PADS, MIM_PITCH_UM, MIM_UNIT_UM, ISLANDS, instances, atb_cells,
                       mim_unit_f, decap_banks)

DECAP_BUS_UM = 12.0   # M4/M5 collector ring around each MIM bank

SITE_PITCH_EDGE = 211.0
# Signal port label of each pad family (the bond-side node the core block must reach).
PORT_LABEL = {'rf_pair': 'PAD_P', 'single_leg': 'PAD_P', 'single_leg_b': 'PAD_P', 'refpad': 'PAD_P', 'wirepad': 'RX_P',
              'txpad': 'MAIN_P'}
GRID = 2.0          # um
HALO = 10.0         # um between blocks
PAD_HALO = 15.0     # um to pad-family cells and the digital macro


def site_origin(edge, site, ring_sites):
    """Site origin along its edge from the provider placement transforms."""
    return ring_sites[site]


def pad_rect(edge, along0, depth, width):
    """Chip rect of a custom pad cell: local x along the edge, local y into the core."""
    if edge == 'west':
        return (26.0, along0, 26.0+depth, along0+width)
    if edge == 'east':
        return (3906.0-depth, along0, 3906.0, along0+width)
    raise ValueError(edge)


def cell_to_chip(name, edge, along0, c):
    """Pad-cell local rect (x along the edge, y into the core) -> chip rect, same transforms as kl_assemble."""
    x1, y1, x2, y2 = c
    if edge == 'west':
        return (26.0+y1, along0+x1, 26.0+y2, along0+x2)
    if name in MIRRORED_PADS:
        hi = along0+75.0+SITE_PITCH_EDGE
        return (3906.0-y2, hi-x2, 3906.0-y1, hi-x1)
    return (3906.0-y2, along0+x1, 3906.0-y1, along0+x2)


MOS_TILE_UM = 40.0
MOS_TILE_F = 3.72e-12        # P5 extracted tt (ss 3.58 pF)


class Occupancy:
    def __init__(self):
        self.x0, self.y0 = CORE[0], CORE[1]
        self.nx = int(math.ceil((CORE[2]-CORE[0])/GRID))
        self.ny = int(math.ceil((CORE[3]-CORE[1])/GRID))
        self.occ = np.zeros((self.ny, self.nx), dtype=np.int32)

    def block(self, r, halo=0.0):
        x1 = int(math.floor((r[0]-halo-self.x0)/GRID)); x2 = int(math.ceil((r[2]+halo-self.x0)/GRID))
        y1 = int(math.floor((r[1]-halo-self.y0)/GRID)); y2 = int(math.ceil((r[3]+halo-self.y0)/GRID))
        x1, y1 = max(x1, 0), max(y1, 0)
        x2, y2 = min(x2, self.nx), min(y2, self.ny)
        if x2 > x1 and y2 > y1:
            self.occ[y1:y2, x1:x2] = 1

    def place(self, w, h, seed):
        """Lower-left corner of the free w x h rect (incl. halo) closest to seed."""
        gw = int(math.ceil((w+2*HALO)/GRID)); gh = int(math.ceil((h+2*HALO)/GRID))
        if gw > self.nx or gh > self.ny:
            return None
        sat = np.zeros((self.ny+1, self.nx+1), dtype=np.int64)
        sat[1:, 1:] = self.occ.cumsum(0).cumsum(1)
        tot = sat[gh:, gw:]-sat[:-gh, gw:]-sat[gh:, :-gw]+sat[:-gh, :-gw]
        free = tot == 0
        if not free.any():
            return None
        ys, xs = np.nonzero(free)
        cx = self.x0+xs*GRID+HALO+w/2; cy = self.y0+ys*GRID+HALO+h/2
        d = (cx-seed[0])**2+(cy-seed[1])**2
        k = int(np.argmin(d))
        return (self.x0+xs[k]*GRID+HALO, self.y0+ys[k]*GRID+HALO)


def build(abstracts, ring_sites, controls, have_wrx_cap, digital_size, digital_origin):
    occ = Occupancy()
    fixed = []
    # Custom pad cells at their sites (true family bounds).
    fam_size = {}
    for name, fam, edge, origin, sites, ports, replaces in CUSTOM_PADS:
        a = abstracts['pad_'+fam]
        x1, y1, x2, y2 = a['bbox']
        along0 = ring_sites[origin]
        if name in MIRRORED_PADS:
            # Mirrored along the edge: the cell's second pad lands on the origin site and the
            # cell extends towards lower site coordinates (see inventory.MIRRORED_PADS).
            hi = along0+75.0+SITE_PITCH_EDGE   # far edge of the second site
            r = pad_rect(edge, hi-(x2-0.0), y2, x2-x1)
        else:
            r = pad_rect(edge, along0+x1, y2, x2-x1)
        # Core-side signal port of the family (label in cell coordinates -> chip), same transforms as kl_assemble:
        # west M45 at (26, ys); east R90 at (3906, ys); mirrored east M135 at (3906, ys+286).
        # v4 compact families carry a second PAD_P label on the inner-edge pin: prefer the deepest label (core side).
        labs = [l for l in a['labels'] if l['text'] == PORT_LABEL[fam]]
        lab = max(labs, key=lambda l: l['y']) if labs else None
        port = None
        if lab is not None:
            lx, ly_ = lab['x'], lab['y']
            port = ((26.0+ly_, along0+lx) if edge == 'west' else
                    (3906.0-ly_, along0+75.0+SITE_PITCH_EDGE-lx) if name in MIRRORED_PADS else (3906.0-ly_, along0+lx))
        # v4: L-shaped compact wired families block only their occupied rectangles (pads owner P5); the notch is free.
        occupied = [r]
        notch = None
        if fam in getattr(inv, 'PAD_NOTCH_UM', {}):
            nx1, ny1, nx2, ny2 = inv.PAD_NOTCH_UM[fam]
            cell_occ = [(x1, y1, x2, ny1), (x1, ny1, nx1, y2)]
            occupied = [cell_to_chip(name, edge, along0, c) for c in cell_occ]
            notch = cell_to_chip(name, edge, along0, (nx1, ny1, nx2, ny2))
        fixed.append(dict(name=name, kind='pad_family', master='pad_'+fam, edge=edge, site=origin, rect=r,
                          port=PORT_LABEL[fam], port_xy=port, occupied=occupied, notch=notch))
        for o_ in occupied:
            occ.block(o_, PAD_HALO)
    dx, dy = digital_origin
    dr = (dx, dy, dx+digital_size[0], dy+digital_size[1])
    fixed.append(dict(name='digital', kind='digital_abstract', master='pt_digital_macro', rect=dr))
    occ.block(dr, PAD_HALO)
    from inventory import RESERVES
    for name, r, why in RESERVES:
        fixed.append(dict(name=name, kind='reserve', rect=r, note=why))
        occ.block(r, HALO)
    placed = []
    failures = []
    # Fixed placements (floorplan v2 RF chain and I/Q pairs) first, at their exact rects.
    # instance -> (master, island) for every movable row, incl. the attached TX pad cells
    known = {r[0]: (r[1], r[2]) for r in instances(have_wrx_cap)}
    known.update({f'attached_tx_steering_{k}': ('attached_tx_steering_driver', 'wired') for k in range(6)})
    known.update({'attached_tx_interlock': ('attached_tx_interlock', 'wired'), 'attached_tx_buffer': ('attached_tx_buffer', 'wired')})
    for inst, (x, y, orient) in inv.FIXED_PLACEMENT.items():
        master, isl = known[inst]
        bx1, by1, bx2, by2 = abstracts[master]['bbox']
        w, h = (by2-by1, bx2-bx1) if orient in ('R90', 'R270', 'M45', 'M135') else (bx2-bx1, by2-by1)
        rect = (x, y, x+w, y+h)
        occ.block((rect[0], rect[1]-35, rect[2], rect[3]+35) if master.startswith('isw_') else rect)
        placed.append(dict(name=inst, master=master, island=isl, rect=rect, orient=orient, fixed=True,
                           origin=(x-bx1, y-by1), mirror_x=False, mirror_dx=None))
    rows = [r for r in instances(have_wrx_cap) if r[0] not in inv.FIXED_PLACEMENT]+atb_cells(controls)
    rows += [(f'attached_tx_steering_{k}', 'attached_tx_steering_driver', 'wired', (2850, 2350)) for k in range(6)]
    rows += [('attached_tx_interlock', 'attached_tx_interlock', 'wired', (3300, 2200)),
             ('attached_tx_buffer', 'attached_tx_buffer', 'wired', (2600, 1900))]
    rows = [r for r in rows if r[0] not in inv.FIXED_PLACEMENT]
    def area(row):
        b = abstracts[row[1]]['bbox']
        return (b[2]-b[0])*(b[3]-b[1])
    rows.sort(key=lambda r: -area(r))      # stable: large blocks first, seeds keep islands together
    big = [r for r in rows if area(r) >= 30000.0]
    small = [r for r in rows if area(r) < 30000.0]

    def place_rows(rs):
        for inst, master, island, seed in rs:
            a = abstracts[master]
            bx1, by1, bx2, by2 = a['bbox']
            w, h = bx2-bx1, by2-by1
            saved = None
            if master in inv.AGGRESSOR_MASTERS:      # temporary keep-out around victims for aggressors
                saved = occ.occ.copy()
                for p in placed:
                    if p['name'] in inv.VICTIM_INSTANCES:
                        occ.block(p['rect'], inv.AGGRESSOR_KEEPOUT_UM)
            pos = occ.place(w, h+(70 if master.startswith('isw_') else 0), seed)
            if saved is not None:
                occ.occ = saved
            if pos is not None and master.startswith('isw_'):
                pos = (pos[0], pos[1]+35)
            if pos is None:
                failures.append(inst)
                continue
            rect = (pos[0], pos[1], pos[0]+w, pos[1]+h)
            # island switches carry Metal5 strap bars 10-30 um above and below the cell
            occ.block((rect[0], rect[1]-35, rect[2], rect[3]+35) if master.startswith('isw_') else rect)
            # mirror_x: the cell is mirrored about its own vertical centre line (same rect);
            # GDS transform M90 with x displacement origin_x + bx1 + bx2.
            placed.append(dict(name=inst, master=master, island=island, rect=rect,
                               origin=(pos[0]-bx1, pos[1]-by1), orient='R0', mirror_x=inst in inv.MIRROR_X,
                               mirror_dx=pos[0]+bx2 if inst in inv.MIRROR_X else None))
    place_rows(big)
    place_rows(small)      # v3: every block before decap (the pool is a recorded check, not a placement gate)
    # Shared MIM pool banks and local island decap, next to the switch row.
    unit_f = mim_unit_f()
    decaps = []
    decap_failures = []
    for name, island, n, seed in decap_banks():
        cx, cy = seed
        best = None
        for cols in range(1, n+1):
            rows_ = math.ceil(n/cols)
            w = cols*MIM_PITCH_UM-(MIM_PITCH_UM-MIM_UNIT_UM)+2*DECAP_BUS_UM
            h = rows_*MIM_PITCH_UM-(MIM_PITCH_UM-MIM_UNIT_UM)+2*DECAP_BUS_UM
            pos = occ.place(w, h, (cx, cy))
            if pos is None:
                continue
            d = ((pos[0]+w/2-cx)**2+(pos[1]+h/2-cy)**2)**.5 + 0.2*abs(w-h)
            if best is None or d < best[0]:
                best = (d, cols, rows_, pos, w, h)
        if best is None:
            decap_failures.append(name)     # recorded as a failed decap check, not a placement failure
            continue
        _, cols, rows_, pos, w, h = best
        rect = (pos[0], pos[1], pos[0]+w, pos[1]+h)
        occ.block(rect)
        decaps.append(dict(name=name, island=island, units=n, cols=cols, rows=rows_,
                           rect=rect, capacitance_f=n*unit_f, pool=island == 'core'))
    # v4 explicit MIM banks (e.g. in the macro<->ADC isolation band, which is a reserve: MIM has no substrate contact).
    for name, bx, by, cols, rows_, rsv in getattr(inv, 'MIM_FIXED_BANKS', []):
        w = cols*MIM_PITCH_UM-(MIM_PITCH_UM-MIM_UNIT_UM)+2*DECAP_BUS_UM
        h = rows_*MIM_PITCH_UM-(MIM_PITCH_UM-MIM_UNIT_UM)+2*DECAP_BUS_UM
        rect = (bx, by, bx+w, by+h)
        decaps.append(dict(name=name, island='core', units=cols*rows_, cols=cols, rows=rows_, rect=rect,
                           capacitance_f=cols*rows_*unit_f, pool=True, in_reserve=rsv))
    # v4 MOS decap tile arrays (P5, Metal1-2 only): tiles fill the free part of each region, one array per run of free
    # tiles in a row (rows mirror about x in kl_assemble). Pad notches additionally get a stacked MIM bank where a full
    # notch-wide run exists (Metal4/5 are free over the tiles). Corridor tiles sit under the routing reserve.
    def free_tile(x, y, ignore_reserve):
        if ignore_reserve:
            return True
        g = lambda v, o: int(math.floor((v-o)/GRID))
        x1, y1 = g(x-HALO, occ.x0), g(y-HALO, occ.y0)
        x2, y2 = int(math.ceil((x+MOS_TILE_UM+HALO-occ.x0)/GRID)), int(math.ceil((y+MOS_TILE_UM+HALO-occ.y0)/GRID))
        if x1 < 0 or y1 < 0 or x2 > occ.nx or y2 > occ.ny:
            return False
        return not occ.occ[y1:y2, x1:x2].any()
    for name, region, fam in getattr(inv, 'DECAP_MOS_REGIONS', []):
        if fam is not None:
            f = next((f for f in fixed if f['kind'] == 'pad_family' and f['master'] == 'pad_'+fam and f.get('notch')), None)
            if f is None:
                decap_failures.append(name)
                continue
            n = f['notch']
            region = (n[0]+HALO, n[1]+HALO, n[2]-HALO, n[3]-HALO)    # 10 um from the family's own geometry
        under = fam is None and any(r[0] == 'rsv_corridor_s' and r[1][0] <= region[0] and r[1][2] >= region[2]
                                     for r in inv.RESERVES)
        x1, y1, x2, y2 = region
        cols = int((x2-x1)//MOS_TILE_UM); rows_ = int((y2-y1)//MOS_TILE_UM)
        k = 0
        for r in range(rows_):
            y = y1+r*MOS_TILE_UM
            c = 0
            while c < cols:
                if not free_tile(x1+c*MOS_TILE_UM, y, under):
                    c += 1
                    continue
                c0 = c
                while c < cols and free_tile(x1+c*MOS_TILE_UM, y, under):
                    c += 1
                rect = (x1+c0*MOS_TILE_UM, y, x1+c*MOS_TILE_UM, y+MOS_TILE_UM)
                decaps.append(dict(name=f'{name}_{k}', island='core', kind='mos', units=c-c0, cols=c-c0, rows=1,
                                   rect=rect, capacitance_f=(c-c0)*MOS_TILE_F, pool=True, under_reserve=under,
                                   mirror=r % 2 == 1, region=name))
                k += 1
                if not under:
                    occ.block(rect)
        if k == 0:
            decap_failures.append(name)
    return dict(fixed=fixed, placed=placed, decaps=decaps, failures=failures, decap_failures=decap_failures,
                grid_um=GRID, halo_um=HALO)


def legality(fp):
    """Independent pairwise rect check: inside core (movables), no overlaps, halo kept."""
    errs = []
    items = []
    for f in fp['fixed']:
        occ_ = f.get('occupied') or [f['rect']]
        items += [(f['name'] if len(occ_) == 1 else f"{f['name']}#{k}", o, f['kind']) for k, o in enumerate(occ_)]
    items += [(p['name'], p['rect'], 'block') for p in fp['placed']]
    items += [(d['name'], d['rect'], 'decap') for d in fp['decaps']]
    allowed = set()
    for d in fp['decaps']:
        if d.get('stacked_on'):
            allowed.add(frozenset((d['name'], d['stacked_on'])))     # MIM (Metal4/5) over MOS tiles (Metal1/2)
        if d.get('in_reserve'):
            allowed.add(frozenset((d['name'], d['in_reserve'])))
        if d.get('under_reserve'):
            allowed.add(frozenset((d['name'], 'rsv_corridor_s')))      # tiles under the corridor routing
    mos = [d['name'] for d in fp['decaps'] if d.get('kind') == 'mos']
    allowed |= {frozenset((a, b)) for a in mos for b in mos}             # tile rows abut (mirrored rails)
    for name, r, kind in items:
        if kind != 'pad_family' and not (r[0] >= CORE[0]-1e-6 and r[1] >= CORE[1]-1e-6 and
                                         r[2] <= CORE[2]+1e-6 and r[3] <= CORE[3]+1e-6):
            errs.append(f'{name} outside core {r}')
    for i in range(len(items)):
        for j in range(i+1, len(items)):
            a, b = items[i][1], items[j][1]
            if frozenset((items[i][0], items[j][0])) in allowed:
                continue
            need = 0.0 if items[i][2] == items[j][2] == 'pad_family' else HALO-GRID
            gap_x = max(b[0]-a[2], a[0]-b[2]); gap_y = max(b[1]-a[3], a[1]-b[3])
            if max(gap_x, gap_y) < need-1e-6:
                errs.append(f'{items[i][0]} / {items[j][0]} spacing {max(gap_x, gap_y):.2f} < {need}')
    return errs


def island_regions(fp):
    reg = {}
    for isl in ISLANDS:
        rs = [p['rect'] for p in fp['placed'] if p['island'] == isl]+[d['rect'] for d in fp['decaps'] if d['island'] == isl]
        reg[isl] = [min(r[0] for r in rs), min(r[1] for r in rs), max(r[2] for r in rs), max(r[3] for r in rs)]
    return reg


def mitigation_report(fp):
    """Per reserved instance: clearance to the nearest other object vs the reserved halo (sum of both halos)."""
    items = [(f['name'], f['rect']) for f in fp['fixed']]+[(p['name'], p['rect']) for p in fp['placed']] + \
            [(d['name'], d['rect']) for d in fp['decaps']]
    out = {}
    for n, h in inv.MITIGATION_HALO_UM.items():
        r = dict(items).get(n)
        if r is None:
            continue
        worst = min(((max(q[0]-r[2], r[0]-q[2], q[1]-r[3], r[1]-q[3]), m) for m, q in items
                     if m != n and not m.startswith('rsv_corridor')), key=lambda t: t[0])
        need = h+inv.MITIGATION_HALO_UM.get(worst[1], 0.0)
        out[n] = dict(halo_um=h, clearance_um=round(worst[0], 1), nearest=worst[1], short_um=round(max(0, need-worst[0]), 1),
                      demanded=inv.MITIGATION_DEMANDED.get(n))
    return out
