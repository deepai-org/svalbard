#!/usr/bin/env python3
"""Schematic LNA gain/noise scenario screen, not RF model qualification."""
import hashlib,json,math,re,subprocess
from pathlib import Path
import numpy as np
SRC=Path('/src'); OUT=Path('/work'); PDK=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
template=(SRC/'lna_noise_tb.spice.in').read_text(); core=SRC/'lna_cs_core.spice'
subckt=re.search(r'^\.subckt\s+(\S+)',core.read_text(),re.M|re.I)[1]
rows=[]
for corner in ('typical','ff','ss'):
 for flicker in (0,1):
  name=f'{corner}_f{flicker}'
  values=dict(MOS_CORNER=corner,DUT_INCLUDE=str(core),DUT_SUBCKT=subckt,TEMP_C='27',VDD_V='3.3',VBIAS_V='1.5',AC_DATA=str(OUT/(name+'_ac.dat')),NOISE_DATA=str(OUT/(name+'_noise.dat')))
  text=template
  for k,v in values.items():text=text.replace('@'+k+'@',v)
  text=text.replace('.temp 27',f'.param fnoicor={flicker}\n.temp 27')
  text=text.replace('op\n','op\nprint i(VDD)\n')
  assert not re.search(r'@[A-Z0-9_]+@',text)
  path=OUT/(name+'.spice');path.write_text(text)
  with (OUT/(name+'.log')).open('w') as log:
   subprocess.run(['ngspice','-b',str(path)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
  ac=np.loadtxt(OUT/(name+'_ac.dat'),skiprows=1); noise=np.loadtxt(OUT/(name+'_noise.dat'),skiprows=1)
  assert ac.shape[1]==3 and noise.shape[1]==3 and np.isfinite(ac).all() and np.isfinite(noise).all()
  gain=float(np.interp(2.4e9,ac[:,0],np.abs(ac[:,1]+1j*ac[:,2])))
  out=float(np.interp(2.4e9,noise[:,0],noise[:,1])); ino=float(np.interp(2.4e9,noise[:,0],noise[:,2]))
  ref=math.sqrt(4*1.380649e-23*300.15*50)
  factor=(out/(gain*ref))**2
  # Check against ngspice's independently input-referred noise output.
  assert abs(out/gain/ino-1)<.005
  logtext=(OUT/(name+'.log')).read_text()
  current=-float(re.search(r'i\(vdd\)\s*=\s*([-+\d.eE]+)',logtext,re.I)[1])
  rows.append(dict(corner=corner,flicker_corner=flicker,gain_v_per_v=gain,gain_db=20*math.log10(gain),input_noise_v_per_sqrt_hz=ino,bench_relative_noise_figure_db=10*math.log10(factor),supply_current_a=current,deck_sha256=sha(path)))
r=dict(status='schematic_lna_noise_scenarios_not_receiver_qualification',frequency_hz=2.4e9,vdd_v=3.3,temperature_c=27,bias_v=1.5,
 cases=rows,source_sha256=dict(core=sha(core),template=sha(SRC/'lna_noise_tb.spice.in'),runner=sha(Path(__file__)),models=sha(PDK/'sm141064.ngspice'),design=sha(PDK/'design.ngspice')),
 limitations=['Standalone single-ended LNA, not the actual dual-mixer loaded IQ chain.',
 'External ideal bias, 300-ohm drain load, 82-ohm degeneration, 50-ohm source, 20pF coupling and 5kohm output load.',
 'No PEX, selected RF ESD/package/matching, substrate coupling, mismatch or periodically mixed noise.',
 'Finite model prediction is not a bound on actual RF noise. No receiver sensitivity or EVM claim.'])
(OUT/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,indent=2))
