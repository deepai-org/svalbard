#!/usr/bin/env python3
"""pin_order_wired.py: writes pin_order_wired.cfg, the pt_wired pin order (row ASM-11, chip assembly).

The N / W / E sections are copied from pin_order.cfg (shared with pt_rf). The south edge is laid out slot by slot so
that wire_tx_data and the pt_wiredtx8 control pins sit at the macro x positions assembly asked for (pt_wiredtx8 is
directly below that stretch of the south edge):
  * wire_tx_clk, c_wiredtx_main_code[1-4,7], c_wiredtx_post_code[0-3], c_wiredtx_ser_en at x 943-1089 um;
  * wire_tx_data in four groups of ten, centred on x 1110 / 1282 / 1451 / 1623 um, in pt_wiredtx8's D order;
  * c_wiredtx_main_code[0,5,6], c_wiredtx_post_code[4-7], c_wiredtx_post_pol at x 1629-1676 um.
Every other south pin keeps its group order and is packed left of x 943 um or into the gaps between the data groups.
Slots: '@min_distance=2.24' on the south edge gives one slot per 4 Metal2 tracks (x = 0.28 + 2.24 * i um); the list
is padded with virtual pins ($n) to exactly the slot count, so the flow places pin i at slot i (io_place.py
equally_spaced_sequence with total == tracks). WIDTH must match the outline in wired/config.json.
"""
import re
from pathlib import Path

H = Path(__file__).resolve().parent
WIDTH = 1676.0
PITCH = 2.24
X0 = 0.28
NSLOT = len(range(0, round((WIDTH - X0) / 0.56) + 1, 4))   # Metal2 tracks every 0.56 um from 0.28, every 4th

def slot(x):
    return round((x - X0) / PITCH)

def bits(name, idx):
    return [f'{name}\\[{i}\\]' for i in idx]

# pt_wiredtx8 D order along increasing x (row ASM-11)
DGROUPS = [([12, 4, 0, 8, 16, 24, 32, 20, 28, 36], 1110.0), ([13, 5, 25, 17, 9, 1, 33, 21, 29, 37], 1282.0),
           ([22, 14, 6, 2, 10, 18, 26, 34, 30, 38], 1451.0), ([15, 7, 3, 11, 19, 27, 35, 23, 31, 39], 1614.0)]
CTRL_A = ['wire_tx_clk'] + bits('c_wiredtx_main_code', [1, 2, 3, 4, 7]) + bits('c_wiredtx_post_code', [0, 1, 2, 3]) + ['c_wiredtx_ser_en']
CTRL_B = bits('c_wiredtx_main_code', [0, 5, 6]) + bits('c_wiredtx_post_code', [4, 5, 6, 7]) + ['c_wiredtx_post_pol']
MOVED = r'c_wiredtx_(main_code|post_code|post_pol|ser_en)'
# remaining south groups (regex lines, as in pin_order.cfg), left part then the filler for the data-group gaps
# (regex, x start um or None): d2h_* starts under the hand-placed D2H block (macro x 630-851 on the south edge)
LEFT = ['rf_.*', 'reset_n_pad', 'por_n', 'por_bypass', 'host_word_clk', ('d2h_.*', 640.0), 'spi_.*', 'wire_rx_.*',
        'c_wiredtx_(?!main_code|post_code|post_pol|ser_en).*', 'c_txpad_.*', 'c_wtxfb_.*']
GAP = ['c_usb_.*', 'c_hsbias_.*', 'c_adc_.*', 'c_dac_.*', 'c_refbuf_.*', 's_adc_.*', 's_refbuf_ready', 's_wtx_ext_.*']

def main():
    base = (H / 'pin_order.cfg').read_text()
    rest = base[base.index('#N'):]
    plan = {}          # slot -> pin regex (single pin)
    def put(names, x_start, step=1):
        s = slot(x_start)
        for n in names:
            while s in plan:
                s += 1
            plan[s] = n
            s += step
    put(CTRL_A, 945.0, 6)                       # 11 pins over ~140 um
    for order, xc in DGROUPS:
        put(bits('wire_tx_data', order), xc - 4.5 * PITCH)
    put(CTRL_B, 1631.0)
    assert max(plan) < NSLOT, 'south pins past the east edge'
    # group-regex lines: LEFT packed from x 20 um, GAP into the gaps between the data groups
    lines = ['#S', '@min_distance=2.24']
    seq = []          # list of (slot, regex)
    s = slot(20.0)
    # The flow expands a group regex into all matching pins in consecutive slots, so groups are given room by the
    # count of their members: read it from the macro port list.
    ports = ports_of_macro()
    out = []
    cur = 0
    def emit_virtual(n):
        if n > 0:
            out.append(f'${n}')
    s = slot(20.0)
    for g in LEFT:
        if isinstance(g, tuple):
            g, xs = g
            s = max(s, slot(xs))
        n = sum(1 for p in ports if re.match(f'^{g}$', p) and not re.match(f'^{MOVED}', p) and p not in ('wire_tx_clk',) and not p.startswith('wire_tx_data'))
        if g == 'wire_rx_.*':
            g = 'wire_rx_.*'
        emit_virtual(s - cur); cur = s
        out.append(g); cur += n; s = cur
    assert cur <= slot(940.0), f'left groups overrun x 940 um ({cur} slots)'
    gaps = [(slot(1110.0 + 6 * PITCH), slot(1282.0 - 6 * PITCH)), (slot(1282.0 + 6 * PITCH), slot(1451.0 - 6 * PITCH)),
            (slot(1451.0 + 6 * PITCH), slot(1614.0 - 6 * PITCH))]
    # explicit pins up to the first gap
    def explicit_until(limit):
        nonlocal cur
        for sl in sorted(k for k in plan if cur <= k < limit):
            emit_virtual(sl - cur); out.append(plan[sl]); cur = sl + 1
    gi = 0
    for g in GAP:
        n = sum(1 for p in ports if re.match(f'^{g}$', p))
        while gi < len(gaps) and gaps[gi][1] - max(gaps[gi][0], cur) < n:
            gi += 1
        assert gi < len(gaps), f'no gap left for {g} ({n} pins)'
        start = max(gaps[gi][0], cur)
        explicit_until(start)
        emit_virtual(start - cur); cur = start
        out.append(g); cur += n
    explicit_until(NSLOT)
    emit_virtual(NSLOT - cur)
    text = '\n'.join(lines + out) + '\n' + rest
    (H / 'pin_order_wired.cfg').write_text(text)
    print(f'pin_order_wired.cfg: {NSLOT} south slots, {len(plan)} placed pins')

def ports_of_macro():
    """bit-blasted port names of the pt_wired macro, from the yosys netlist of synth_area.sh 2 (run it after any port
    change: scratch/digital_hardening-synth/2/pt_digital_macro.syn.v)"""
    nl = (H.parents[3] / 'scratch/digital_hardening-synth/2/pt_digital_macro.syn.v').read_text()
    mod = nl[nl.index('module pt_digital_macro'):]
    mod = mod[:mod.index('endmodule')]
    ports = []
    for d, a, b, name in re.findall(r'^\s*(input|output|inout)\s+(?:\[(\d+):(\d+)\]\s+)?(\S+);', mod, re.M):
        if a is None or a == '':
            ports.append(name)
        else:
            ports += [f'{name}[{i}]' for i in range(min(int(a), int(b)), max(int(a), int(b)) + 1)]
    return ports

if __name__ == '__main__':
    main()
