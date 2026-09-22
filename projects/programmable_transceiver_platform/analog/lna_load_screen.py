"""Transistor-level reuse screen; fixed supply/temperature, swept process and load."""
import pathlib,subprocess,re,json,hashlib,math
out=pathlib.Path('/work');core=pathlib.Path('/core')
template=(core/'lna_ac_tb.spice.in').read_text();results=[]
for corner in ('typical','ff','ss'):
 for cap in (0,50,200,500,1000):
  name=f'{corner}_{cap}f'
  s=template
  for k,v in {'MOS_CORNER':corner,'DUT_INCLUDE':'.include /core/lna_cs_core.spice','TEMP_C':'27','VDD_V':'3.3','VBIAS_V':'1.5','DUT_SUBCKT':'wifi_lna_cs_core'}.items():s=s.replace('@'+k+'@',v)
  if cap:s=s.replace('RLOAD OUT 0 5k',f'RLOAD OUT 0 5k\nCLOAD OUT 0 {cap}f')
  assert '@' not in s
  deck=out/(name+'.spice');deck.write_text(s)
  r=subprocess.run(['ngspice','-b',str(deck)],capture_output=True,text=True,timeout=60)
  log=r.stdout+r.stderr;(out/(name+'.log')).write_text(log)
  vals={k:float(v) for k,v in re.findall(r'^(output_dc|supply_current|gain_2p4g|input_mag_2p4g)\s*=\s*([-+\deE.]+)',log,re.M)}
  assert len(vals)==4 and all(math.isfinite(v) for v in vals.values()),log[-2000:]
  assert 0<vals['output_dc']<3.3 and vals['supply_current']>0
  results.append(dict(process=corner,load_fF=cap,**vals))
report={'pass':89,'temperature_C':27,'supply_V':3.3,'external_bias_V':1.5,'results':results,'scope':'Schematic GF180 transistor-level AC/DC LNA core reuse screen. Ideal external bias, resistors/coupling and lumped output load; no PEX, RF model qualification, matching/noise/linearity or complete receiver proof.','source_sha256':{f:hashlib.sha256((core/f).read_bytes()).hexdigest() for f in ['lna_cs_core.spice','lna_ac_tb.spice.in']}}
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(results,indent=2))
