import sys, json
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/wired_rx/r12/r6m4')
import capture_r6 as c
tag = sys.argv[1]
K = {'f500_ss': (1, dict(f=500e6, words=8, psel=3, corner='ss', temp=32, vdd=3.15)), 'q625': (4, dict(f=625e6, words=12)), 'q625_ss': (4, dict(f=625e6, words=12, corner='ss', temp=32, vdd=3.15)),
     'f480p3': (1, dict(f=480e6, words=8, psel=3))}
import subprocess
pess = tag.startswith('pess_'); b, k = K[tag.replace('pess_', '')]
if pess:
    from pathlib import Path
    H = Path(c.__file__).resolve().parent; g = H / 'gen_pess'; (g / 'generated').mkdir(parents=True, exist_ok=True)
    subprocess.run(['python3', '/home/ubuntu/svalbard/scratch/wired_rx/r7slicer/pess.py', str(H / 'generated' / 'wrx_cap.ext.spice'), str(g / 'generated' / 'wrx_cap.ext.spice')], check=True)
    c.HERE = g
r = c.run_bench(tag, b, ext=True, **k)
print(tag, json.dumps({x: r.get(x) for x in ('words', 'bits', 'bit_errors', 'edge_errors', 'pd_ok', 'pass_', 'error')}), flush=True)
