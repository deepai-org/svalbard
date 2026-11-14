#!/usr/bin/env python3
"""M3a deck generator: two extracted pt_pll_ring (open loop, VCTRL fixed) in one deck.
mode: free   = separate ideal supplies (null control: must show no pulling)
      direct = separate ideal supplies + resistor Rc between phase nodes A0 and B0 (strong: must lock; weak: Adler scaling)
      strong = both rings on ONE node fed through Rs from an ideal source, no decap (negative control: must lock)
      reg    = extracted pt_pll_vreg2, regulated (BYP=0), VIN ideal
      regz   = same, VIN through the island-rail impedance (Rr, Cr)
      (the shared gate is held at its 7 mA-per-output steady state, 3.1213 V, through the cell's own 20 kohm ATB_G leaf: a plain .ic was
       not honoured after source stepping and left VOUT at 2.06 V; the gate is still free above ~80 kHz, so ring-to-ring gate coupling is kept)
      byp    = extracted pt_pll_vreg2, BYP=1 (the 810 MHz mode), VIN through the rail impedance
usage: mk.py name mode vA vB T [Rs|Rr] [Cr]"""
import sys
name,mode,vA,vB,T=sys.argv[1],sys.argv[2],float(sys.argv[3]),float(sys.argv[4]),sys.argv[5]
R=float(sys.argv[6]) if len(sys.argv)>6 else 1.0
Cr=sys.argv[7] if len(sys.argv)>7 else '50p'
d=f"* M3a {name} {mode}\n.include /w/hdr.inc\n.include /w/pll_ring.ext.spice\n"
def ring(tag,vdd,vct):
    s=f"VEN{tag} en{tag} 0 pwl(0 0 2n 0 2.1n 3.3)\nIB{tag} {vdd} ib{tag} 10u\nVCT{tag} vc{tag} 0 {vct}\n"
    sub, xp = ('pt_pll_ring_x', f' xa0{tag}') if mode=='direct' else ('pt_pll_ring', '')
    s+=f"XR{tag} 0 en{tag} 0 0 0 ib{tag} "+' '.join(f'p{tag}{k}' for k in range(8))+f" lock{tag} fbck{tag} refo{tag} vc{tag} 0 0"+' 0'*11+f" {vdd} {vdd} 0{xp} {sub}\n"
    s+=''.join(f'CP{tag}{k} p{tag}{k} 0 20f\n' for k in range(8))+f'CRO{tag} refo{tag} 0 20f\n'
    return s
if mode=='free':
    d+="VSA VT 0 2.9027\nVSB VC 0 2.9027\n"
elif mode=='direct':      # separate ideal supplies, ring output node O4 (= XPHB/I0, a node of the oscillation loop; XRING/A0 was tried first and is not in the loop) of A tied to that of B through Rc (negative control: must lock when Rc is small)
    d+=f".include /w/pll_ring_x.inc\nVSA VT 0 2.9027\nVSB VC 0 2.9027\nRC xa0a xa0b {R}\n"
elif mode=='strong':
    d+=f"VS VS0 0 {2.9027+0.014*R}\nRS VS0 VT {R}\nVSH VT VC 0\n"
else:
    d+=".include /w/pt_pll_vreg2.ext.spice\n"
    byp=3.3 if mode=='byp' else 0
    if mode=='reg': d+="VIN VIN 0 3.25\n"
    else: d+=f"VIN VIN0 0 {3.25+0.014*R}\nRR VIN0 VIN {R}\nCR VIN 0 {Cr}\n"
    d+=f"VB BYP 0 {byp}\nXD VIN VT VC 0 BYP BYP AO AG pt_pll_vreg2\nRAO AO 0 1g\nVAG AG 0 3.1213\n"
d+=ring('a','VT',vA)+ring('b','VC',vB)
d+=f".option method=gear reltol=1e-3\n.tran 2p {T}\n.control\nset wr_singlescale\nrun\nwrdata /w/{name}.txt v(pa0) v(pb0) v(VT) v(VC)\n.endc\n.end\n"
open(name+'.cir','w').write(d)
