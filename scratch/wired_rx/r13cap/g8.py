"""r8 capture gating cases (quarter / half rate) on the r13cap build. g8.py TAG"""
import sys, json, subprocess
from pathlib import Path
W = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx'); sys.path.insert(0, str(W))
import capture as c
S = Path(__file__).resolve().parent
c.FAST = S / 'fast'; c.SCRATCH = S / 'cap'; c.GEN = S / 'gen'
K = {'f500_ss': (1, dict(f=500e6, words=8, psel=3, corner='ss', temp=32, vdd=3.15)), 'q625_ss': (4, dict(f=625e6, words=12, corner='ss', temp=32, vdd=3.15)), 'q625': (4, dict(f=625e6, words=12)),
     'q625_ff': (4, dict(f=625e6, words=12, corner='ff', temp=22, vdd=3.35, d_lat=0.327e-9)),
     'h625_ss': (2, dict(f=625e6, words=12, corner='ss', temp=32, vdd=3.15))}
tag = sys.argv[1]; pess = tag.startswith('pess_'); b, k = K[tag.replace('pess_', '')]
if pess:
    g = S / 'gen_pess'; g.mkdir(exist_ok=True)
    subprocess.run(['python3', '/home/ubuntu/svalbard/scratch/wired_rx/r7slicer/pess.py', str(S / 'gen' / 'wrx_cap.ext.spice'), str(g / 'wrx_cap.ext.spice')], check=True)
    c.GEN = g
r = c.run_bench(tag, b, ext=True, **k)
out = {x: r.get(x) for x in ('words', 'bits', 'bit_errors', 'edge_errors', 'pd_ok', 'gear_ok', 'strobe_word_errors', 'word_timing', 'pass_', 'error')}
res = S / 'results.json'; R = json.loads(res.read_text()) if res.exists() else {}; R[tag] = out; res.write_text(json.dumps(R, indent=1, default=str))
print(tag, json.dumps(out), flush=True)
