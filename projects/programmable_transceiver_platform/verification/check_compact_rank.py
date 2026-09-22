import pathlib,subprocess
out=pathlib.Path('/out');rtl=pathlib.Path('/src/rtl/pt_lane_compact_rank.sv')
def prove(path,name):
 s=f'read_verilog -sv /src/rtl/pt_lane_compact.sv {path} /src/verification/compact_rank_miter.sv; prep -top compact_rank_miter -flatten; opt; sat -verify -prove mismatch 0 -show-inputs'
 r=subprocess.run(['yosys','-Q','-T','-p',s],capture_output=True,text=True)
 (out/(name+'.log')).write_text(r.stdout+r.stderr);return r
r=prove(rtl,'proof');assert r.returncode==0 and 'SUCCESS' in r.stdout
s=rtl.read_text();assert s.count('selected[src]&&')==1
(out/'bad.sv').write_text(s.replace('selected[src]&&',''))
r=prove(out/'bad.sv','negative');assert r.returncode!=0 and 'proof did fail' in r.stdout+r.stderr
print('PASS all-input compactor equivalence; omitted selection qualification rejected')
