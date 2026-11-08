#!/usr/bin/env python3
"""Host-link pad-cell toggle-rate screen from the provider gf180mcu_fd_io Liberty (canary PDK).

The provider cells have no characterized maximum toggle frequency, so this screen derives one
from the Liberty arcs with an explicit, conservative eye budget (engineering screen, not a
qualification; no package/board/FPGA/SSO modelling):

  D2H (pad driver, A -> PAD, load = external lumped load table coordinate):
      UI_min = t_tr + DCD + W_rx + S
        t_tr  worst 10-90 % PAD transition (rise/fall) at the load
        DCD   |cell_rise - cell_fall| A->PAD (duty-cycle distortion of both data and the
              forwarded clock through identical cells)
        W_rx  FPGA input setup+hold window, assumed 1.0 ns (generic GPIO DDR class)
        S     board/package/intra-bank skew budget, assumed 0.4 ns
  H2D (pad receiver, PAD -> Y into the digital macro, Y load 0.1 pF):
      UI_min = t_in + DCD_in + t_tr_Y + W_cap + S
        t_in   10-90 % edge at the pad from the FPGA, at the Liberty PAD max_transition 1.0 ns
        DCD_in |cell_rise - cell_fall| PAD->Y at that input slew
        t_tr_Y worst Y transition
        W_cap  capture-flop setup+hold inside the macro, 0.3 ns (STA reports the actual value)
  f_DDR_max = 1 / (2 UI_min) (pin clock; word rate is 2 f). SDR: f_SDR_max = 1 / UI_min.
Also flagged: PAD transitions above the Liberty max_transition (1.0 ns) - outside the
characterized range of the cell as a driver of a full-swing edge.
"""
import argparse
import json
import re
from pathlib import Path

IO = '/pdk/gf180mcuD/libs.ref/gf180mcu_fd_io/lib/gf180mcu_fd_io__{}.lib'
CORNERS = ['tt_025C_3v30', 'ss_125C_2v97', 'ff_n40C_3v63']
LOADS_PF = [5.0, 6.0, 10.0]          # 6 pF = contract full-rate external load target
W_RX, SKEW, W_CAP, T_IN = 1.0, 0.4, 0.3, 1.0
UI_TARGET = 3.2                       # 156.25 MHz DDR


def blocks(text, kw):
    """Yield (header_arg, body) for every `kw (arg) { ... }` group at any depth."""
    for m in re.finditer(kw + r'\s*\(\s*"?([^")]*)"?\s*\)\s*\{', text):
        i, depth = m.end(), 1
        while depth:
            c = text[i]
            depth += c == '{'
            depth -= c == '}'
            i += 1
        yield m.group(1), text[m.end():i - 1]


def table(body, name):
    for _, b in blocks(body, name):
        i1 = [float(x) for x in re.search(r'index_1\s*\(\s*"([^"]*)"', b).group(1).split(',')]
        i2m = re.search(r'index_2\s*\(\s*"([^"]*)"', b)
        i2 = [float(x) for x in i2m.group(1).split(',')] if i2m else [0.0]
        vals = re.search(r'values\s*\((.*?)\)\s*;', b, re.S).group(1)
        rows = [[float(x) for x in r.split(',')] for r in re.findall(r'"([^"]*)"', vals)]
        return i1, i2, rows
    return None


def interp(t, x, y):
    i1, i2, v = t

    def seg(ax, q):
        for k in range(len(ax) - 1):
            if q <= ax[k + 1]:
                return k
        return len(ax) - 2
    a = seg(i1, x)
    if len(i2) == 1:
        fx = (x - i1[a]) / (i1[a + 1] - i1[a])
        return v[a][0] + fx * (v[a + 1][0] - v[a][0])
    b = seg(i2, y)
    fx = (x - i1[a]) / (i1[a + 1] - i1[a])
    fy = (y - i2[b]) / (i2[b + 1] - i2[b])
    r0 = v[a][b] + fy * (v[a][b + 1] - v[a][b])
    r1 = v[a + 1][b] + fy * (v[a + 1][b + 1] - v[a + 1][b])
    return r0 + fx * (r1 - r0)


def cell(text, name):
    for arg, body in blocks(text, 'cell'):
        if arg == name:
            return body
    return None


def arcs(cellbody, pin, related):
    out = []
    for pn, pb in blocks(cellbody, 'pin'):
        if pn != pin:
            continue
        for _, tb in blocks(pb, 'timing'):
            if re.search(r'related_pin\s*:\s*"%s"' % related, tb) and 'combinational' in tb:
                when = re.search(r'when\s*:\s*"([^"]*)"', tb)
                out.append(dict(when=when.group(1) if when else '',
                                **{k: table(tb, k) for k in ('cell_rise', 'cell_fall', 'rise_transition', 'fall_transition')}))
        mt = re.search(r'max_transition\s*:\s*([0-9.]+)', pb)
        cap = re.search(r'\bcapacitance\s*:\s*([0-9.]+)', pb)
        return out, float(mt.group(1)) if mt else None, float(cap.group(1)) if cap else None
    return [], None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    res = dict(method=__doc__.strip().split('\n\n')[1], assumptions=dict(
        fpga_rx_window_ns=W_RX, skew_budget_ns=SKEW, macro_capture_window_ns=W_CAP, pad_input_edge_ns=T_IN,
        driver_input_slew_ns=0.5, y_load_pf=0.1, ui_target_ns=UI_TARGET), corners={})
    for c in CORNERS:
        p = Path(IO.format(c))
        text = p.read_text()
        cr = dict(liberty=p.name, outputs=[], inputs=[])
        for cname in ('gf180mcu_fd_io__bi_24t', 'gf180mcu_fd_io__bi_t'):
            body = cell(text, cname)
            out_arcs, pad_mt, pad_cap = arcs(body, 'PAD', 'A')
            for arc in out_arcs:
                for L in LOADS_PF:
                    rr, ff = interp(arc['cell_rise'], 0.5, L), interp(arc['cell_fall'], 0.5, L)
                    tr, tf = interp(arc['rise_transition'], 0.5, L), interp(arc['fall_transition'], 0.5, L)
                    t_tr, dcd = max(tr, tf), abs(rr - ff)
                    ui = t_tr + dcd + W_RX + SKEW
                    cr['outputs'].append(dict(cell=cname.split('__')[1], when=arc['when'], load_pf=L,
                                              delay_rise_ns=round(rr, 3), delay_fall_ns=round(ff, 3),
                                              tr_rise_ns=round(tr, 3), tr_fall_ns=round(tf, 3), dcd_ns=round(dcd, 3),
                                              ui_min_ns=round(ui, 3), f_ddr_max_mhz=round(1000 / (2 * ui), 1),
                                              f_sdr_max_mhz=round(1000 / ui, 1),
                                              meets_156p25_ddr=ui <= UI_TARGET,
                                              exceeds_liberty_max_transition=t_tr > (pad_mt or 1e9),
                                              pad_capacitance_pf=pad_cap))
        for cname in ('gf180mcu_fd_io__bi_24t', 'gf180mcu_fd_io__in_c', 'gf180mcu_fd_io__in_s'):
            body = cell(text, cname)
            in_arcs, _, _ = arcs(body, 'Y', 'PAD')
            for arc in in_arcs:
                rr, ff = interp(arc['cell_rise'], T_IN, 0.1), interp(arc['cell_fall'], T_IN, 0.1)
                tr, tf = interp(arc['rise_transition'], T_IN, 0.1), interp(arc['fall_transition'], T_IN, 0.1)
                dcd = abs(rr - ff)
                ui = T_IN + dcd + max(tr, tf) + W_CAP + SKEW
                cr['inputs'].append(dict(cell=cname.split('__')[1], when=arc['when'], delay_rise_ns=round(rr, 3),
                                         delay_fall_ns=round(ff, 3), dcd_ns=round(dcd, 3),
                                         y_tr_ns=round(max(tr, tf), 3), ui_min_ns=round(ui, 3),
                                         f_ddr_max_mhz=round(1000 / (2 * ui), 1), meets_156p25_ddr=ui <= UI_TARGET))
        res['corners'][c] = cr
    # Summary: best provider configuration per corner at the 6 pF target load.
    summ = {}
    for c, cr in res['corners'].items():
        o6 = [o for o in cr['outputs'] if o['load_pf'] == 6.0]
        best = min(o6, key=lambda o: o['ui_min_ns'])
        site = [o for o in o6 if o['cell'] == 'bi_24t' and o['when'].replace(' ', '') in ('!IE&OE&!SL',)]
        ins = [i for i in cr['inputs'] if i['cell'] == 'bi_24t']
        summ[c] = dict(best_output=dict(cell=best['cell'], when=best['when'], f_ddr_max_mhz=best['f_ddr_max_mhz']),
                       bi_24t_fast_slew_6pF_f_ddr_max_mhz=site[0]['f_ddr_max_mhz'] if site else None,
                       bi_24t_input_f_ddr_max_mhz=min(i['f_ddr_max_mhz'] for i in ins) if ins else None)
    res['summary'] = summ
    Path(a.out).write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps(summ, indent=1))


if __name__ == '__main__':
    main()
