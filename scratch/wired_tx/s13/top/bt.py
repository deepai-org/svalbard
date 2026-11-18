import sys, json, re
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_tx')
import pt_wiredtx8_layout as P, wtx_mux8_layout as L
from collections import Counter
r = P.build()
if P.T.DECAP['n'] != r['decap']['fingers']: P.set_decap(r['decap']['fingers'])
w = P.WORK / 'build'
c = L.check(w, P.NAME, P.reference())
print(r['size_um'], r['seam_um'], r['tracks'], r['buffer_cell_um'], json.dumps(c)[:200])
d = (w / 'drc-details.txt').read_text()
ms = re.findall(r'\{([^{}]*?[A-Za-z][^{}]*?)\} \{((?:\{[-\d ]+\} ?)+)\}', d)
for m, boxes in ms[:14]:
    b = re.findall(r'\{(-?\d+) (-?\d+) (-?\d+) (-?\d+)\}', boxes)
    print(len(b), m[:70], [tuple(round(int(v) / 200, 1) for v in x) for x in b[:3]])
lv = (w / f'{P.NAME}-lvs.txt').read_text()
print([l[:120] for l in lv.splitlines() if 'Number of' in l][-4:])
i = lv.rfind('NET mismatches'); print(lv[i:i + 2500] if i > 0 else lv[-1500:])
