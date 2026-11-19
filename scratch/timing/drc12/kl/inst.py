import pya
for g,tc in (('pll_ring','pt_pll_ring'),('pll_ring_core','pt_pll_ring_core')):
    ly=pya.Layout(); ly.read(f'/repo/projects/programmable_transceiver_platform/analog/timing/generated/{g}.gds'); top=ly.cell(tc)
    print(g, top.dbbox())
    for i in top.each_inst():
        n=i.cell.name
        if 'ct_' in n or 'ft' in n: print('  ',n, i.dbbox(), i.dtrans)
