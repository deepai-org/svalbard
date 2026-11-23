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

# --esd-a[=JSON] (2026-11-20, opt-in; absent = the published cell): pad_wirepad ESD option A. JSON keys: "tb" = layout.py
# usb_term_block overrides (termination block, neck, cleared site band), "site" = pad_site_primary OPT overrides. No
# protection network macro; pad-site primaries at both bond sites; new port DVDD. Flags go after the positional arguments.
ESD_A = None
for _a in [a for a in sys.argv[4:] if a.startswith('--esd-a')]:
    ESD_A = json.loads(_a.split('=', 1)[1]) if '=' in _a else {}
    if set(ESD_A) - {'tb', 'site', 'term_poly', 'trim_poly', 'fs_pad_6v'}: raise ValueError('--esd-a: keys tb / site / term_poly / trim_poly / fs_pad_6v only')
    sys.argv.remove(_a)
family = sys.argv[1]; work = Path(sys.argv[2]); net = Path(sys.argv[3])
# usbfix6v2 (PD28, opt-in): usbfix6v + 16 base 6 V termination switches, shorter base poly and a 4-bit
# binary-weighted 6 V trim bank (TERM_TRIM0..2; 4 bits overflow the 146 um trunk bank), FS fast-off/control sizing for the 6 V high side.
USB6V2 = dict(termination_geometry_um=(16., 1.48, 1), termination_switch_units=10,
              termination_trim=dict(poly=(4., 2.4), switch_w=5., bits=3), term_gate_drive=2.5, fast_off_width_um=16., control_width_um=8.)
# usbfix6v2ls (PD28, opt-in): usbfix6v2 + LS slow-edge mode (wired_receive ls_slow, port LS_SLOW); the v9 nets keep
# their trunk x (RX_P/N 98/97, VSS, ports) and the new nets share free signal tracks (layout.shared_tracks).
if ESD_A and ESD_A.get('term_poly'):   # --esd-a: base termination poly (w, l) um, one segment (re-centred for the block's metal)
    USB6V2['termination_geometry_um'] = (float(ESD_A['term_poly'][0]), float(ESD_A['term_poly'][1]), 1)
if ESD_A and ESD_A.get('trim_poly'):   # --esd-a: trim unit poly (w, l) um of bit 0 (bit k: w x 2^k)
    USB6V2['termination_trim'] = dict(USB6V2['termination_trim'], poly=(float(ESD_A['trim_poly'][0]), float(ESD_A['trim_poly'][1])))
USB_LS = dict(high_a_units=10, low_a_units=3)
# usbfix6v2lsm (PD46 = PD44 laid out, opt-in): usbfix6v2 + Miller-integrated LS edges (wired_receive ls_slow['miller'];
# no A/B split), 1.5 pF MIMs in the strip right of the trunk bank, and 2-finger pairs for the parallel FS / pull-up
# high-side units, bypass and base shunt switches (layout.pair_prefixes) to recover area.
USB_LSM = dict(high_a_units=10, low_a_units=3, miller=dict(c_um=27.4, control_w=16., limit_n=(4., 1.), limit_p=(.8, 1.),
               bypass_n_w=16., bypass_p_w=8., inv_n_w=4., inv_p_w=8., tg_w=4., term_bleed_segments=8))
PAIR_PREFIXES = ('FS_P_SUP_', 'FS_P_PAD_', 'FS_N_SUP_', 'FS_N_PAD_', 'PULLUP_P_SUP_', 'PULLUP_P_PAD_', 'PULLUP_N_SUP_', 'PULLUP_N_PAD_',
                 'BYPASS_', 'TERM_P_', 'TERM_N_', 'FS_P_POWER_', 'FS_N_POWER_')
KEEP_TRACKS = None
if len(sys.argv) > 4 and sys.argv[4] in ('usbfix6v2', 'usbfix6v2ls', 'usbfix6v2lsm'):
    import functools, wired_receive
    _canonical_build = wired_receive.build
    wired_receive.build = functools.partial(_canonical_build, **{**USB_FIX, **USB6V2}, pad_side_6v=True)
    if sys.argv[4] == 'usbfix6v2lsm':
        _v9 = wired_receive.build
        wired_receive.build = functools.partial(_canonical_build, **{**USB_FIX, **USB6V2}, pad_side_6v=True, ls_slow=USB_LSM)
        KEEP_TRACKS = _v9
    if sys.argv[4] == 'usbfix6v2ls':
        _v9 = wired_receive.build
        wired_receive.build = functools.partial(_canonical_build, **{**USB_FIX, **USB6V2}, pad_side_6v=True, ls_slow=USB_LS)
        KEEP_TRACKS = _v9
if len(sys.argv) > 4 and sys.argv[4] in ('usbfix', 'usbfix6v'):
    import functools, wired_receive
    # usbfix6v (PD21, HBM item a): USB fixes + every pad-tracking 3.3 V device on 6 V oxide (wired_receive.pad_side_6v)
    wired_receive.build = functools.partial(wired_receive.build, **USB_FIX, **({'pad_side_6v': True} if sys.argv[4] == 'usbfix6v' else {}))
pdk = PROJECT.parents[1]/'scratch/transceiver-pad-pdk/ngspice'
cfg = json.loads((PROJECT/'spec/schematic-implementation.json').read_text())['io_pad_first_pass']
work.mkdir(parents=True)
params = dict(cfg['generation_parameters'].get(family, {}))
params.update(COMPACT[family]['base'])
if len(sys.argv) > 5 and sys.argv[4] in ('usbfix6v2', 'usbfix6v2ls', 'usbfix6v2lsm'):
    params['fs_high_width_um'] = float(sys.argv[5])   # optional FS high-side unit width override (cfg 14)
if KEEP_TRACKS is not None:
    gp = {k: v for k, v in params.items() if k in ('fs_high_width_um', 'fs_series_geometry_um')}
    params['keep_tracks_of'] = sorted({n for d in KEEP_TRACKS(**gp).devices for n in d.nodes})
if sys.argv[4:5] == ['usbfix6v2lsm']:
    params['pair_prefixes'] = PAIR_PREFIXES
if ESD_A and ESD_A.get('fs_pad_6v'):   # --esd-a b6: the 24 pad-side FS high-side PMOS per leg (FS_x_PAD_i) on 6 V oxide
    # (pfet_06v0, L 0.55 um, same W) - a schematic device change: with the FS high side in the low-R block the 3.3 V pad-side PMOS
    # takes VDD - pad in CDM (5.6 V > 5.0 V); the 6 V device holds. Applied to the circuit before layout (schematic = layout).
    import dataclasses, re as _re, wired_receive as _wr
    _b6_build = _wr.build
    def _fs6(*a, **k):
        c = _b6_build(*a, **k); n = 0
        for i, d in enumerate(c.devices):
            if _re.fullmatch(r'FS_[PN]_PAD_\d+', d.name):
                if d.model != 'pfet_03v3': raise ValueError('fs_pad_6v: ' + d.name)
                c.devices[i] = dataclasses.replace(d, model='pfet_06v0', l_um=.55); n += 1
        if n != 48: raise ValueError(f'fs_pad_6v: {n} devices')
        return c
    _wr.build = _fs6
if ESD_A is not None:
    if family not in ('wired_receive_usb', 'reference_clock'): raise ValueError('--esd-a is for wired_receive_usb / reference_clock')
    params['usb_term_block'] = ESD_A.get('tb', {})
    if family == 'reference_clock':   # (2026-11-22) pad_refpad option A: no termination block, grid height kept (see layout.py term_block)
        if set(ESD_A) - {'tb', 'site'}: raise ValueError('--esd-a reference_clock: keys tb / site only')
        params['usb_term_block'] = dict(dict(term_block=False, height_um=None), **params['usb_term_block'])
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
                side_pins=None if (ESD_A and ESD_A.get('tb', {}).get('top_pins')) else COMPACT[family].get('side_pins'),   # ASM-2: RX pins on the top edge
                **({'esd_a': dict({'neck': [33.5, 41.5], 'vss_strip': [9., 11.]}, **ESD_A.get('site', {}))} if ESD_A is not None else {}))
print(json.dumps(json.loads((work/'pad/layout-screen.json').read_text()), indent=1)[:1500])
