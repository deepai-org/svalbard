"""Ensure the independent scoreboard rejects lost metadata and invalid admission."""
import pathlib
import subprocess
source = pathlib.Path('/src/rtl/pt_block_fifo.sv').read_text()
for name, old, new in [
    ('metadata', '.din({wr_words,wr_data})', ".din({4'd8,wr_data})"),
    ('invalid', '.push(wr_valid&&wr_ready&&legal)', '.push(wr_valid&&wr_ready)'),
    ('reset_bypass', 'assign wr_ready=wr_active&&!full;', 'assign wr_ready=rst_n&&!full;'),
]:
    assert source.count(old) == 1
    path = pathlib.Path('/out') / (name + '.sv')
    path.write_text(source.replace(old, new))
    exe = '/out/' + name
    subprocess.run(['iverilog', '-g2012', '-s', 'tb_block_fifo', '-o', exe,
                    '/src/rtl/pt_fifo.sv', str(path), '/src/sim/tb_block_fifo.sv'], check=True)
    result = subprocess.run(['vvp', exe], text=True, capture_output=True)
    if result.returncode == 0 or not any(message in result.stdout for message in ('block mismatch', 'fault mismatch', 'premature handshake')):
        raise RuntimeError((name, result.returncode, result.stdout, result.stderr))
    print('PASS negative control:', name)
