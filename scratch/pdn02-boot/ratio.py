import json,statistics as st
from pathlib import Path
cells=['dffrnq_2','mux2_2','aoi21_2','buf_4','nand2_2','clkbuf_8']
def r(num,den):
    out={}
    for c in cells:
        b=json.load(open(f'cache/{num}/{c}.json')); a=json.load(open(f'cache/{den}/{c}.json')); rs=[]
        for aid,arc in b['arcs'].items():
            if arc.get('kind')!='delay' or 'res' not in arc or aid not in a['arcs']: continue
            for k,v in arc['res'].items():
                u=a['arcs'][aid]['res'].get(k)
                if u and u[0]>1e-3: rs.append(v[0]/u[0])
        rs.sort(); out[c]=(st.median(rs),rs[9*len(rs)//10])
    return out
for num,den in [('ss_032C_2v84','ss_032C_3v15'),('ss_032C_3v00','ss_032C_3v15'),('ss_032C_3v19','ss_032C_3v50'),('ss_032C_3v35','ss_032C_3v50'),('ss_032C_3v50','ss_032C_3v15')]:
    o=r(num,den); print(num,'/',den,' '.join('%s %.3f/%.3f'%(c,m,p) for c,(m,p) in o.items()),' max-median %.3f max-p90 %.3f'%(max(m for m,p in o.values()),max(p for m,p in o.values())))
