"""Physical binding of the provider pad ring and the digital macro's control ports (KH-1..KH-3, 2026-11-26).

One source for assembly (`assembly/common.py`, `kl_place.py`, `kl_stream.py`) and the LVS reference (`signoff/lvs/gen_netlist.py`):

macro_ctl(inst)        adds every control port of ctl_ports.txt (c_*, bit-expanded) to the `digital` instance as an output on
                       the net of the same name ('-' where no consumer on this chip). The conn does not repeat them ("every
                       c_* net is a macro output port of the same name"), so without this no c_* net has a driver end.
sites(inst, bondrows)  one record per bond site whose conn instance is a provider-ring instance (host, debug_pads,
                       pad_por_bypass, atb*_io, supply pads): the provider cell at the site and every core pin's net,
                       ties included ('VDD' / 'VSS'); 'NC' = left open by the model.

The ties are transcribed from integration/pt_provider_io.sv (the model; keep in step): inputs (pt_provider_input, bi_24t):
A = OE = SL = 0, IE = 1, CS / PU / PD per pad; outputs (pt_provider_output, bi_t = layout cell selected_host_output):
CS = IE = PU = PD = 0, A / OE / PDRV / SL from the macro except SPI_MISO (PDRV = 2'b10, SL = 0); observation pads
(pt_debug_physical, bi_24t): A / OE from the macro, CS = SL = IE = PU = PD = 0; RESET_N (in_c): PU = 0, PD = 1;
POR_BYPASS (pad_strap, in_c): PU / PD as the conn binds them (PU~VSS PD~VDD).
"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
BI24, BIT, INC, ASIG = 'gf180mcu_fd_io__bi_24t', 'selected_host_output', 'gf180mcu_fd_io__in_c', 'gf180mcu_fd_io__asig_5p0'
DVDD_C, DVSS_C = 'gf180mcu_fd_io__dvdd', 'gf180mcu_fd_io__dvss'
# pins of each provider cell = its top-cell labels (what the layout extraction names)
CELL_PINS = {BI24: 'A CS DVDD DVSS IE OE PAD PD PU SL VDD VSS Y'.split(),
             BIT: 'A CS DVDD DVSS IE OE PAD PD PDRV0 PDRV1 PU SL VDD VSS Y'.split(),
             INC: 'DVDD DVSS PAD PD PU VDD VSS Y'.split(),
             ASIG: 'ASIG5V DVDD DVSS VDD VSS'.split(),
             DVDD_C: 'DVDD DVSS VSS'.split(), DVSS_C: 'DVDD DVSS VDD'.split()}
RAIL = {'DVDD': 'VDD', 'VDD': 'VDD', 'DVSS': 'VSS', 'VSS': 'VSS'}
CORE = {c: [p for p in ps if p not in RAIL and p not in ('PAD', 'ASIG5V')] for c, ps in CELL_PINS.items()}   # core-side pins
PROVIDER = ('pt_host_physical', 'pt_debug_physical', 'atb_provider_pad', 'pad_strap', 'prov_supply', 'prov_supply_sig')
B = lambda x: 'VDD' if x else 'VSS'


def ctl_bits():
    out = []
    for line in open(HERE+'/ctl_ports.txt'):
        if not line.strip() or line.startswith('#'): continue
        c = [x.strip() for x in line.split('|')]
        w = int(c[1]); out += [c[0]] if w == 1 else [f'{c[0]}[{k}]' for k in range(w)]
    return out


def macro_ctl(inst):
    """add the c_* output ports to inst['digital'] (in place); -> number added"""
    if 'digital' not in inst: return 0
    used = {n for nm, i in inst.items() if nm != 'digital' for k, n in i['pins'].values()}
    d = inst['digital']['pins']; k0 = len(d)
    for p in ctl_bits():
        if p not in d: d[p] = ('>', p if p in used else '-')
    return len(d)-k0


def sites(inst, bondrows):
    """-> [dict(site, name, inst, cell, pins={cell pin: net | 'VDD' | 'VSS' | 'NC'})] for every provider-ring bond site"""
    def net(i, p):
        k = inst.get(i, {}).get('pins', {}).get(p)
        return 'NC' if k is None or k[1] == '-' else k[1]
    out = []
    for site, side, bnet, i in bondrows:
        if i not in inst or inst[i]['master'] not in PROVIDER: continue
        m = inst[i]['master']; pins = None
        def inp(y, cs=0, pu=0, pd=0):
            return BI24, dict(Y=y, A='VSS', OE='VSS', SL='VSS', IE='VDD', CS=B(cs), PU=B(pu), PD=B(pd))
        if m == 'pt_host_physical':
            k = re.fullmatch(r'(H2D|D2H)\[(\d+)\]', bnet)
            if bnet == 'RESET_N': cell, pins = INC, dict(Y=net(i, 'rst_n'), PU='VSS', PD='VDD')
            elif bnet == 'SPI_SCLK': cell, pins = inp(net(i, 'sclk'), cs=1, pd=1)
            elif bnet == 'SPI_CS_N': cell, pins = inp(net(i, 'cs_n'), cs=1, pu=1)
            elif bnet == 'SPI_MOSI': cell, pins = inp(net(i, 'mosi'), cs=1, pd=1)
            elif bnet == 'H2D_CLK': cell, pins = inp(net(i, 'h2d_clk'), pd=1)
            elif k and k.group(1) == 'H2D': cell, pins = inp(net(i, f'h2d_pin[{k.group(2)}]'), pd=1)
            elif bnet == 'SPI_MISO':
                cell, pins = BIT, dict(A=net(i, 'miso'), OE=net(i, 'miso_oe'), PDRV0='VSS', PDRV1='VDD', SL='VSS')
            elif bnet == 'D2H_CLK' or (k and k.group(1) == 'D2H'):
                a = net(i, 'd2h_clk_pin') if bnet == 'D2H_CLK' else net(i, f'd2h_pin[{k.group(2)}]')
                cell, pins = BIT, dict(A=a, OE=net(i, 'd2h_oe'), PDRV0=net(i, 'd2h_pdrv[0]'), PDRV1=net(i, 'd2h_pdrv[1]'), SL=net(i, 'd2h_sl'))
            else: raise ValueError(f'host bond net {bnet} at {site}: not in the provider model')
            if cell == BIT: pins.update(CS='VSS', IE='VSS', PU='VSS', PD='VSS', Y='NC')
        elif m == 'pt_debug_physical':
            p = {'CLK_OBS': 'clk_obs', 'DBG_OBS0': 'dbg_obs0', 'DBG_OBS1': 'dbg_obs1'}[bnet]
            cell, pins = BI24, dict(A=net(i, p), OE=net(i, p+'_oe'), CS='VSS', SL='VSS', IE='VSS', PU='VSS', PD='VSS', Y='NC')
        elif m == 'pad_strap':
            cell, pins = INC, dict(Y=net(i, 'Y'), PU=net(i, 'PU'), PD=net(i, 'PD'))
        elif m == 'atb_provider_pad':
            cell, pins = ASIG, {}
            if net(i, 'ASIG5V') not in ('NC', bnet): raise ValueError(f'{i}.ASIG5V on {net(i, "ASIG5V")}, bond net {bnet}')
        else:
            cell, pins = (DVDD_C if bnet == 'VDD' else DVSS_C), {}
        for p in CELL_PINS[cell]:
            if p in RAIL: pins[p] = RAIL[p]
            elif p in ('PAD', 'ASIG5V'): pins[p] = bnet
        assert set(pins) == set(CELL_PINS[cell]), (site, cell, sorted(set(CELL_PINS[cell]) ^ set(pins)))
        out.append(dict(site=site, name='io_'+site.replace('[', '_').replace('].pad', '').replace('.pad', ''), inst=i, cell=cell, pins=pins))
    return out
