from pathlib import Path
import json
from stream_codec import encode,slots
out=Path('/out');cycles=0;frames=0
with (out/'stream-tx-vectors.txt').open('w') as f:
    for mode in (0,1):
        plan=slots(mode);wquota=plan.count('wire');qquota=plan.count('iq')
        f.write(f'{mode:x} 1 0 0 0 0 0 0 0 0 0\n')
        priorw=[];priorq=[];priorop=priorarg=0;wi=qi=0
        counts=[(w,q) for w in range(wquota+1) for q in range(qquota+1)]+[(80,63),(0,0),(0,0)]
        for frame,(wc,qc) in enumerate(counts):
            op=frame%3;arg=0 if op==0 else frame%2
            expected=encode(mode,priorw,priorq,frame%64,priorop,priorarg)
            nextw=[];nextq=[]
            for pos,owner in enumerate(plan):
                wp=int(owner=='wire' and len(nextw)<min(wc,wquota))
                qp=int(owner=='iq' and len(nextq)<min(qc,qquota))
                wd=(wi*37+15)%1024;qd=(qi*53+713)%1024
                # Change live command inputs after the snapshot edge; only the
                # frame-boundary value may accompany the captured payload.
                drive_op,drive_arg=(op,arg) if pos==0 else ((op+1)%3,0)
                # Counts also change immediately after word zero: a delayed
                # quota calculation must use the original snapshot.
                drive_wc,drive_qc=(wc,qc) if pos==0 else (127-wc,63-qc)
                row=(mode,0,drive_wc,drive_qc,wd,qd,drive_op,drive_arg,wp,qp,expected[pos])
                f.write(' '.join(f'{v:x}' for v in row)+'\n');cycles+=1
                if wp:nextw.append(wd);wi+=1
                if qp:nextq.append(qd);qi+=1
            priorw,priorq,priorop,priorarg=nextw,nextq,op,arg;frames+=1
(out/'stream-tx-vectors.json').write_text(json.dumps({'frames':frames,'word_cycles':cycles,'profiles':2,'legal_count_pairs':1308,'additional_frames':6},indent=2)+'\n')
print(f'Generated {frames} TX frames / {cycles} word cycles')
