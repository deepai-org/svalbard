"""Reject a one-slot-early full flag using the independent FIFO scoreboard."""
from pathlib import Path
import subprocess
s=Path('/src/rtl/pt_fifo.sv').read_text()
old='full<=count==((1<<A)-1)';assert s.count(old)==1
path=Path('/out/early_full.sv');path.write_text(s.replace(old,'full<=count==((1<<A)-2)'))
subprocess.run(['iverilog','-g2012','-s','tb_sync_fifo_flags','-o','/out/early_full',str(path),'/src/sim/tb_sync_fifo_flags.sv'],check=True)
r=subprocess.run(['vvp','/out/early_full'],capture_output=True,text=True)
Path('/out/early_full.log').write_text(r.stdout+r.stderr)
assert r.returncode!=0 and 'FIFO state' in r.stdout,r
print('FIFO_FLAGS_NEGATIVE_CONTROL_PASS early_full')
