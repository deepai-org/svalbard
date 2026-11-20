"""mini bench: every element touching the detector phase copies XE0..7 (devices with any terminal on them, caps, R),
taken from one block netlist; all other nodes kept as-is (held by rshunt); ideal 8-phase sources on PH k (2.69 V, 390.6 MHz).
usage: mini.py <netlist> <out.sp> [drop-regex]   (drop-regex removes matching element lines: bisection)"""
import re, sys
src, out = sys.argv[1], sys.argv[2]; drop = re.compile(sys.argv[3]) if len(sys.argv) > 3 else None
L = open(src).read().replace('\n+', ' ').split('\n')
full = '/' not in open(src).read()[:200000]
def base(n): return re.sub(r'(\.(t|n)\d+|#.*)$', '', n).replace('/', '.')
pat = re.compile(r'^XMUX\.XE\d$')
keep = []
for l in L:
    p = l.split()
    if not p or p[0][0] not in 'XRC' or l.startswith('.'): continue
    k = 4 if p[0][0] == 'X' and 'fet' in l else (3 if p[0][0] == 'X' else 2)
    if any(pat.match(base(n)) for n in p[1:1 + k]):
        if drop and drop.search(l): continue
        keep.append(l.replace('/', '__'))
ph = {}
for l in keep:
    for n in l.split()[1:5]:
        if re.match(r'^PH\d', n): ph[n] = 1
T = 1 / 390.6e6; tr = 60e-12
hdr = open('/home/ubuntu/svalbard/scratch/wired_tx/s14/det/hdr.sp').read()
o = [hdr, 'VDD VDD 0 3.15', 'VSS VSS 0 0'] + (['RVDM VDD VDD#mux 0.01', 'RVSM VSS VSS#mux 0.01'] if not full else []) + keep
for k in range(8):
    o.append(f'VP{k} PHS{k} 0 PULSE(0 2.69 {1e-9 + k * T / 8:.6e} {tr} {tr} {T / 2 - tr:.6e} {T:.6e})')
for n in ph:   # all PH nodes of this netlist (PH0, PH0#m, PH0.t4 ...) tied to the source through 0.1 ohm
    k = re.match(r'PH(\d)', n).group(1); o.append(f'RPH_{n.replace("#","_").replace(".","_")} PHS{k} {n.replace("/","__")} 0.1')
o += ['.options reltol=1e-3 method=gear rshunt=1e10', '.tran 1e-11 12e-9 0 4e-12', '.control', 'run',
      'wrdata wave.txt ' + ' '.join(f'v({("XMUX.XE" if full else "XMUX__XE") + str(k)})' for k in range(8)), '.endc', '.end']
open(out, 'w').write('\n'.join(o) + '\n')
print(out, len(keep), 'elements, PH nodes', sorted(ph))
