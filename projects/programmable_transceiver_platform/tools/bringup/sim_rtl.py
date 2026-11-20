"""RTL back-end: the real pt_digital_macro (PT_CHIP) against the chip's generated stub analog top, driven over SPI from
Python through vvp's stdin/stdout. The bench is built from the instantiation of integration/chips/sim/tb_top_modes.sv
(so it follows that bench), with pt_ring_osc / aosc modelled as clocks gated by their enables.
    python3 sim_rtl.py rf|wired [--ring-mhz 210.5]"""
import argparse, re, subprocess, sys, tempfile
from pathlib import Path
import sequence, atb

P = Path(__file__).resolve().parents[2]
TOP = P/'integration/chips'
F_REF = 50e6                     # tb_top_modes ref_clk (#10 half period)

LOOP = r'''
 // host word clock (156.25 MHz) exists only when the software programmed the TX-ring host_follow path (D-HF):
 // H2D_CLK -> ring reference (PS_H2D), TX ring enabled, host prescaler /4, host select HS_INT
 always @* hw_en = analog.p_clockmux__PS_H2D & analog.p_pll_tx__EN & analog.p_prescale__EN & analog.p_prescale__D4 & analog.p_clockmux__HS_INT;
 // FPGA model: H2D is the D2H stream looped back; the forwarded clock is delayed by the trained capture delay
 initial if ($test$plusargs("pg_dead")) force s_pg_lo = 1'b0;   // negative control: dead lo switch on pt_rf
 real cap_dly = 0.0; reg dclk_d = 0; always @(dut.d2h_clk_pin) dclk_d <= #(cap_dly) dut.d2h_clk_pin;
 wire h2d_lb = dclk_d; wire [9:0] h2d_pin_lb = dut.d2h_pin;
 integer qn = 0; always @(posedge dut.core_clk) if ($test$plusargs("qtrace") && qn < 40 && dut.host_rst_n) begin qn = qn + 1; $display("Q %h en=%b crst=%b", dut.d2h_quad, dut.host.en_c, dut.core_rst_n); end
 reg [9:0] capbuf [0:1023]; integer capn = 0, k;
 always @(dclk_d) if (dut.d2h_oe && capn < 1024) begin capbuf[capn] = dut.d2h_pin; capn = capn + 1; end   // the FPGA's capture memory, from arming
 real ring_half = 2.375; reg ro = 0; always #(ring_half) ro = analog.p_ring_osc__EN ? ~ro : 1'b0;
 task spi(input [7:0] command, address, input [15:0] value, output [15:0] result);
  reg [31:0] tx; integer i;
  begin
   tx = {command, address, value}; result = 0; cs_n = 0; #50;
   for (i = 31; i >= 0; i = i-1) begin mosi = tx[i]; #50; sclk = 1; #50; if (i < 16) result[i] = miso; sclk = 0; end
   #50; cs_n = 1; mosi = 0; #50;
  end
 endtask
 reg [8*64-1:0] line; integer c, a, d, n; reg [15:0] r; reg [7:0] op;
 initial begin
  if ($value$plusargs("ring_half=%f", ring_half)) ;
  forever begin
   n = $fgets(line, 32'h8000_0000);
   if (n == 0) $finish;
   n = $sscanf(line, "%c %d %d %d", op, c, a, d);
   case (op)
    "X": begin spi(c, a, d, r); if (^r === 1'bx) $display("R X %b", r); else $display("R %0d", r); end
    "W": begin #(c * 1000); $display("OK"); end
    "L": begin rst_pad = c; #100; $display("OK"); end
    "A": begin $display("R 0 atb %0d %0d %0d %0d", atb1_sw, atb1_grp, atb1_en, island_on); end
    "T": begin cap_dly = c / 1000.0; capn = 0; $display("OK"); end
    "C": begin $write("R 0 cap"); for (k = 0; k < capn; k = k + 1) $write(" %0d", capbuf[k]); $display(""); end
    "P": begin $display("OK dbg hw=%b ps=%b txen=%b pen=%b d4=%b hs=%b oe=%b capn=%0d rs=%b rst_n=%b", hw_en, analog.p_clockmux__PS_H2D, analog.p_pll_tx__EN, analog.p_prescale__EN, analog.p_prescale__D4, analog.p_clockmux__HS_INT, dut.d2h_oe, capn, dut.reset_seen, dut.rst_n); end
    default: $finish;
   endcase
   $fflush;
  end
 end
endmodule
'''


def build(chip, work):
    src = (TOP/'sim/tb_top_modes.sv').read_text()
    head = src[src.index('module tb_top_modes;'):src.index(' integer errors = 0')]
    head = head.replace('module tb_top_modes;', 'module tb_bringup;').replace('`include "tb_fields.svh"', '')
    head = head.replace(".fc_src({1'b0, aosc, 4'b0})", ".fc_src({1'b0, aosc, 1'b0, ro, 2'b0})")
    head = '\n'.join(l for l in head.split('\n') if 'task clear_mon_fault' not in l)
    head = head.replace(".h2d_clk(h2d_clk), .h2d_pin(10'b0)", ".h2d_clk(h2d_lb), .h2d_pin(h2d_pin_lb)")
    assert 'h2d_lb' in head and 'ro, 2' in head, 'tb_top_modes instantiation changed: update sim_rtl.py'
    tb = work/'tb_bringup.sv'
    tb.write_text('`timescale 1ns/1ps\n`include "pt_regmap_defs.svh"\n' + head + LOOP)
    rtl = sorted(str(p) for p in (P/'rtl').glob('*.sv'))
    vvp = work/'tb.vvp'; g = TOP/chip/'generated'
    subprocess.run(['iverilog', '-g2012', '-I', str(P/'rtl'), '-I', str(g), '-s', 'tb_bringup', '-o', str(vvp),
                    str(tb), str(g/'pt_analog_top_stub.sv')] + rtl, check=True, capture_output=True, text=True)
    return vvp


class Sim:
    def __init__(self, vvp, ring_mhz, trace=False, extra=()):
        self.trace = trace
        self.p = subprocess.Popen(['vvp', '-n', str(vvp), f'+ring_half={500.0/ring_mhz:.6f}'] + (['+qtrace'] if trace else []) + list(extra), stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True, bufsize=1)
    def _cmd(self, s):
        self.p.stdin.write(s + '\n'); self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError('simulator ended')
            if self.trace and line.startswith('Q '): print('  ', line.strip())
            if line.startswith(('R ', 'OK')):
                return line
    def xfer(self, cmd, addr, data):
        r = self._cmd(f'X {cmd} {addr} {data}').split()
        if self.trace: print('  spi', hex(cmd), hex(addr), hex(data), '->', r[1:])
        if r[1] == 'X':
            raise RuntimeError(f'read of 0x{addr:02X} returned unknown bits {r[2]}')
        return int(r[1])
    def reset(self, low):
        if low:                      # an event-driven simulator needs an edge to fire the asynchronous reset
            self._cmd('L 1 0 0')
        self._cmd(f'L {0 if low else 1} 0 0')
    def wait_us(self, t):
        self._cmd(f'W {max(1, int(round(t)))} 0 0')
    def arm(self, delay_ps):
        """FPGA side: set the capture delay and arm a 1024-word capture of D2H (first words after arming)."""
        self._cmd(f'T {int(delay_ps)} 0 0')
    def captured(self):
        line = self._cmd('C 0 0 0').split()
        return [int(x) if x.isdigit() else None for x in line[3:]]
    def atb_state(self):
        """(atb1_sw, atb1_grp, atb1_en, island_on) as driven by the macro: the switch path the software closed."""
        return tuple(int(x) for x in self._cmd('A 0 0 0').split()[3:7])
    def close(self):
        self.p.stdin.write('Q 0 0 0\n'); self.p.stdin.close(); self.p.wait(timeout=60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('chip', choices=('rf', 'wired'))
    ap.add_argument('--ring-mhz', type=float, default=210.5)
    ap.add_argument('--trace', action='store_true')
    ap.add_argument('--negative', action='store_true', help='build the other chip: the identity step must stop the sequence')
    ap.add_argument('--negative-host', action='store_true', help='host prescaler /8 instead of /4: no 156.25 MHz word clock, training must fail')
    ap.add_argument('--negative-pg', action='store_true', help='pt_rf: lo switch power-good held low: step 5 must stop')
    ap.add_argument('--negative-atb', action='store_true', help='also sense a code with no leaf on this chip: must fail')
    a = ap.parse_args()
    if a.negative_pg:
        a.negative = True
    if a.negative_atb:
        sequence.EXTRA_ATB = ({'rf': 7, 'wired': 8}[a.chip],)
    if a.negative_host:
        sequence.HOST_PRESCALE = 3; a.negative = True
    with tempfile.TemporaryDirectory() as w:
        other = {'rf': 'wired', 'wired': 'rf'}[a.chip]
        sim = Sim(build(other if a.negative and not (a.negative_host or a.negative_pg) else a.chip, Path(w)), a.ring_mhz, a.trace, ['+pg_dead'] if a.negative_pg else [])
        meter = atb.AtbSim(sim, a.chip); sim.atb_read = meter.read
        try:
            out = sequence.run(sim, sim, a.chip, F_REF)
            out['host_link'] = sequence.host_link(sim, sim, a.chip)
            sequence.h2d_health(sim, a.chip)
            sequence.mode(sim, sim, a.chip)
        except RuntimeError as e:
            print(f'{"PASS (negative control)" if a.negative else "FAIL"}: {e}')
            sys.exit(0 if a.negative else 1)
        finally:
            sim.close()
    if a.negative_atb:
        ok = bool(out['atb_fail']); print(('PASS (negative control): ATB ' if ok else 'FAIL: ATB negative not detected ') + str(out['atb_fail'])); sys.exit(0 if ok else 1)
    if a.negative:
        print('FAIL: negative control was not detected'); sys.exit(1)
    err = abs(out['ring_hz'] / (a.ring_mhz * 1e6) - 1)
    f_dig_model = 1e9 / (2 * 6.5)        # pt_dig_ring behavioural model HALF_NS = 6.5 (rtl/pt_cells.sv)
    err_d = abs(out['dig_ring_hz'] / f_dig_model - 1)
    ok = not out['atb_fail'] and err < 0.01 and err_d < 0.01 and out['supply_setpoint'] == sequence.trim_choice(
        a.ring_mhz * 1e6 / sequence.RING_TT_330, f_dig_model / sequence.DIG_TT_330)
    print(f'{"PASS" if ok else "FAIL"} pt_{a.chip}: ring read {out["ring_hz"]/1e6:.2f} MHz vs {a.ring_mhz} modelled; dig ring {out["dig_ring_hz"]/1e6:.2f} vs {f_dig_model/1e6:.2f} MHz')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
