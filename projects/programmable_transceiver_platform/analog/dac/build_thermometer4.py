"""Generate explicit static-CMOS four-bit >=k decoder, k=1..15."""
from pathlib import Path
cells='''* Static CMOS decoder candidate; no retiming or hazard suppression.
.subckt pt_dac_dec_inv A Y VDD VSS
XP Y A VDD VDD pfet_03v3 w=2u l=.28u
XN Y A VSS VSS nfet_03v3 w=1u l=.28u
.ends
.subckt pt_dac_dec_and A B Y VDD VSS
XP0 N A VDD VDD pfet_03v3 w=2u l=.28u
XP1 N B VDD VDD pfet_03v3 w=2u l=.28u
XN0 N A S VSS nfet_03v3 w=2u l=.28u
XN1 S B VSS VSS nfet_03v3 w=2u l=.28u
XI N Y VDD VSS pt_dac_dec_inv
.ends
.subckt pt_dac_dec_or A B Y VDD VSS
XP0 S A VDD VDD pfet_03v3 w=4u l=.28u
XP1 N B S VDD pfet_03v3 w=4u l=.28u
XN0 N A VSS VSS nfet_03v3 w=1u l=.28u
XN1 N B VSS VSS nfet_03v3 w=1u l=.28u
XI N Y VDD VSS pt_dac_dec_inv
.ends
'''
lines=[];cache={}
def ge(n,k):
 if (n,k) in cache:return cache[n,k]
 half=2**(n-1);msb=f'D{n-1}'
 if k==half:return msb
 lower=ge(n-1,k if k<half else k-half)
 node=f'G{n}_{k}';kind='or' if k<half else 'and'
 lines.append(f'X{node} {msb} {lower} {node} VDD VSS pt_dac_dec_{kind}')
 cache[n,k]=node;return node
outputs=[ge(4,k) for k in range(1,16)]
# All threshold outputs get the same two-inverter output stage.
for k,node in enumerate(outputs,1):
 lines.extend([f'XB{k} {node} N{k} VDD VSS pt_dac_dec_inv',f'XO{k} N{k} T{k} VDD VSS pt_dac_dec_inv'])
s=cells+'.subckt pt_dac_thermometer4 D0 D1 D2 D3 '+' '.join(f'T{k}' for k in range(1,16))+' VDD VSS\n'+'\n'.join(lines)+'\n.ends\n'
Path(__file__).with_name('thermometer4.spice').write_text(s)
