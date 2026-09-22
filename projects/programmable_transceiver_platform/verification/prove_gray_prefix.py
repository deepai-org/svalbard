"""SAT-check the actual extracted functions for each installed async FIFO width."""
from pathlib import Path
import hashlib,json,re,subprocess
p=Path('/src');out=Path('/out')
old=p/'evidence/experiments/fifo-before-prefix.sv';new=p/'evidence/experiments/fifo-prefix-candidate.sv'
def function(path):
 s=path.read_text();m=re.search(r'function automatic \[A:0\] binary.*?endfunction',s,re.S);assert m
 return m[0]
results=[]
for a in [4,6,7]:
 for corrupt in [False,True]:
  name=f'a{a}-negative{int(corrupt)}';v=out/f'{name}.v'
  v.write_text('\n'.join(f'module {mod}(input [{a}:0] g, output [{a}:0] b); localparam A={a};\n{function(path)}\nassign b=binary(g)'+("^1'b1" if mod=='gate' and corrupt else '')+';\nendmodule' for mod,path in [('gold',old),('gate',new)]))
  cmd=f'read_verilog -sv {v}; proc; opt; miter -equiv -flatten gold gate m; hierarchy -top m; proc; opt; check -assert; sat -verify -prove trigger 0 -show-inputs'
  r=subprocess.run(['yosys','-Q','-T','-p',cmd],capture_output=True,text=True)
  log=r.stdout+r.stderr;(out/f'{name}.log').write_text(log)
  if corrupt:assert r.returncode!=0 and 'proof did fail' in log,log[-1000:]
  else:assert r.returncode==0 and 'SUCCESS' in log,log[-1000:]
  results.append({'A':a,'negative_control':corrupt,'expected_result_verified':True,'log_sha256':hashlib.sha256(log.encode()).hexdigest()})
r={'scope':'Combinational two-state Gray-to-binary equivalence for all input values at installed A=4,6,7; not a CDC/metastability or whole-FIFO proof','cases':results,'source_sha256':{str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [old,new,p/'verification/prove_gray_prefix.py']}}
(out/'proof.json').write_text(json.dumps(r,indent=2)+'\n')
print('GRAY_PREFIX_PROOF_PASS widths=3 negative_controls=3')
