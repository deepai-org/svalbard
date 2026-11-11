"""Compact (area-recovery) variant of the stress-safe wired/reference families (I8, 2026-11-10).

Usage: stress_safe_compact_layout.py <family> <empty work dir> <drop-in network dir> [usbfix]

Same circuit, same devices and sizes, same drop-in network macro (network + gate
discharge + ATB tap + v2 shunt, unchanged) as stress_safe_wired_layout.py. Only
placement and the connecting wires change:
  * the network macro sits directly behind the bond rows (y 440, as in the RF pair)
    instead of above the attachment column, so the family depth or footprint shrinks;
  * the network ground joins the base VSS trunk at the bond end (no M5/M4 detour
    over the column top);
  * reference_clock only: its 16-device bias array is refolded to 3 columns in the
    strip left of the network, and every port (PAD_P/N, VCM, VSS) is drawn up to the
    cell's inner edge (boundary pins, PAD trunks 4 um wide).
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from design import PROJECT
from layout import generate as base_layout
from wired_protection_layout_ss import generate as connect_primary

NETWORK_Y = 440.        # network origin; its top lands at 440 + 472.91 = 912.91 (RF-pair depth)
BOND_Y_OFFSETS = (14., 6.)   # base P/N bond transverses at 426 / 434 (clear of the network's M4 port stubs at 438)
ROUTE_Y = [396., 406.]       # protection P/N transverses (were 400 / 412)
GROUND_LOW = 415.            # network ground row (between the protection rows and the base ground landing at 420)
COMPACT = {
    'reference_clock': dict(origin=[80., NETWORK_Y], base=dict(columns=3, port_top_um=NETWORK_Y+472.91-0.72,  # trunk top (span+0.72) = network top
                                                              trunk_width_overrides_um={'PAD_P': 4., 'PAD_N': 4.})),
    'wired_transmit': dict(origin=[160., NETWORK_Y], base={}),
    'wired_receive_usb': dict(origin=[200., NETWORK_Y], base={}, side_pins=[
        # RX_P/RX_N side pins (I8): Metal3 from the port trunks (x 98 / 97, bottom 437.28) to the cell's
        # x = 2.78 edge, in the free Metal3 band y 437.3..440.02 just above the PAD_N bond transverse
        # (M4, top 437.0) and below the array's first M3/M4 rows (440.8). Neither strip runs under the
        # PAD transverses, so the added P/N cross-coupling stays small. RX_N widens its existing M3-M5
        # stack pad at (97, 439.8); RX_P gets a new M3-M5 stack on its trunk at (98, 437.7).
        dict(net='RX_P', rects=[(3, 2.78, 437.4, 98.22, 438.4)], stacks=[(98., 437.7, 3, 5)], label=(4.78, 437.9, 3)),
        dict(net='RX_N', rects=[(3, 2.78, 438.8, 97.22, 440.02)], stacks=[], label=(4.78, 439.4, 3))]),
}
USB_FIX = dict(termination_geometry_um=(16., 1.3, 1), high_side_fast_off=True, hs_mirror_reference=False)

family = sys.argv[1]; work = Path(sys.argv[2]); net = Path(sys.argv[3])
# usbfix6v2 (PD28, opt-in): usbfix6v + 16 base 6 V termination switches, shorter base poly and a 4-bit
# binary-weighted 6 V trim bank (TERM_TRIM0..2; 4 bits overflow the 146 um trunk bank), FS fast-off/control sizing for the 6 V high side.
USB6V2 = dict(termination_geometry_um=(16., 1.48, 1), termination_switch_units=10,
              termination_trim=dict(poly=(4., 2.4), switch_w=5., bits=3), term_gate_drive=2.5, fast_off_width_um=16., control_width_um=8.)
if len(sys.argv) > 4 and sys.argv[4] == 'usbfix6v2':
    import functools, wired_receive
    wired_receive.build = functools.partial(wired_receive.build, **{**USB_FIX, **USB6V2}, pad_side_6v=True)
if len(sys.argv) > 4 and sys.argv[4] in ('usbfix', 'usbfix6v'):
    import functools, wired_receive
    # usbfix6v (PD21, HBM item a): USB fixes + every pad-tracking 3.3 V device on 6 V oxide (wired_receive.pad_side_6v)
    wired_receive.build = functools.partial(wired_receive.build, **USB_FIX, **({'pad_side_6v': True} if sys.argv[4] == 'usbfix6v' else {}))
pdk = PROJECT.parents[1]/'scratch/transceiver-pad-pdk/ngspice'
cfg = json.loads((PROJECT/'spec/schematic-implementation.json').read_text())['io_pad_first_pass']
work.mkdir(parents=True)
params = dict(cfg['generation_parameters'].get(family, {}))
params.update(COMPACT[family]['base'])
if len(sys.argv) > 5 and sys.argv[4] == 'usbfix6v2':
    params['fs_high_width_um'] = float(sys.argv[5])   # optional FS high-side unit width override (cfg 14)
base_layout(work/'base', family, external_primary=True, bond_y_offsets_um=BOND_Y_OFFSETS, **params)
base = work/'base'
if family == 'wired_receive_usb':
    from extract_audit import export_extracted
    from receive_pad_layout import generate as attach_discharge
    import shutil
    export_extracted(base/'pad_wired_receive_usb_flat.ext', base/'physical.spice', capacitance=True)
    inputs = work/'discharge-inputs'; inputs.mkdir()
    for s, n in [('pad_wired_receive_usb_flat.gds', 'wired-receive-usb.gds'), ('layout-report.json', 'wired-receive-usb-layout.json'),
                 ('physical.spice', 'wired-receive-usb-extracted-c.spice')]:
        shutil.copyfile(base/s, inputs/n)
    attach_discharge(work/'discharge', inputs, PROJECT/'analog/pads/generated/receiver-core-discharge')
    staged = work/'primary-inputs'; staged.mkdir()
    for s, n in [('combined.gds', 'rx_pad_with_discharge.gds'), ('layout-report.json', 'layout-report.json'),
                 ('physical.spice', 'pad_wired_receive_usb.spice')]:
        shutil.copyfile(work/'discharge'/s, staged/n)
    base = staged
connect_primary(work/'pad', base, net, COMPACT[family]['origin'], pdk, route_y_um=ROUTE_Y, ground_low_um=GROUND_LOW,
                side_pins=COMPACT[family].get('side_pins'))
print(json.dumps(json.loads((work/'pad/layout-screen.json').read_text()), indent=1)[:1500])
