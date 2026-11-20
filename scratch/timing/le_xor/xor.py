import pya
a=pya.Layout(); a.read(f1); b=pya.Layout(); b.read(f2)
ta=a.top_cell(); tb=b.top_cell(); n=0
for li in a.layer_indexes():
    info=a.get_info(li); lb=b.find_layer(info)
    ra=pya.Region(ta.begin_shapes_rec(li)); rb=pya.Region(tb.begin_shapes_rec(lb)) if lb is not None else pya.Region()
    x=(ra^rb); n+=x.count()
    if x.count(): print(info, x.count())
for li in b.layer_indexes():
    if a.find_layer(b.get_info(li)) is None: print('only in b', b.get_info(li)); n+=1
print('XOR shapes', n)
