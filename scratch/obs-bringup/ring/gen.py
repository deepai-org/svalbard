# Ring-oscillator / aosc speed table for the supply-trim procedure (obs/bring-up owner, 2026-11-20).
# Extracted netlists copied from analog/timing/generated; decks follow analog/timing/timing_flow.header().
M='/foss/pdks/gf180mcuD/libs.tech/ngspice'
def hdr(c,t):
    mc={'tt':'typical'}.get(c,c); r={'ss':'res_ss','ff':'res_ff'}.get(c,'res_typical')
    d={'ss':'diode_ss','ff':'diode_ff'}.get(c,'diode_typical')
    return f'.lib {M}/sm141064.ngspice {mc}\n.lib {M}/sm141064.ngspice {r}\n.lib {M}/sm141064.ngspice {d}\n.include {M}/design.ngspice\n.temp {t}\n.option method=gear reltol=1e-3\n'
names=[]
for c in ('tt','ss','ff','sf','fs'):
  for v in (3.15,3.30,3.50):
    n=f'ro_{c}_{v:.2f}'; names.append(n)
    open(n+'.spice','w').write(hdr(c,27)+f'''.include ring_osc.ext.spice
VDD vdd 0 {v}
VEN en 0 pwl(0 0 2n 0 2.1n {v})
X1 en out vdd 0 pt_ring_osc
CL out 0 20f
.tran 2p 50n
.measure tran per trig v(out) val={v/2} td=15n rise=1 targ v(out) val={v/2} td=15n rise=5
.measure tran ion avg i(VDD) from=15n to=50n
.end
''')
for c in ('tt','ss','ff'):
  for v in (3.15,3.50):
    n=f'ao_{c}_{v:.2f}'; names.append(n)
    open(n+'.spice','w').write(hdr(c,27)+f'''.include aosc.ext.spice
VDD vdd 0 {v}
VEN en 0 pwl(0 0 2n 0 2.1n {v})
X1 en clk x vdd 0 pt_aosc
CL clk 0 20f
.tran 10p 300n
.measure tran per trig v(clk) val={v/2} td=100n rise=1 targ v(clk) val={v/2} td=100n rise=7
.end
''')
open('run.sh','w').write('for n in '+' '.join(names)+'; do ngspice -b $n.spice > $n.log 2>&1; done\n')
