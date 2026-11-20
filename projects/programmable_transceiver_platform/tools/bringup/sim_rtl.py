"""RTL back-end: the real pt_digital_macro (PT_CHIP) against the chip's generated stub analog top, driven over SPI from
Python through vvp's stdin/stdout. The bench is built from the instantiation of integration/chips/sim/tb_top_modes.sv
(so it follows that bench), with pt_ring_osc / aosc modelled as clocks gated by their enables.
    python3 sim_rtl.py rf|wired [--ring-mhz 210.5]"""
import argparse, re, subprocess, sys, tempfile
from pathlib import Path
import sequence

P = Path(__file__).resolve().parents[2]
TOP = P/'integration/chips'
F_REF = 50e6                     # tb_top_modes ref_clk (#10 half period)

LOOP = r'''
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
    "P": begin $display("OK dbg rs=%b por=%b en=%b on=%b pg=%b%b rst_n=%b", dut.reset_seen, por_n, island_en, island_on, s_pg_pll, s_pg_debug, dut.rst_n); end
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
    assert 'ro, 2' in head, 'tb_top_modes instantiation changed: update sim_rtl.py'
    tb = work/'tb_bringup.sv'
    tb.write_text('`timescale 1ns/1ps\n`include "pt_regmap_defs.svh"\n' + head + LOOP)
    rtl = sorted(str(p) for p in (P/'rtl').glob('*.sv'))
    vvp = work/'tb.vvp'; g = TOP/chip/'generated'
    subprocess.run(['iverilog', '-g2012', '-I', str(P/'rtl'), '-I', str(g), '-s', 'tb_bringup', '-o', str(vvp),
                    str(tb), str(g/'pt_analog_top_stub.sv')] + rtl, check=True, capture_output=True, text=True)
    return vvp


class Sim:
    def __init__(self, vvp, ring_mhz, trace=False):
        self.trace = trace
        self.p = subprocess.Popen(['vvp', '-n', str(vvp), f'+ring_half={500.0/ring_mhz:.6f}'], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True, bufsize=1)
    def _cmd(self, s):
        self.p.stdin.write(s + '\n'); self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError('simulator ended')
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
    def close(self):
        self.p.stdin.write('Q 0 0 0\n'); self.p.stdin.close(); self.p.wait(timeout=60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('chip', choices=('rf', 'wired'))
    ap.add_argument('--ring-mhz', type=float, default=210.5)
    ap.add_argument('--trace', action='store_true')
    ap.add_argument('--negative', action='store_true', help='build the other chip: the identity step must stop the sequence')
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as w:
        other = {'rf': 'wired', 'wired': 'rf'}[a.chip]
        sim = Sim(build(other if a.negative else a.chip, Path(w)), a.ring_mhz, a.trace)
        try:
            out = sequence.run(sim, sim, a.chip, F_REF)
        except RuntimeError as e:
            print(f'{"PASS (negative control)" if a.negative else "FAIL"}: {e}')
            sys.exit(0 if a.negative else 1)
        finally:
            sim.close()
    if a.negative:
        print('FAIL: negative control was not detected'); sys.exit(1)
    err = abs(out['ring_hz'] / (a.ring_mhz * 1e6) - 1)
    ok = err < 0.01 and out['supply_setpoint'] == sequence.trim_choice(a.ring_mhz * 1e6 / sequence.RING_TT_330)
    print(f'{"PASS" if ok else "FAIL"} pt_{a.chip}: ring read {out["ring_hz"]/1e6:.2f} MHz vs {a.ring_mhz} MHz modelled')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
