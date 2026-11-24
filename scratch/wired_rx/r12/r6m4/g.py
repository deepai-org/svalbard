import sys, json
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/wired_rx/r12/r6m4')
import capture_r6 as c
tag = sys.argv[1]
K = {'q625': (4, dict(f=625e6, words=12)), 'q625_ss': (4, dict(f=625e6, words=12, corner='ss', temp=32, vdd=3.15)),
     'f480p3': (1, dict(f=480e6, words=8, psel=3))}
b, k = K[tag]
r = c.run_bench(tag, b, ext=True, **k)
print(tag, json.dumps({x: r.get(x) for x in ('words', 'bits', 'bit_errors', 'edge_errors', 'pd_ok', 'pass_', 'error')}), flush=True)
