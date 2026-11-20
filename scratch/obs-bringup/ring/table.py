# Speed-indicator table: frequency and freq-counter codes per corner/supply (27 C), from the logs here and ../scring.
import re,glob,json
def per(f,k):
    m=re.search(r'^per\s*=\s*([-0-9.e+]+)',open(f).read(),re.M); return k/float(m.group(1)) if m else None
T={}
for f in glob.glob('ro_*.log'): _,c,v=f[:-4].split('_'); T.setdefault('ring_osc',{})[f'{c}@{v}']=round(per(f,4)/1e6,1)
for f in glob.glob('ao_*.log'): _,c,v=f[:-4].split('_'); T.setdefault('aosc',{})[f'{c}@{v}']=round(per(f,6)/1e6,1)
for f in glob.glob('../scring/sc_*.log'): _,c,v=f.split('/')[-1][:-4].split('_'); T.setdefault('stdcell_ring_mcu7t5v0',{})[f'{c}@{v}']=round(per(f,4)/1e6,1)
for ref in (25e6,50e6):
  T[f'fca_count_window1024_ref{int(ref/1e6)}MHz_ring_osc']={k:round(v*1e6/ref*1024) for k,v in T['ring_osc'].items()}
json.dump(T,open('speed_table.json','w'),indent=1,sort_keys=True); print(json.dumps(T,indent=1,sort_keys=True))
