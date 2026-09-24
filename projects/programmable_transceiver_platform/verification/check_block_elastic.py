"""Reuse transaction scoreboard, then require sustained read throughput."""
import pathlib, subprocess

def main(staged=False):
    src = pathlib.Path('/src')
    out = pathlib.Path('/out')
    s = (src / 'sim/tb_block_fifo.sv').read_text().replace('tb_block_fifo', 'tb_block_elastic').replace('pt_block_fifo dut', 'pt_block_elastic dut').replace('dut.storage', 'dut.fifo.storage')
    s = s.replace('integer phase=0,cycles=0,i;', 'integer phase=0,cycles=0,i; integer streak=0,best=0;')
    s = s.replace('old_rg=dut.fifo.storage.rg;', 'old_rg=dut.fifo.storage.rg;\n  if(phase==3 && rd_valid&&rd_ready)begin streak=streak+1;if(streak>best)best=streak;end\n  else streak=0;\n  if(rst_n && (dut.receive_buffer.overflow || dut.receive_buffer.underflow))$fatal(1,"elastic buffer error");')
    s = s.replace('// Stop producer, drain all accepted blocks.', '// Saturate the source and require uninterrupted one-block-per-read-cycle service.\n  @(negedge wr_clk);force wr_valid=1;force wr_words=8;force rd_ready=1;phase=3;\n  #15000;\n  if(best<500)$fatal(1,"throughput bubble: best %0d",best);\n  $display("PASS sustained block reads=%0d",best);\n  // Stop producer, drain all accepted blocks.')
    if staged:
        s = s.replace('tb_block_elastic', 'tb_block_staged').replace('pt_block_elastic dut', 'pt_block_staged dut').replace('dut.fifo.storage', 'dut.link.fifo.storage').replace('dut.receive_buffer', 'dut.link.receive_buffer')
        s = s.replace('if(wr_ready!==0||rd_valid!==0)$fatal(1,"premature handshake");', 'if(rd_valid!==0)$fatal(1,"premature handshake");')
    (out / 'test.sv').write_text(s)
    rtl = [str(src / 'rtl' / f) for f in ('pt_fifo.sv', 'pt_block_fifo.sv', 'pt_block_elastic.sv')]
    if staged:
        rtl.append(str(src / 'rtl/pt_block_staged.sv'))

    def run(files, name):
        exe = str(out / name)
        subprocess.run(['iverilog', '-g2012', '-s', 'tb_block_staged' if staged else 'tb_block_elastic', '-o', exe, *files, str(out / 'test.sv')], check=True)
        return subprocess.run(['vvp', exe], text=True, capture_output=True)
    r = run(rtl, 'test')
    print(r.stdout)
    assert r.returncode == 0, r.stderr
    if staged:
        original = (src / 'rtl/pt_block_staged.sv').read_text()
        assert original.count('else if(wr_ready)begin') == 1
        (out / 'bad.sv').write_text(original.replace('else if(wr_ready)begin', 'else begin').replace('if(wr_valid&&!legal)bad_count', 'if(wr_ready&&wr_valid&&!legal)bad_count'))
    else:
        original = (src / 'rtl/pt_block_elastic.sv').read_text()
        assert original.count('.din({block_words,block_data})') == 1
        (out / 'bad.sv').write_text(original.replace('.din({block_words,block_data})', ".din({block_words,block_data ^ 80'd1})"))
    r = run(rtl[:-1] + [str(out / 'bad.sv')], 'bad')
    assert r.returncode != 0 and 'block mismatch' in r.stdout
    print('PASS overwrite-while-stalled mutation rejected' if staged else 'PASS corrupted elastic data rejected')

if __name__ == '__main__':
    main()
