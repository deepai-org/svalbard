"""Ensure the independent bit queue rejects bit corruption and ignored stalls."""
from pathlib import Path
import subprocess
source,unpack=Path('/src/rtl/pt_pack.sv').read_text().split('module pt_unpack',1)
for name,old,new,message in [
 ('flip_bit','assign word=bits[9:0]','assign word=bits[9:0]^10\'d1','bit order'),
 ('ignore_stall','if(word_valid&&word_ready)','if(word_valid)','stalled output changed')]:
 assert source.count(old)==1
 path=Path(f'/out/{name}.sv');path.write_text(source.replace(old,new)+'module pt_unpack'+unpack)
 subprocess.run(['iverilog','-g2012','-s','tb_pack_stream','-o',f'/out/{name}',str(path),'/src/sim/tb_pack_stream.sv'],check=True)
 result=subprocess.run(['vvp',f'/out/{name}'],capture_output=True,text=True)
 Path(f'/out/{name}.log').write_text(result.stdout+result.stderr)
 assert result.returncode!=0 and message in result.stdout,(name,result)
 print(f'PACK_NEGATIVE_CONTROL_PASS {name}')
