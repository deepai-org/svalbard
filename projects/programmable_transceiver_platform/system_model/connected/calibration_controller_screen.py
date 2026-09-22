import json
from pathlib import Path
from chip_model import P
from calibration_trim import OffsetTrimPlant,calibrate_reversed
from calibration_controller import TimedCalibration

rows=[]
for offset in (-.2,-.03,0,.07,.2,.3):
 for chunks in (1,173):
  p=OffsetTrimPlant(offset,comparator_offset_v=.002)
  c=TimedCalibration(p.write,p.above);g=c.start(0,epoch=2,quiet=True,code=p.code,spacing=225e-9,tolerance=.001)
  end=25.01*225e-9
  for i in range(chunks):c.advance(end*(i+1)/chunks,epoch=2,quiet=True)
  assert c.state=='observe' and len(c.history)==24
  expected=calibrate_reversed(OffsetTrimPlant(offset,comparator_offset_v=.002),0)
  assert c.code==expected['code']
  residual=p.apply(end,0.)
  c.observe(end,generation=g,epoch=2,quiet=True,value=residual,error_bound=20e-6)
  assert c.valid==(abs(offset)<.25)
  rows.append(dict(offset=offset,chunks=chunks,code=c.code,result=c.result))
c.advance(end+1e-6,epoch=3,quiet=True);assert not c.valid and c.state=='cancelled'
# Lose ownership midway: rollback once, no later scheduled comparator activity.
p=OffsetTrimPlant(.07);c=TimedCalibration(p.write,p.above)
g=c.start(0,epoch=1,quiet=True,code=p.code,spacing=1e-6,tolerance=.001)
c.advance(4e-6,epoch=1,quiet=True);count=len(c.history)
c.advance(4.5e-6,epoch=2,quiet=True)
assert c.state=='cancelled' and p.code==2048 and not c.valid
c.advance(50e-6,epoch=2,quiet=True);assert len(c.history)==count
try:c.observe(50e-6,generation=g,epoch=1,quiet=True,value=0,error_bound=0)
except ValueError:pass
else:raise AssertionError('Stale observation accepted')
g2=c.start(50e-6,epoch=2,quiet=True,code=p.code,spacing=1e-6,tolerance=.001)
assert g2!=g
try:c.start(51e-6,epoch=2,quiet=True,code=p.code,spacing=1e-6,tolerance=.001)
except ValueError:pass
else:raise AssertionError('Busy target stolen')
c.advance(51e-6,epoch=2,quiet=False);assert c.state=='cancelled'
(P/'evidence/connected-calibration-controller.json').write_text(json.dumps(dict(status='passed',cases=rows,controls=['epoch cancellation','rollback','no post-abort comparisons','stale observation','busy rejection','quiet loss']),indent=2)+'\n')
print('Passed timed search, subdivision, rollback and stale observation checks')
