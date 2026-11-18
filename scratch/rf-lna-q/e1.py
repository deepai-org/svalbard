"""E1: reproduce the committed-tree baseline common-mode failure, extracted and schematic (extpr ff 32C 3.35V, lowr spiral)."""
import sys, time; sys.path.insert(0, '/home/ubuntu/svalbard/scratch/rf-lna-q')
from var import *
t0 = time.time()
r = LM.stability(Q / 'w' / 'e1_ext', 'extpr', FF, deg='lowr'); print('ext base', fmt(r), '%.0fs' % (time.time() - t0), flush=True)
W = variant('e1_sch'); t0 = time.time()
r = LM.stability(W, 'selftest', FF, deg='lowr'); print('sch base', fmt(r), '%.0fs' % (time.time() - t0), flush=True)
