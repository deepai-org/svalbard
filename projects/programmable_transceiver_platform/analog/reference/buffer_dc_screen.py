"""Bidirectional DC drive screen; no real voltage/current reference implementation."""
import hashlib,json,subprocess
from pathlib import Path

def main(variant='scaled'):
 if variant not in ('scaled','complement'):raise ValueError('Unknown reference buffer variant')
 O=Path('/work');rows=[]
 for target in (1.15,2.15):
  for scale in (1,4,16):
   for direction in (1,-1):
    name=f'v{target:g}_s{scale}_d{direction}'
    d=f'''* Reference buffer static source/sink capacity candidate
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/reference/buffer_{variant}.spice
.temp 27
VDD VDD 0 3.3
VT TARGET 0 {target}
IBN VDD BN 20u
IBP BP 0 20u
XBN BN BN 0 0 nfet_03v3 w=8u l=.5u
XBP BP BP VDD VDD pfet_03v3 w=8u l=.5u
XBUF TARGET OUT BN BP VDD 0 pt_reference_buffer_{variant} S={scale}
ILOAD OUT 0 0
CLOAD OUT 0 10p
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
dc ILOAD {-20*direction}m {20*direction}m {.5*direction}m
wrdata /work/{name}.dat v(OUT) i(VDD) v(XBUF.X) v(XBUF.T)
.endc
.end
'''
    (O/(name+'.spice')).write_text(d)
    with (O/(name+'.log')).open('w') as log:r=subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,timeout=120)
    rows.append(dict(name=name,target_v=target,scale=scale,direction=direction,returncode=r.returncode,artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log') if (O/(name+s)).exists()}))
    print(name,r.returncode,flush=True)
 source=Path(f'/screen/reference/buffer_{variant}.spice')
 (O/'result.json').write_text(json.dumps(dict(status='reference_drive_DC_unverified',cases=rows,source_sha256={str(source):hashlib.sha256(source.read_bytes()).hexdigest()},limitations=['External ideal target and 20uA bias sources remain; this is a driver candidate only.', 'DC currents do not represent switched-CDAC transient drive or stability.', 'FET typical, 3.3V, 27C; no mismatch/noise/startup/parasitics.']),indent=2)+'\n')

if __name__=='__main__':main()
