# Standard-cell (gf180mcu_fd_sc_mcu7t5v0, 5 V devices) 21-stage ring: how the digital macro's speed moves with
# corner and supply, against the 3.3 V-device pt_ring_osc (obs/bring-up owner 2026-11-20). Schematic cells + 3 fF/node.
M='/foss/pdks/gf180mcuD/libs.tech/ngspice'; C='/foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice'
names=[]
for c in ('tt','ss','ff'):
  for v in (3.15,3.30,3.50):
    n=f'sc_{c}_{v:.2f}'; names.append(n); mc={'tt':'typical'}.get(c,c)
    st='\n'.join(f'X{i} r{i-1} r{i} vdd vdd 0 0 gf180mcu_fd_sc_mcu7t5v0__inv_1\nC{i} r{i} 0 3f' for i in range(1,21))
    open(n+'.spice','w').write(f'''.lib {M}/sm141064.ngspice {mc}
.include {M}/design.ngspice
.include {C}
.temp 27
.option method=gear reltol=1e-3
VDD vdd 0 {v}
VEN en 0 pwl(0 0 2n 0 2.1n {v})
XN r20 en r0 vdd vdd 0 0 gf180mcu_fd_sc_mcu7t5v0__nand2_1
C0 r0 0 3f
{st}
.tran 5p 120n
.measure tran per trig v(r10) val={v/2} td=40n rise=1 targ v(r10) val={v/2} td=40n rise=5
.end
''')
open('run.sh','w').write('for n in '+' '.join(names)+'; do ngspice -b $n.spice > $n.log 2>&1; done\n')
