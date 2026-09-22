import pathlib,subprocess
out=pathlib.Path('/out');src=pathlib.Path('/src')
a=src/'rtl/pt_block_route_rank.sv'
def prove(rank,name):
 script=f'read_verilog -sv /src/rtl/pt_lane_compact.sv /src/rtl/pt_block_route_mask.sv {rank} /src/verification/route_rank_miter.sv; prep -top route_rank_miter -flatten; opt; sat -verify -prove mismatch 0 -show-inputs'
 r=subprocess.run(['yosys','-Q','-T','-p',script],text=True,capture_output=True)
 (out/(name+'.log')).write_text(r.stdout+r.stderr);return r
r=prove(a,'proof');assert r.returncode==0 and 'SUCCESS' in r.stdout
s=a.read_text();assert s.count('left_wire>prefix')==1
(out/'bad.sv').write_text(s.replace('left_wire>prefix','left_wire>=prefix'))
r=prove(out/'bad.sv','negative');assert r.returncode!=0 and 'proof did fail' in r.stderr+r.stdout
print('PASS all-input combinational equivalence; rank-boundary mutation rejected')
