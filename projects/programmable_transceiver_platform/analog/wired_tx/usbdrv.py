"""pt_usb_txdrv: USB 2.0 transmit pre-driver between the serializer / digital macro and the
pads family's USB pad (`pad_wirepad`, top subckt `tx_protected_pad`).

Why it exists (mode walk MW-18): the USB pad's driver gate pins HS_P/HS_N (14 x nfet_06v0 20/0.7
series switches per leg under the HS_PBIAS current sources) and FS_HIGH_P/N, FS_LOW_P/N (FS/LS
driver controls) had no driver anywhere on the die.

Static CMOS only (nfet_03v3 / pfet_03v3 on VDD_WIRED_SW 3.3 V), every input is a MOS gate, no bias
current.  All six outputs are active high at the pad and are low (pad driver off) whenever the
function is not enabled.

  inputs
    CMD_P, CMD_N  HS serial data, complementary CMOS: pt_wiredtx CMD_MAIN_P / CMD_MAIN_N
                  (x4 bit repetition upstream: 2.083 ns bits).  Load: one 2/2 um NAND input per leg.
    HS_EN         static: HS branch selected (usbdrive.select.branch == hs AND usbhs.config.tx_enable)
    HS_DRV        timed by the digital macro: 1 while an HS packet is on the line (gates CMD_P/N)
    FS_EN         static: FS/LS branch selected (usbdrive.select.branch == fsls AND usbfs.config.drive_enable)
    TX_DP, TX_DN  line levels requested by the digital macro (FS/LS data; HS chirp / calibration)
    TX_OE         output enable for TX_DP/TX_DN
    ISLAND_OFF    1 = wired island off / isolating: all outputs clamped low
    HS_STR1..0    static: strength of the HS gate driver, equivalent inverter 4/8, 6/12, 8/16, 10/20 um for codes
                  0..3 (line edge rate trim against process: slow silicon uses 3, fast silicon 0; reset value 1)
    HS_PBIAS      not an input of the logic: the pad's HS bias node (pt_wtx_hsbias output), bypassed to VDD here
  outputs (pad pins of the same name)
    HS_P  = hs_on AND (CMD_P AND HS_DRV  OR  TX_DP AND TX_OE)     hs_on = HS_EN AND NOT FS_EN AND NOT ISLAND_OFF
    HS_N  = hs_on AND (CMD_N AND HS_DRV  OR  TX_DN AND TX_OE)
    FS_HIGH_x = fs_on AND TX_OE AND TX_Dx        (x = P, N)       fs_on = FS_EN AND NOT HS_EN AND NOT ISLAND_OFF
    FS_LOW_x  = fs_on AND TX_OE AND NOT TX_Dx
      with break-before-make per leg: a driver's gate command can rise only while the opposite gate
      command is low and the opposite pad pin has been low for the off-delay (see usbdrv()).

  line states (FS_EN = 1, TX_OE = 1):  TX_DP TX_DN = 10 -> D+ high / D- low,  01 -> D+ low / D- high,
  00 -> SE0,  11 -> both high (SE1, never requested by a legal controller);  TX_OE = 0 -> high-Z.
  HS_EN = FS_EN = 1 is treated as "nothing selected" (all outputs low).

Usage:  python3 usbdrv.py netlist | layout
"""
import os
import shutil
import sys
from pathlib import Path

import cells as C          # read-only: Cell / Dev classes and gate generators
import tools

N, P = C.N, C.P
HS_OUT_WN = float(os.environ.get('USBD_HS_WN', '4'))     # final HS gate driver, always-on part (sets the line edge rate)
HS_OUT_WP = float(os.environ.get('USBD_HS_WP', '8'))
OFFD_WP = float(os.environ.get('USBD_OFFD_WP', '1'))     # off-delay: weak PMOS W / L and capacitor W (L = 2 um)
OFFD_LP = float(os.environ.get('USBD_OFFD_LP', '3'))
OFFD_CW = float(os.environ.get('USBD_OFFD_CW', '1'))
PB_CAP_N = int(os.environ.get('USBD_PBCAP_N', '30'))    # x 16 um x 10 um PMOS gate: ~0.69 pF each
PB_CAP_L = 10.0

# own subcircuit names: the chip netlist also contains wiredtx.spice / hsbias.spice (wtx_* cells)
INV1 = C.inv('usbd_inv1', 1, 2)
INV2 = C.inv('usbd_inv2', 2, 4)
INV4 = C.inv('usbd_inv4', 4, 8)
INVO = C.inv('usbd_invo', HS_OUT_WN, HS_OUT_WP)
NAND = C.nand2('usbd_nand2', 2, 2)
NAND4 = C.nand2('usbd_nand2x', 4, 4)
NOR = C.nor2('usbd_nor2', 1, 4)


def tinv(name, wn, wp):
    """Tri-state inverter (stacked, enable devices at the rails): one switchable leg of the HS gate driver."""
    c = C.Cell(name, ['A', 'EN', 'ENB', 'Y', 'VDD', 'VSS'])
    c.dev('MPE', P, 'XP', 'ENB', 'VDD', wp)
    c.dev('MPA', P, 'Y', 'A', 'XP', wp)
    c.dev('MNA', N, 'Y', 'A', 'XN', wn)
    c.dev('MNE', N, 'XN', 'EN', 'VSS', wn)
    return c


TINV2 = tinv('usbd_tinv2', 4, 8)       # equivalent to an inverter 2/4
TINV4 = tinv('usbd_tinv4', 8, 16)      # equivalent to an inverter 4/8

PORTS = ['CMD_P', 'CMD_N', 'HS_EN', 'HS_DRV', 'FS_EN', 'TX_DP', 'TX_DN', 'TX_OE', 'ISLAND_OFF', 'HS_STR0', 'HS_STR1', 'HS_PBIAS',
         'HS_P', 'HS_N', 'FS_HIGH_P', 'FS_HIGH_N', 'FS_LOW_P', 'FS_LOW_N', 'VDD', 'VSS']
OUTPUTS = ['HS_P', 'HS_N', 'FS_HIGH_P', 'FS_HIGH_N', 'FS_LOW_P', 'FS_LOW_N']


def nor3(name, wn, wp):
    c = C.Cell(name, ['A', 'B', 'C', 'Y', 'VDD', 'VSS'])
    c.dev('MPA', P, 'X1', 'A', 'VDD', wp)
    c.dev('MPB', P, 'X2', 'B', 'X1', wp)
    c.dev('MPC', P, 'Y', 'C', 'X2', wp)
    for k in 'ABC':
        c.dev(f'MN{k}', N, 'Y', k, 'VSS', wn)
    return c


def offdelay(name='usbd_offd'):
    """Off-delay with pulse stretching for the break-before-make: OUT rises at once when IN exceeds about
    0.9 V (strong NMOS against a long weak PMOS, so even a runt on the driver gate is seen) and falls only
    after the weak PMOS has recharged node X (PMOS gate capacitor to VDD) once IN is low again."""
    c = C.Cell(name, ['IN', 'OUT', 'VDD', 'VSS'])
    c.dev('MN', N, 'X', 'IN', 'VSS', 2)
    c.dev('MP', P, 'X', 'IN', 'VDD', OFFD_WP, OFFD_LP)
    c.dev('MC', P, 'VDD', 'X', 'VDD', OFFD_CW, 2.0)
    c.dev('MNO', N, 'OUT', 'X', 'VSS', 1)
    c.dev('MPO', P, 'OUT', 'X', 'VDD', 2)
    return c


NOR3 = nor3('usbd_nor3', 1, 6)
OFFD = offdelay()


def usbdrv():
    """Item order = placement order (first = bottom row, last = top row next to the port edge): bypass
    capacitors, FS/LS logic, selection logic, then the HS path with the CMD input gates last, so the
    CMD_P/CMD_N port trunks are the shortest."""
    c = C.Cell('pt_usb_txdrv', list(PORTS), row_width=110)
    V = dict(VDD='VDD', VSS='VSS')
    # HS_PBIAS bypass to VDD (PMOS gate capacitors, always inverted: HS_PBIAS is 0-0.6 V or, disabled, VDD).
    # Without it the pad's 28 current-source gates are kicked by 0.35 V at every data transition through
    # their drain-gate capacitance (pt_wtx_hsbias output is ~2 kohm): data-dependent HS amplitude.
    for i in range(PB_CAP_N):
        c.dev(f'CB{i}', P, 'VDD', 'HS_PBIAS', 'VDD', 16, PB_CAP_L)
    for x in ('P', 'N'):
        # FS/LS: requests, break-before-make, buffers.  A driver's gate command G* may rise only while the
        # opposite command (GL/GH, immediate) is low AND the opposite pad pin has been below ~0.9 V for the
        # off-delay (LD/HD: rises with the pin, falls 1-4 ns after it).  Review finding B1 (2026-11-14): the
        # first version looked only at a delayed copy of the opposite pin and could be defeated by input
        # changes 0.8-3 ns apart.
        c.inst(f'FI{x}', INV1, A=f'TX_D{x}', Y=f'DB_{x}', **V)
        c.inst(f'FH{x}', NAND, A=f'TX_D{x}', B='GF', Y=f'RHB_{x}', **V)
        c.inst(f'FL{x}', NAND, A=f'DB_{x}', B='GF', Y=f'RLB_{x}', **V)
        c.inst(f'NH{x}', NOR3, A=f'RHB_{x}', B=f'GL_{x}', C=f'LD_{x}', Y=f'GH_{x}', **V)
        c.inst(f'NL{x}', NOR3, A=f'RLB_{x}', B=f'GH_{x}', C=f'HD_{x}', Y=f'GL_{x}', **V)
        for s, g in (('HIGH', 'GH'), ('LOW', 'GL')):
            c.inst(f'B{s[0]}1{x}', INV1, A=f'{g}_{x}', Y=f'{g}B_{x}', **V)
            c.inst(f'B{s[0]}2{x}', INV4, A=f'{g}B_{x}', Y=f'FS_{s}_{x}', **V)
            c.inst(f'D{s[0]}{x}', OFFD, IN=f'FS_{s}_{x}', OUT=f'{s[0]}D_{x}', **V)
    for o in OUTPUTS:                                                # island-off clamps (as pt_wiredtx CMD_*)
        c.dev(f'CL_{o}', N, o, 'ISLAND_OFF', 'VSS', 2)
    # branch selection (mutually exclusive, both off when ISLAND_OFF)
    c.inst('SA', NOR, A='FS_EN', B='ISLAND_OFF', Y='NFS', **V)       # not FS and island on
    c.inst('SB', NOR, A='HS_EN', B='ISLAND_OFF', Y='NHS', **V)
    c.inst('SH', NAND, A='HS_EN', B='NFS', Y='HS_ONB', **V)
    c.inst('SF', NAND, A='FS_EN', B='NHS', Y='FS_ONB', **V)
    c.inst('ID', INV1, A='HS_DRV', Y='DRVB', **V)
    c.inst('IO', INV1, A='TX_OE', Y='OEB', **V)
    c.inst('GS', NOR, A='HS_ONB', B='OEB', Y='GS', **V)              # hs_on & TX_OE
    c.inst('GF', NOR, A='FS_ONB', B='OEB', Y='GF', **V)              # fs_on & TX_OE
    for k in (0, 1):                                                 # HS gate-driver strength select (static)
        c.inst(f'S{k}I', INV1, A=f'HS_STR{k}', Y=f'STRB{k}', **V)
        c.inst(f'S{k}O', INV1, A=f'STRB{k}', Y=f'STR{k}', **V)
    c.inst('GD', NOR, A='HS_ONB', B='DRVB', Y='GDN', **V)            # hs_on & HS_DRV
    c.inst('GDI', INV1, A='GDN', Y='GDB', **V)
    c.inst('GDO', INV2, A='GDB', Y='GD', **V)
    for x in ('P', 'N'):
        # HS: serial path and static path, OR, two inverters, strength legs
        c.inst(f'HF{x}', TINV4, A=f'HI_{x}', EN='STR1', ENB='STRB1', Y=f'HS_{x}', **V)
        c.inst(f'HE{x}', TINV2, A=f'HI_{x}', EN='STR0', ENB='STRB0', Y=f'HS_{x}', **V)
        c.inst(f'HD{x}', INVO, A=f'HI_{x}', Y=f'HS_{x}', **V)
        c.inst(f'HI{x}', INV4, A=f'HO_{x}', Y=f'HI_{x}', **V)
        c.inst(f'HB{x}', NAND, A=f'TX_D{x}', B='GS', Y=f'HB_{x}', **V)
        c.inst(f'HO{x}', NAND4, A=f'HA_{x}', B=f'HB_{x}', Y=f'HO_{x}', **V)
    for x in ('P', 'N'):
        c.inst(f'HA{x}', NAND, A=f'CMD_{x}', B='GD', Y=f'HA_{x}', **V)
    return c


CELL = usbdrv()
SPICE = tools.HERE / 'usbdrv.spice'
GEN = tools.GENERATED
LAY = tools.SCRATCH / 'usbdrv' / 'layout'
HEAD = ('* pt_usb_txdrv: USB 2.0 TX pre-driver (HS switch gates, FS/LS driver gates with break-before-make)\n'
        '* Generated by usbdrv.py. GF180 gf180mcuD 3.3 V MOS only.\n')


def write_netlist(path=SPICE):
    Path(path).write_text(HEAD + C.netlist(CELL))
    return path


def lvs_reference(dst, summary):
    """Schematic + the layout generator's antenna diodes (same rule as run_all.with_antenna_diodes)."""
    sys.path.insert(0, str(tools.HERE.parent))
    import antenna_diodes as ad
    text = HEAD + C.netlist(CELL)
    lines = ad.spice_lines(summary.get('antenna_diodes', []))
    if lines:
        k = text.index(f'.subckt {CELL.name} ')
        e = text.index('\n', text.index('.ends', k))
        flat = [f'.subckt {CELL.name} {" ".join(CELL.ports)}']
        for d in C.layout_devices(CELL):
            flat.append(d.spice().replace(f'X{d.name}', 'X' + d.name.replace('/', '__'), 1))
        flat += lines + [f'.ends {CELL.name}']
        text = text[:k] + '\n'.join(flat) + text[e:]
    Path(dst).write_text(text)


def layout(row_width=110.0, publish=True):
    import layoutgen
    write_netlist()
    if LAY.exists():
        shutil.rmtree(LAY)
    s = layoutgen.generate(LAY, cell=CELL, row_width=row_width)
    lvs_reference(LAY / 'usbdrv.spice', s)
    lvs = tools.netgen_lvs(LAY, 'pt_usb_txdrv_lvs.spice', 'pt_usb_txdrv', 'usbdrv.spice')
    g = tools.gds_export_analog(LAY, 'pt_usb_txdrv')
    kl = tools.klayout_drc(LAY, g, 'pt_usb_txdrv')
    gate = dict(magic_drc=s['drc_count'] == 0, lvs=bool(lvs['unique_match']),
                klayout=bool(kl.get('ran')) and kl.get('violations', 1) == 0)
    res = dict(published=False, gate=gate, layout=s, lvs=lvs, klayout=kl,
               gds_export='analog image Magic 8.3.678, cif ostyle gdsii',
               magic_drc_lvs_extract_image=tools.DIGITAL_IMAGE)
    if publish and all(gate.values()):
        shutil.copy(g, GEN / 'usbdrv.gds')
        sys.path.insert(0, str(tools.HERE.parent))
        from gds_uniquify import publish_checked
        res['klayout_precheck'] = publish_checked(GEN / 'usbdrv.gds', 'usbdrv', 'pt_usb_txdrv')
        md = GEN / 'mag_usbdrv'
        if md.exists():
            shutil.rmtree(md)
        md.mkdir()
        for m in LAY.glob('pt_usb_txdrv*.mag'):
            shutil.copy(m, md / m.name)
        shutil.copy(LAY / 'pt_usb_txdrv_pex.spice', GEN / 'usbdrv.ext.spice')
        shutil.copy(LAY / 'pt_usb_txdrv_lvs.spice', GEN / 'usbdrv.lvs.spice')
        shutil.copy(LAY / 'lvs.out', GEN / 'usbdrv-lvs.txt')
        (GEN / 'usbdrv-drc.txt').write_text(f"magic drc(full) flat error count: {s['drc_count']}\n"
                                            + (LAY / 'drc-why.txt').read_text())
        res['published'] = True
    tools.write_json(GEN / 'usbdrv-layout.json', res)
    return res


if __name__ == '__main__':
    import json
    what = sys.argv[1] if len(sys.argv) > 1 else 'netlist'
    if what == 'netlist':
        print(write_netlist(sys.argv[2] if len(sys.argv) > 2 else SPICE), len(CELL.flat_devices()), 'devices')
    else:
        print(json.dumps(layout(float(sys.argv[2]) if len(sys.argv) > 2 else 110.0), indent=1)[:3000])
