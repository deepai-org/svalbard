#!/usr/bin/env python3
"""Provider IO cell supply current at the safety corner, per cell: input pad at 0 / VDD / floating mid-rail.
gf180mcu_fd_io__bi_24t as strapped in integration/pt_provider_io.sv for SPI/H2D inputs (OE=0 IE=1 PU=PD=0),
bi_t as strapped for D2H/MISO (OE=0), in_c for RESET_N (PD=1), plus the dvdd/dvss/cor supply cells."""
import re, sys
PDK = '/foss/pdks/gf180mcuD'
io = open('/m/sim/fd_io.spice').read()
io = re.sub(r'\n\+\s*', ' ', io)
def refinger(m):
    mult, w, l, nf = float(m.group(1)), float(m.group(2)), m.group(3), float(m.group(4))
    k = nf
    while w/k > 50e-6: k *= 2
    return f'm={mult*k:g} w={w/k:g} l={l} nf=1'
io = re.sub(r'm=(\S+) w=(\S+) l=(\S+) nf=(\S+)', refinger, io)
io = re.sub(r' (as|ad|ps|pd|nrd|nrs|sa|sb|sd)=\S+', '', io)
corner, temp, vdd = sys.argv[1], sys.argv[2], float(sys.argv[3])
m = f'{PDK}/libs.tech/ngspice/sm141064.ngspice'
hdr = [f'.include {PDK}/libs.tech/ngspice/design.ngspice', f'.lib {m} {corner}', f'.lib {m} res_{corner}', f'.lib {m} mimcap_{corner}',
       f'.lib {m} diode_{corner}', f'.lib {m} moscap_{corner}', f'.temp {temp}', '.option gmin=1e-15 rshunt=1e13', io]
cases = {
 'bi24_in_pad0': 'Xc 0 0 VDD 0 VDD 0 pad 0 0 0 VDD 0 y gf180mcu_fd_io__bi_24t\nVp pad 0 0',
 'bi24_in_padhi': f'Xc 0 0 VDD 0 VDD 0 pad 0 0 0 VDD 0 y gf180mcu_fd_io__bi_24t\nVp pad 0 {vdd}',
 'bi24_in_padmid': f'Xc 0 0 VDD 0 VDD 0 pad 0 0 0 VDD 0 y gf180mcu_fd_io__bi_24t\nVp pad 0 {vdd/2}',
 'bi24_obs_hiz': 'Xc 0 0 VDD 0 0 0 pad 0 0 0 VDD 0 y gf180mcu_fd_io__bi_24t\nRp pad 0 1e9',
 'bit_out_hiz': 'Xc 0 0 VDD 0 0 0 pad 0 0 VDD 0 0 VDD 0 y gf180mcu_fd_io__bi_t\nRp pad 0 1e9',
 'inc_reset_pad0': 'Xc VDD 0 pad VDD 0 VDD 0 y gf180mcu_fd_io__in_c\nVp pad 0 0',
 'inc_reset_padhi': f'Xc VDD 0 pad VDD 0 VDD 0 y gf180mcu_fd_io__in_c\nVp pad 0 {vdd}',
 'dvdd': 'Xc VDD 0 0 gf180mcu_fd_io__dvdd', 'dvss': 'Xc VDD 0 VDD gf180mcu_fd_io__dvss', 'cor': 'Xc VDD 0 VDD 0 gf180mcu_fd_io__cor',
}
for n, body in cases.items():
    open(f'/m/leak/io_{n}_{corner}_{temp}_{vdd}.sp', 'w').write('\n'.join([f'* {n}']+hdr+[f'Vdd VDD 0 {vdd}', body, 'Cy y 0 10f', 'Ry y 0 1e12',
        '.control', 'op', 'print -i(Vdd)', '.endc', '.end'])+'\n')
