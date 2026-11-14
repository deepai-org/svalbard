# hier_area.py <netlist.v> [depth]: cell area and flop count by hierarchy prefix (flattened names a.b.c)
import re,sys,collections
lib=open('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/verification/digital_hardening/liberty/gf180mcu_fd_sc_mcu7t5v0__ss_032C_3v15.lib').read()
area={m.group(1):float(m.group(2)) for m in re.finditer(r'cell\s*\(\s*"?(\w+)"?\s*\)\s*\{[^}]*?area\s*:\s*([\d.]+)',lib)}
depth=int(sys.argv[2]) if len(sys.argv)>2 else 2
A=collections.Counter();F=collections.Counter();N=collections.Counter()
for m in re.finditer(r'^\s*(gf180mcu_fd_sc_mcu7t5v0__\w+)\s+\\?(\S+)\s*\(',open(sys.argv[1]).read(),re.M):
    c,n=m.groups(); parts=re.split(r'\.',re.sub(r'\[[^\]]*\]','',n))
    k='.'.join(parts[:depth]) if len(parts)>depth else '.'.join(parts[:-1]) or '(top)'
    A[k]+=area.get(c,0);N[k]+=1
    if '__dff' in c: F[k]+=1
tot=sum(A.values())
for k,v in A.most_common(45): print(f"{k:42s} {v/1e6:.4f} mm2 {100*v/tot:5.1f}%  cells {N[k]:6d} ff {F[k]:5d}")
print('total',tot/1e6,'ff',sum(F.values()))
