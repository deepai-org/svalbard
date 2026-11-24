import sys,ast,statistics as st
P=1/2.4e9
for l in open(sys.argv[1]):
    if not l.startswith(sys.argv[2]): continue
    c,m,e=ast.literal_eval(l.split(' ',1)[1])
    try:
        qi=[((m[f'rq{k}']-m[f'ri{k}'])%P)/P*360 for k in range(1,9)]
        du=[((m[f'fi{k}']-m[f'ri{k}'])%P)/P for k in range(1,9)]
        print(c,'QI %.1f +-%.1f'%(st.mean(qi),st.pstdev(qi)),'duty %.3f'%st.mean(du),'idd %.1f'%(-1e3*m['idd']))
    except Exception as ex: print(c,'FAIL',ex)
