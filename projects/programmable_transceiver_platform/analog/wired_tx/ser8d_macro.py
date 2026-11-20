"""wtx_ser8d: eighth-rate stream source for the muxing pre-driver wtx_mux8 (NOT published).

8 five-bit parallel-load stream registers (the 40-bit word, stream k = D(k + 8 j), clocked from phase 0), the /5 word
divider and per-stream retiming hops (cells of serq8_macro.py).  Outputs F0..F7: F k = NOT(bit of stream k).

Hop plan (HOPS: stream -> hop clock phases), from measurements on the extracted macro and mux
(scratch/wired_tx/s13: probe.py runs p1 / p_ff, bath/bath.log).  Times after the PH0 edge at the pin:
                                          ss pessimistic 3.15 V      ff 3.35 V
  register outputs B change at            2.45-2.51 ns               1.26-1.32 ns
  hop clock Q c rises at  c slots +       1.19-1.30 ns               0.63-0.68 ns
  hop output changes after its clock      0.65 ns                    0.33 ns
  mux: a stream may NOT change from       -0.1 to +0.35 ns           0.0 to +0.25 ns   after its slice's phase edge
  * first capture of a register output at phase 6, 7 or 0 of the next cycle (abs 8).  Phase 6: set-up 6 slots - 1.24 ns
    (0.61 ns at 3.24 Gb/s).  Abs 8: hold = B delay - clock delay = 1.2 ns (ss) / 0.65 ns (ff), independent of the rate.
    The earlier plan captured streams 0, 5, 6, 7 at phase 4: 55-110 ps of set-up at ss pessimistic, 3.125 Gb/s failed.
  * a second hop 4 or 6 slots after the first (set-up 4 slots - 0.76 ns).
  * the final hop of the stream on slice s is clocked by phase s itself (stream 3: phase s - 1): the stream changes
    1.5-1.9 ns (ss) / 0.65-1.0 ns (ff) after the slice's own phase edge, i.e. after its window has closed, and is
    then stable for the rest of the ring period.
  stream:  0     1     2      3      4       5       6       7
  hops:    6     7     0      0      6, 2    7, 3    6, 4    7, 5
  slice:   6     7     0      1      2       3       4       5        -> wtx_mux8 slice k takes stream (k + 2) mod 8
                                                                         (wtx8_top.FROT)

    python3 ser8d_macro.py        # -> generated/fast/wtx_ser8d.*
"""
import json

import serq4_macro as M
import serq8_macro as Q
import tools

NAME = 'wtx_ser8d'
PORTS = [f'D{i}' for i in range(40)] + Q.PH + ['SERQ'] + [f'F{k}' for k in range(8)] + ['WCKQ', 'VDD', 'VSS']
HOPS = {0: (6,), 1: (7,), 2: (0,), 3: (0,), 4: (6, 2), 5: (7, 3), 6: (6, 4), 7: (7, 5)}
CELLS = [c for c in Q.CELLS if not c.startswith(('wtx_omux8', 'wtx_ofin8', 'wtx_ppost8'))]


# ---- Metal5 / supply plan (ASM-8, session 15).  Metal5 is the top grid's.  The chip grid's Metal5 straps (VDD / VSS
# alternating every 35 um, pair pitch 70 um, 10.5-16 um wide, cut 2.5 um from block Metal5) cross wtx_ser8d in Metal5-free
# CHANNELS of CH_W um at x = CH_X0 + 35 k for k in CH_K (block = ser8d coordinates; the assembly places pt_wiredtx8 so that
# grid strap axes land on these axes).  Not every axis is opened: channel pairs are spaced so that no piece of the block's
# Metal5 exception is wider than 250 um (power-delivery G3), see REPORT.  ser8d's own Metal5 (supply straps, signal trunks)
# lives between them.  Three VSS_BAR_W VSS bars (block VSS trunks: seam plate -> bottom edge tie points) at VSS_BARS:
# 340 / 410 / 480 lie half-way between the mux PH pin pads above (285.25 + 34.5 k), which the bars pass in the seam.
CH_PITCH, CH_X0, CH_W = 35.0, 7.5, 21.0          # channel = 16 um strap (strap_widths.json ME/SE) + 2 x 2.5 um grid cut
CH_K = (6, 7, 11, 12, 16, 17)
VSS_BARS, VSS_BAR_W = (340.0, 410.0, 480.0), 10.0
STRAP_PITCH, STRAP_X0 = 35.0, 23.5               # ser8d strap pairs (VDD x, VSS x + 3) centred between grid axes (25 + 35 k);
                                                 # the three pairs under the VSS bars are dropped by the keep-out: 18 pairs


def channels(width=744.12):
    """Channel x ranges (Metal5 free over the full ser8d height), block coordinates."""
    return [(round(max(0.0, CH_X0 + CH_PITCH * k - CH_W / 2), 3), round(min(width, CH_X0 + CH_PITCH * k + CH_W / 2), 3)) for k in CH_K]


def bars():
    return [(round(x - VSS_BAR_W / 2, 3), round(x + VSS_BAR_W / 2, 3)) for x in VSS_BARS]


def supply_em():
    """em options of the supply plan (see channels / bars)."""
    keep = channels() + [(a - 0.6, b + 0.6) for a, b in bars()]
    return dict(m5_keep=keep, strap_x0=STRAP_X0, strap_pitch=STRAP_PITCH, strap_cuts=True,
                m5_bars=[('VSS', a, b) for a, b in bars()])


def _slot_w(cell):
    """Row slot width of a macro in le.generate (bbox + escape columns: pins right, rails left)."""
    m = json.loads((M.FAST / f'{cell}.pins.json').read_text())
    w = m['bbox'][2] - m['bbox'][0]
    return w + sum(M.le.COL_INNER + M.le.PITCH_COL * (n - 1) + M.le.SLOT_GAP / 2 for n in (len(m['pins']), len(m['rails'])))


def rows():
    """Floorplan derived from HOPS (session 13, 4 rows, bottom to top; the top edge is the mux edge):
      R0  L0..L3, R1  L4..L7      stream registers (register k and k + 4 in the same column);
      R2  CK CTL | hops           the hops of streams k and k + 4 under the BO (right) end of their register column
                                  (short B k), the /5 divider between the first two groups;
      R3  P0..P7                  phase slices, all in the top row: equal PH trunks, F trunks cross one row.
    Gaps spread the hop groups over the width of the P row (never beyond it)."""
    hop = {k: [f'H{k}_{i}' for i in range(len(HOPS[k]))] for k in range(8)}
    grp = [hop[c] + hop[c + 4] for c in range(4)]
    cell = dict(top_instances_cells())
    used = sum(_slot_w(cell['X' + n]) for n in ['CK', 'CTL', 'DV'] + [h for g in grp for h in g])
    slack = max(0.0, 8 * _slot_w('wtx_qph') - used - 3.0)
    gap = lambda f: [f'GAP:{slack * f:.2f}'] if slack * f >= 0.01 else []
    return [[f'L{k}' for k in range(4)], [f'L{k}' for k in range(4, 8)],
            ['CK', 'CTL'] + gap(0.30) + grp[0] + ['DV'] + grp[1] + gap(0.36) + grp[2] + gap(0.34) + grp[3],
            [f'P{k}' for k in range(8)]]


def top_instances_cells():
    return [(i, cell) for i, cell, _ in top_instances()]


def top_instances():
    out = [(i, cell, c) for i, cell, c in Q.top_instances() if i[:2] != 'XH' and i not in ('XOA', 'XOB', 'XOF', 'XPP')]
    for k, seq in HOPS.items():
        prev = f'B{k}_0'
        for i, q in enumerate(seq):
            last = i == len(seq) - 1
            o = f'F{k}' if last else f'R{k}_{i}'
            out.append((f'XH{k}_{i}', 'wtx_tspcbx' if last else 'wtx_tspcb', [f'Q{q}', prev, o, 'QRST', 'VDD', 'VSS']))
            prev = o
    return out


def top_spice():
    body = [f'.subckt {NAME} {" ".join(PORTS)}']
    body += [f'{i} {" ".join(c)} {cell}' for i, cell, c in top_instances()]
    return '\n'.join(body + [f'.ends {NAME}']) + '\n'


def build_top():
    text = ''.join((M.FAST / f'{n}.spice').read_text() for n in CELLS)
    # over_cell: the cells use Metal1/2 only, so each row's Metal4 tracks run over the row (s13: height 317 -> 197 um);
    # track_first: the eight PH tracks are the first (adjacent) tracks of the P row, so the PH trunks are equal.
    # net_space (0.02 um: no real track cost): the Metal5 trunks of the phase inputs, the hop clocks and the outputs keep
    # both neighbouring trunk columns free (first s13 build: F2 trunk beside the Q7 trunk 10 fF, F1 / F3 beside D trunks
    # 9-11 fF, PH135 beside SERQ 10 fF; second build: B1_0 beside LDA 17 fF).
    hopd = [c[1] for i, _, c in top_instances() if i[:2] == 'XH']     # hop data inputs: B k_0, R k_i
    quiet = {n: 0.02 for n in list(Q.PH) + [f'F{k}' for k in range(8)] + [f'Q{k}' for k in range(8)] + hopd}
    # Metal5 / supply plan (ASM-8): channels, lanes, VSS bars, strap Via4 arrays (layout_engine em options m5_keep, strap_x0, m5_bars)
    res = M.build_le(NAME, PORTS, top_spice(), text, rows(), CELLS, max_row_width=760.0, workname='ser8d',
                     over_cell=True, em=dict(track_first=list(Q.PH), **supply_em()), net_space=quiet)
    write_m5_plan()
    return res


def write_m5_plan():
    """For the block top (pt_wiredtx8_layout.py): the Metal5 plan in wtx_ser8d.pins.json (channels, VSS bars) and the
    lower ends of the port trunks that the top continues to the bottom edge (s13/top/serm5/dcols.json), both from the
    engine report of this build."""
    rep = json.loads((M.SCRATCH / 'ser8d' / 'layout-report.json').read_text())
    pj = M.FAST / f'{NAME}.pins.json'
    meta = json.loads(pj.read_text())
    meta['m5_channels'] = channels(meta['bbox'][2])
    meta['vss_bars'] = bars()
    pj.write_text(json.dumps(meta, indent=1))
    tr = rep['routes']['trunks']
    dc = {}
    for t in tr:
        if t['net'] in PORTS and (t['net'][0] == 'D' or t['net'] == 'WCKQ'):
            below = [u for u in tr if u is not t and abs(u['x'] - t['x']) < 0.05 and u['hi'] < t['lo']]
            dc[t['net']] = dict(x=t['x'], lo=round(t['lo'] - t['width'] / 2, 3), nblk=len(below), top=[])
    (tools.SCRATCH / 's13' / 'top' / 'serm5' / 'dcols.json').write_text(json.dumps(dc))


if __name__ == '__main__':
    build_top()
