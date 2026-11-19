import pya
ly=pya.Layout(); ly.read('/repo/projects/programmable_transceiver_platform/analog/wired_rx/generated/slicer.gds'); top=ly.cell('pt_slicer')
bb=pya.DBox(21.3,7.1,91.5,36.1).to_itype(ly.dbu)
r=pya.Region(top.begin_shapes_rec_touching(ly.layer(30,0),bb))&pya.Region(bb)
for p in list(r.merged().each())[:40]: print(p.bbox().to_dtype(ly.dbu))
free=pya.Region(bb)-r.sized(int(1/ly.dbu))
print('free area frac', free.area()/pya.Region(bb).area(), 'largest', max((q.bbox().width()*q.bbox().height() for q in free.merged().each()),default=0)*ly.dbu**2)
