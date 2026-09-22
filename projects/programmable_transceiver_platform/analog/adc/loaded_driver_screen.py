"""Reduced loaded acquisition: actual driver, always-on sampler and static PDK CDAC."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files=[Path(__file__)]+[Path('/screen/adc')/s for s in ('sample_driver_headroom.spice','cdac8_scaled.spice','cdac8_mim.spice')]+[Path('/wifi/rf_if_transmission_gate/rf_if_transmission_gate.spice')]
files+=list(Path('/foss/pdks/gf180mcuD/libs.tech/ngspice').rglob('*.ngspice'))+list(Path('/foss/pdks/gf180mcuD/libs.tech/ngspice').rglob('*.spice'))
before={str(p):sha(p) for p in files}
bits=' '.join(['0 VDD']*7+['VDD 0'])
d=f'''* Reduction only: no SAR logic, comparator, Q channel or physical reference driver
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical
.include /screen/adc/sample_driver_headroom.spice
.include /screen/adc/cdac8_scaled.spice
.include /screen/adc/cdac8_mim.spice
.include /wifi/rf_if_transmission_gate/rf_if_transmission_gate.spice
.temp 27
VDD VDD 0 3.3
VIP SP 0 PWL(0n 1.27 60n 1.27 60.1n .87 80n .87 80.1n 1.27)
VIN SN 0 PWL(0n .87 60n .87 60.1n 1.27 80n 1.27 80.1n .87)
RIP SP GP 1k
RIN SN GN 1k
IBN VDD BN 20u
IBP BP 0 20u
XBN BN BN 0 0 nfet_03v3 w=8u l=.5u
XBP BP BP VDD VDD pfet_03v3 w=8u l=.5u
XBPDRV GP IP BN BP VDD 0 pt_sample_driver_headroom CC=.5p
XBNDRV GN IN BN BP VDD 0 pt_sample_driver_headroom CC=.5p
XS IP IN HP HN VDD 0 VDD 0 wifi_if_transmission_gate
VH VH 0 2.15
VL VL 0 1.15
XD HP HN VH VL {bits} VDD 0 pt_cdac8_mim
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
tran 5p 100n 0 5p
wrdata /work/loaded.dat v(SP) v(SN) v(GP) v(GN) v(IP) v(IN) v(HP) v(HN) v(xd.xp7.bot) v(xd.xn7.bot) i(VDD)
.endc
.end
'''
p=O/'loaded.spice';p.write_text(d);h=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,deck_sha256_before=h,requested_horizon_ns=100,scope='Reduced diagnostic: static code128, always-on actual sampler, actual PDK CDAC; ideal references and source drive; no comparator/control/Q channel.'),indent=2)+'\n')
with (O/'loaded.log').open('w') as log:
 try:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=300);code=r.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={str(p):sha(p) for p in files};assert before==after and sha(p)==h
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={e:sha(O/('loaded'+e)) for e in ('.spice','.log','.dat') if (O/('loaded'+e)).exists()}),indent=2)+'\n')
print(code,timeout)
