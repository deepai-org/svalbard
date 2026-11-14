#!/usr/bin/env python3
"""Independent decode check: force the register file's ACTIVE fields, compare every static c_* port with a table written from
ctl_ports.txt + the analog owners' pin files (not from the RTL)."""
import json, re, random, sys
from pathlib import Path
P = Path(__file__).resolve().parents[2] if "decode_table" in str(Path(__file__).resolve()) else Path("/home/ubuntu/svalbard/projects/programmable_transceiver_platform"); TOP = P/"integration/top"
reg = json.loads((P/'spec/register-map.json').read_text())
rf = (P/'rtl/pt_regfile.sv').read_text()
FIELDS = [f for f in reg['fields'] if re.search(r'reg\[(\d+):0\]s_%s[,;]' % f['sv'], rf)]
def width(f):
    m = re.search(r'reg\[(\d+):0\]s_%s[,;]' % f['sv'], rf); f['direct_wire'] = bool(re.search(r'wire\[\d+:0\]a_%s=' % f['sv'], rf)); return int(m.group(1)) + 1
for f in FIELDS: f['w'] = width(f)
PORTS = [(c[0].strip(), int(c[1]), int(c[2])) for c in (l.split('|') for l in (TOP/'ctl_ports.txt').read_text().split('\n') if l.startswith('c_'))]
DYN = [('rx_gain', 7), ('rx_gain_active', 1), ('rf_mute', 1), ('vth_fast', 2), ('vth_a', 8), ('vth_b', 8), ('vreg_tx_ok', 1), ('vreg_rx_ok', 1), ('bg_ok', 1)]
BENCH = [('fault_pin', 1), ('pg', 10), ('wired_on_ext', 1)]
EXTRA = [('island_on', 6), ('island_en', 6), ('wire_rx_ptrim_en', 1), ('rx_en_aux', 1), ('rx_en_wtx_ext', 1), ('wire_tx_data', 40), ('rf_tx_sample', 24)]
def legal(f):
    if f.get('allowed'): return list(f['allowed'])
    lo = f.get('minimum') or 0; hi = f.get('maximum'); hi = (1 << f['w']) - 1 if hi is None else hi
    return range(lo, hi + 1)
def default(f):
    d = f['default']
    if isinstance(d, str) or (f.get('values') and d in f['values'] and not isinstance(d, bool) and f.get('allowed')):
        return f['values'].index(d)
    return d
def write_tb(nvec, settle, out='tb_dec.sv'):
    L = ['`timescale 1ns/1ps', 'module tb_dec;',
         ' reg rst_pad = 0, sclk = 0, cs_n = 1, mosi = 0, ref_clk = 0, fault_pin = 0, wired_on_ext = 0; reg [9:0] pg = 0;',
         ' always #10 ref_clk = ~ref_clk;', ' reg wtx_clk = 0; always #10.4 wtx_clk = c_wiredtx_ser_en ? ~wtx_clk : 1\'b0;']
    for n, w, _ in PORTS: L.append(f' wire [{w-1}:0] {n};')
    L += [' wire [5:0] island_on, island_en, island_off; wire wire_rx_ptrim_en, rx_en_aux, rx_en_wtx_ext; wire [39:0] wire_tx_data; wire [23:0] rf_tx_sample;',
          ' pt_digital_macro dut(.reset_n_pad(rst_pad), .por_n(1\'b1), .por_bypass(1\'b0), .spi_sclk(sclk), .spi_cs_n(cs_n), .spi_mosi(mosi),',
          '  .island_en(island_en), .island_on(island_on), .island_off(island_off), .s_pg_wired_rx(pg[0]), .s_pg_wired_cap(pg[1]), .s_pg_wired_tx(pg[2]), .s_pg_rf_rx(pg[3]),',
          '  .s_pg_rf_tx(pg[4]), .s_pg_lod(pg[5]), .s_pg_lo(pg[6]), .s_pg_pll(pg[7]), .s_pg_conv(pg[8]), .s_pg_debug(pg[9]), .wired_on_ext(wired_on_ext),',
          '  .wire_rx_ptrim_en(wire_rx_ptrim_en), .fault(fault_pin), .rx_en_aux(rx_en_aux), .rx_en_wtx_ext(rx_en_wtx_ext), .wire_tx_data(wire_tx_data), .rf_tx_sample(rf_tx_sample),',
          '  .host_word_clk(1\'b0), .h2d_clk(1\'b0), .h2d_pin(10\'b0), .ref_clk(ref_clk), .wire_rx_clk(1\'b0), .wire_tx_clk(wtx_clk), .rf_rx_clk(1\'b0), .rf_tx_clk(1\'b0), .ct_wclk(1\'b0),',
          '  .fc_src(6\'b0), .wire_rx_data(40\'b0), .wire_rx_edge(20\'b0), .rf_rx_sample(24\'b0), .rf_rx_sample_b(24\'b0), .rf_rx_ph_i(1\'b0), .rf_rx_ph_q(1\'b0),',
          '  .s_pll_tx_lock(1\'b0), .s_pll_cdr_lock(1\'b0), .s_ref_present(1\'b1), .s_refbuf_ready(1\'b0), .s_adc_i_ovl(1\'b0), .s_adc_i_b_ovl(1\'b0), .s_adc_q_ovl(1\'b0), .s_adc_q_b_ovl(1\'b0),',
          '  .s_adc_i_done(1\'b0), .s_adc_i_b_done(1\'b0), .s_adc_q_done(1\'b0), .s_adc_q_b_done(1\'b0), .s_detect_diff_pos(1\'b0), .s_detect_diff_neg(1\'b0), .s_detect_se_p(1\'b0),',
          '  .s_detect_se_n(1\'b0), .s_wrx_slp(1\'b0), .s_wrx_slm(1\'b0), .s_wtx_ext_data(1\'b0), .s_aux_present(1\'b0), .s_wtx_ext_present(1\'b0),']
    L.append('  ' + ', '.join(f'.{n}({n})' for n, _, _ in PORTS) + ');')
    nin = len(FIELDS) + len(DYN) + len(BENCH)
    L += [f' reg [31:0] v [0:{nin-1}]; integer fi, fo, k, n, rc;', ' task apply; begin']
    for i, f in enumerate(FIELDS): L.append(f'  force dut.digital.control.regs.{"s" if f["direct_wire"] else "a"}_{f["sv"]} = v[{i}][{f["w"]-1}:0];')
    for j, (n, w) in enumerate(DYN): L.append(f'  force dut.{n} = v[{len(FIELDS)+j}][{w-1}:0];')
    for j, (n, w) in enumerate(BENCH): L.append(f'  {n} = v[{len(FIELDS)+len(DYN)+j}][{w-1}:0];')
    L += [' end endtask', ' initial begin', '  #20 rst_pad = 1; #20 rst_pad = 0; #50 rst_pad = 1; #200;',
          '  fi = $fopen("vec.txt", "r"); fo = $fopen("out.txt", "w");',
          f'  for (n = 0; n < {nvec}; n = n + 1) begin',
          f'   for (k = 0; k < {nin}; k = k + 1) rc = $fscanf(fi, "%h", v[k]);',
          f'   apply; #{settle};',
          '   $fdisplay(fo, "' + ' '.join(['%h'] * (len(PORTS) + len(EXTRA))) + '", ' + ', '.join([n for n, _, _ in PORTS] + [n for n, _ in EXTRA]) + ');',
          '  end', '  $fclose(fo); $finish;', ' end', 'endmodule']
    Path(out).write_text('\n'.join(L) + '\n')
def write_vec(vectors, out='vec.txt'):
    with open(out, 'w') as fh:
        for F, D, B in vectors:
            fh.write(' '.join('%x' % F[f['name']] for f in FIELDS) + ' ' + ' '.join('%x' % D[n] for n, _ in DYN) + ' ' + ' '.join('%x' % B[n] for n, _ in BENCH) + '\n')
def read_out(out='out.txt'):
    R = []
    for line in open(out):
        t = line.split(); R.append({n: t[i] for i, n in enumerate([p[0] for p in PORTS] + [e[0] for e in EXTRA])})
    return R
