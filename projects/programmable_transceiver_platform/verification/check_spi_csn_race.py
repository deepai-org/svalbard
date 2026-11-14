#!/usr/bin/env python3
"""CS_N rise vs the SPI write edge (interface row DT-11, structural fix in rtl/pt_spi.sv).

Runs sim/tb_spi_csn_race.sv
  1. on the RTL (zero-delay pt_spi, skewed register-file model),
  2. on a yosys generic-gate netlist of pt_spi with the spread transport-delay / metastability cell
     models of sim/spi_race_cells.sv (several delay seeds),
and on mutated copies of rtl/pt_spi.sv, each of which must FAIL:
  original       the pre-fix logic: wr_en = !cs_n && count==32 && cmd_r==0x80, datapath reset by CS_N
  csn_gate       wr_en = !cs_n && wr_q                       (CS_N pin back in the write qualifier)
  csn_data       address/data/command registers reset by CS_N again (write bus collapses under wr_en)
  write_twice    wr_q <= count>=31 && ...                    (a 33rd clock commits a second time)
  no_addr_guard  address capture without hdr_done            (gate level only: a tCSH violation can
                                                              rewrite the address under a set wr_q)
  no_saturate    bit counter wraps instead of stopping at 33 (review S4: a long frame writes again)
  cmd_msb_only   write qualifier looks at command bit 7 only (review S4: 0x81 / 0xC0 / 0xFF write)
  cmd_low_bits   write qualifier ignores command bit 7       (0x00 read / 0x01 write)
The bench also records the KNOWN LIMIT S1 (SCLK runt in idle after a 32-clock write frame commits the
frame a second time; pt_spi.sv is not changed for it) and asserts the 33-clock mitigation.
Light: iverilog + yosys on one 60-line module. Usage: check_spi_csn_race.py [--seeds 1,2] [--no-gl]
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SYNTH = ('read_verilog -sv {src}; synth -top pt_spi -flatten; '
         'dfflegalize -cell $_DFF_PN0_ 01 -cell $_DFF_NN0_ 01; abc -g AND,NAND,OR,NOR,XOR,XNOR,MUX; '
         'opt_clean -purge; write_verilog -noattr -noexpr {out}')
DATA_GOOD = (" always @(posedge sclk or negedge rst_n)begin\n"
             "  if(!rst_n)begin shift<=0;")
DATA_CSN = (" always @(posedge sclk or negedge serial_reset_n)begin\n"
            "  if(!serial_reset_n)begin shift<=0;")
MUTANTS = {
    'original': [("assign wr_en=wr_q;", "assign wr_en=!cs_n&&count==32&&cmd_r==8'h80;"), (DATA_GOOD, DATA_CSN),
                 ("if(count==15&&!hdr_done)", "if(count==15)")],
    'csn_gate': [("assign wr_en=wr_q;", "assign wr_en=!cs_n&&wr_q;")],
    'csn_data': [(DATA_GOOD, DATA_CSN)],
    'write_twice': [("wr_q<=count==31&&cmd_r==8'h80;", "wr_q<=count>=31&&cmd_r==8'h80;")],
    'no_saturate': [("else if(count<33)count<=count+1'b1;", "else count<=count+1'b1;")],
    'cmd_msb_only': [("wr_q<=count==31&&cmd_r==8'h80;", "wr_q<=count==31&&cmd_r[7];")],
    'cmd_low_bits': [("wr_q<=count==31&&cmd_r==8'h80;", "wr_q<=count==31&&cmd_r[6:0]==7'h00;")],
}
GL_ONLY = {'no_addr_guard': [("if(count==15&&!hdr_done)", "if(count==15)")]}


def sim(src, work, gl, seed):
    files = [str(src)]
    if gl:
        net = work/'pt_spi_gl.v'
        subprocess.run(['yosys', '-q', '-p', SYNTH.format(src=src, out=net)], check=True, capture_output=True)
        files = [str(net), str(PROJECT/'sim/spi_race_cells.sv')]
    vvp = work/'tb.vvp'
    subprocess.run(['iverilog', '-g2012', '-s', 'tb_spi_csn_race', '-o', str(vvp), *files,
                    str(PROJECT/'sim/tb_spi_csn_race.sv')], check=True, capture_output=True)
    out = subprocess.run(['vvp', '-n', str(vvp), f'+seed={seed}'], capture_output=True, text=True).stdout
    return bool(re.search(r'^SPI_CSN_RACE_PASS \d+ checks$', out, re.M)), out


def mutate(source, edits, path):
    for old, new in edits:
        assert source.count(old) == 1, f'pt_spi.sv text changed, update this check: {old!r}'
        source = source.replace(old, new)
    path.write_text(source)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='1,2')
    ap.add_argument('--no-gl', action='store_true')
    args = ap.parse_args()
    seeds = [int(s) for s in args.seeds.split(',')]
    good = PROJECT/'rtl/pt_spi.sv'
    source = good.read_text()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ok, out = sim(good, tmp, False, seeds[0])
        print('RTL :', '\n      '.join(l for l in out.splitlines() if re.search(r'sweep|SPI_CSN|KNOWN LIMIT|S1 mitigation', l)))
        if 'KNOWN LIMIT S1' not in out:
            sys.exit('SPI_CSN_RACE_CHECK_FAIL: the S1 known-limit case did not run')
        if not ok:
            print(out[-3000:])
            sys.exit('SPI_CSN_RACE_CHECK_FAIL: RTL bench failed')
        for name, edits in MUTANTS.items():
            ok, out = sim(mutate(source, edits, tmp/f'{name}.sv'), tmp, False, seeds[0])
            fails = len(re.findall(r'^FAIL ', out, re.M))
            if ok or not fails:
                sys.exit(f'SPI_CSN_RACE_CHECK_FAIL: RTL mutant {name} was not detected')
            print(f'RTL mutant {name}: detected ({fails}{"+" if "stopped early" in out else ""} failing checks; first: '
                  f'{re.search(r"^FAIL (.*?) \(t=", out, re.M)[1]})', flush=True)
        if not args.no_gl:
            for seed in seeds:
                ok, out = sim(good, tmp, True, seed)
                print(f'GL seed {seed}:', '\n      '.join(l for l in out.splitlines() if re.search(r'sweep|SPI_CSN|KNOWN LIMIT|S1 mitigation', l)), flush=True)
                if not ok:
                    print(out[-3000:])
                    sys.exit(f'SPI_CSN_RACE_CHECK_FAIL: gate-level bench failed (seed {seed})')
            for name, edits in {**MUTANTS, **GL_ONLY}.items():
                hit = None
                for seed in seeds:
                    ok, out = sim(mutate(source, edits, tmp/f'{name}.sv'), tmp, True, seed)
                    if not ok and re.search(r'^FAIL ', out, re.M):
                        hit = (seed, re.search(r'^FAIL (.*?) \(t=', out, re.M)[1])
                        break
                if not hit:
                    sys.exit(f'SPI_CSN_RACE_CHECK_FAIL: gate-level mutant {name} was not detected')
                print(f'GL mutant {name}: detected (seed {hit[0]}; first: {hit[1]})', flush=True)
    print('SPI_CSN_RACE_CHECK_PASS RTL' + ('' if args.no_gl else f' + gate level (seeds {args.seeds})') + '; all mutants detected')


if __name__ == '__main__':
    main()
