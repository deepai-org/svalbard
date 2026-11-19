# replace the ct_phbuf8 instance of a block GDS by ct_phbuf8y at the same transform (pins of shared nets lie on the
# same tracks, extended); subcells of the new cell get a block prefix.  -rd gds -rd top -rd new -rd out -rd old
import pya
ly = pya.Layout(); ly.read(gds); topc = ly.cell(top)
src = pya.Layout(); src.read(new)
nc = ly.create_cell(top.replace('pt_', '') + '__ct_phbuf8y')
mp = {}
def copy(sc, dc):
    for li in src.layer_indexes():
        info = src.get_info(li); dc.shapes(ly.layer(info)).insert(sc.shapes(li))
    for inst in sc.each_inst():
        ch = inst.cell
        if ch.cell_index() not in mp:
            c2 = ly.create_cell(top.replace('pt_', '') + '__y_' + ch.name); mp[ch.cell_index()] = c2; copy(ch, c2)
        ia = inst.cell_inst.dup(); ia.cell_index = mp[ch.cell_index()].cell_index(); dc.insert(ia)
copy(src.cell('ct_phbuf8y'), nc)
n = 0
for inst in list(topc.each_inst()):
    if inst.cell.name.endswith('__ct_phbuf8'):
        tr = inst.trans; inst.delete(); topc.insert(pya.CellInstArray(nc.cell_index(), tr)); n += 1
assert n == 1, n
ly.cleanup(); ly.write(out); print('swapped', n)
