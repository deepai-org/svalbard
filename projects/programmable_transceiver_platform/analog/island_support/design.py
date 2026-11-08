"""Island power-switch and analog-test-bus (ATB) switch cells: sizing and netlists.

Single source for the island table, the parametric sizes and the transistor
netlists used by schematic simulation, layout generation and LVS. All devices
are GF180MCU 3.3 V core devices (nfet_03v3 / pfet_03v3); the ring is 3.0-3.6 V.

Island current allocations are read from spec/analog-architecture.json
(per-block resource_allocation.current_budget_ma grouped by block "supply"),
not restated here. Sizing is a design rule applied to those allocations.
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCH_CANDIDATES = [HERE.parent.parent / 'spec' / 'analog-architecture.json',
                   Path('/spec/analog-architecture.json')]

# Island membership. Domains come from analog-architecture.json block "supply".
# Core (aosc, digital, monitor, bias) and host (hostio, usbfs) are never switched
# (tapeout-readiness.json power.safe_mechanism), so usbfs stays on the host
# domain and the USB island holds only the wire-domain USB blocks.
USB_BLOCKS = ('usbhs', 'usbdrive')
NEVER_SWITCHED = ('core', 'host', 'external')
CORE_IN_PLL_DOMAIN = ('bias',)          # master bias is a core block

# Consolidation pass 2 (P2-8): no separate USB island. USB drive lives in the
# wired pad/wiredtx and the USB-mode peak fits the wired switch, so the wired
# island holds every wire-domain block. A DEBUG island lets a broken debug
# buffer be cut off its functional node. The register file has a 'debug' enable.
ISLANDS = {
    'wired': {'domain': 'wire', 'exclude': ()},
    'rf': {'domain': 'rf', 'exclude': ()},
    'pll': {'domain': 'pll', 'exclude': CORE_IN_PLL_DOMAIN},
    'conv': {'domain': 'conv', 'exclude': ()},
    'debug': {'domain': 'debug', 'estimate': True},
}

# DEBUG island current, mA while observing. Only bb_tap is characterized
# (analog/rf_rx/README.md: 1.01 mA supply current observing, extracted). The
# rest are planning estimates, not simulated: pad-driving CMOS clock outputs at
# CV*f (~5 pF, 3.3 V, <=200 MHz), CML-class differential receivers, and an
# analog buffer like bb_tap. The off-state averages in analog/timing/README.md
# are standby, not active, currents.
DEBUG_ESTIMATE_MA = {
    'bb_tap x2': (2 * 1.01, 'analog/rf_rx/README.md extracted 1.01 mA each'),
    'wmon': (2.0, 'estimate: bandwidth-limited analog monitor buffer driving a pad, bb_tap-class'),
    'clk_obs x2': (2 * 3.0, 'estimate: CMOS pad driver, ~5 pF x 3.3 V x 200 MHz'),
    'aux_clk/wclk_in/wtx_ext receivers x3': (3 * 4.0, 'estimate: differential pad receiver, CML class'),
    'ring_osc': (1.0, 'estimate: 211 MHz monitor ring (analog/timing/README.md frequency)'),
    'vco_replica': (5.0, 'estimate: VCO replica core + /16 divider'),
}

# Sizing rule (design choice, recorded in evidence):
DESIGN_MARGIN = 1.25          # design current = allocation x margin, rounded up to 5 mA
# The die-rail window is 3.15-3.35 V (spec/tapeout-plan.md "Operating envelope").
# Island rails must stay inside it, so the switch drop is charged against the
# PDN allocation: 20 mV at design current at the worst functional check point
# (ss, 32 C, 3.15 V).
DROP_TARGET_V = 0.020          # total, checked on the full-RC extracted layout
DEVICE_DROP_TARGET_V = 0.012   # sizing target for the pass device; 8 mV left for the metal grid
RON_W_WORST_OHM_UM = None     # filled from the characterization run; see sizing()
FINGER_W_UM = 10.0
PASS_L_UM = 0.28
FINGERS_PER_ROW = 100

ISLAND_DECAP_F = {'wired': 150e-12, 'rf': 200e-12, 'pll': 250e-12,
                  'conv': 250e-12, 'debug': 100e-12}   # conv = 150 pF + 100 pF reference reservoir; debug assumed


def architecture():
    for p in ARCH_CANDIDATES:
        if p.exists():
            return json.loads(p.read_text()), p
    raise FileNotFoundError('analog-architecture.json not found')


def island_allocations():
    arch, path = architecture()
    out = {}
    for name, rule in ISLANDS.items():
        if rule.get('estimate'):
            peak = round(sum(v for v, _ in DEBUG_ESTIMATE_MA.values()), 3)
            out[name] = {'domain': 'debug (new switched island)', 'blocks': list(DEBUG_ESTIMATE_MA),
                         'estimate_sources': {k: s_ for k, (_, s_) in DEBUG_ESTIMATE_MA.items()},
                         'mode_current_ma': {'debug_observing': peak}, 'peak_allocation_ma': peak,
                         'design_current_ma': 5 * math.ceil(peak * DESIGN_MARGIN / 5),
                         'island_decap_f': ISLAND_DECAP_F[name]}
            continue
        modes = {}
        members = []
        for blk, spec in sorted(arch['blocks'].items()):
            if spec.get('supply') != rule['domain']:
                continue
            if 'only' in rule and blk not in rule['only']:
                continue
            if blk in rule.get('exclude', ()):
                continue
            members.append(blk)
            for mode, ma in spec.get('resource_allocation', {}).get('current_budget_ma', {}).items():
                modes[mode] = round(modes.get(mode, 0.0) + ma, 4)
        peak = max(modes.values())
        design = 5 * math.ceil(peak * DESIGN_MARGIN / 5)
        out[name] = {'domain': rule['domain'], 'blocks': members, 'mode_current_ma': modes,
                     'peak_allocation_ma': round(peak, 3), 'design_current_ma': design,
                     'island_decap_f': ISLAND_DECAP_F[name]}
    return out, str(path)


def pass_fingers(design_ma, ron_w_worst_ohm_um):
    """Fingers of FINGER_W_UM so the worst-corner drop meets DROP_TARGET_V,
    rounded up to a whole rectangular array (see array_shape)."""
    r_target = DEVICE_DROP_TARGET_V / (design_ma * 1e-3)
    w_um = ron_w_worst_ohm_um / r_target
    nf = max(20, int(math.ceil(w_um / FINGER_W_UM / 20.0)) * 20)
    return array_shape(nf)[2]


def array_shape(nf):
    """Rows x fingers-per-row covering nf. The array is about twice as wide as
    it is tall (14 um row pitch, 0.8 um finger pitch): VDD/VISL current
    crosses the array vertically on the M5 grid, so a short, wide array keeps
    the grid drop small. Least excess within +-40 fingers of that width."""
    target = max(60, 20 * round(math.sqrt(nf * 35.0) / 20))
    best = None
    for per_row in range(max(20, target - 40), target + 41, 20):
        rows = max(1, math.ceil(nf / per_row))
        cand = (rows * per_row, abs(per_row - target), rows, per_row)
        if best is None or cand < best:
            best = cand
    total, _, rows, per_row = best
    return rows, per_row, total


# ---------------------------------------------------------------------------
# Netlists. Device lines use the PDK subcircuit names so the same text serves
# ngspice (with design.ngspice + sm141064.ngspice) and Netgen LVS.
# ---------------------------------------------------------------------------

GEOM = True   # emit S/D junction geometry for simulation; LVS netlists set False


def _m(name, d, g, s, b, kind, w, l, m=1):
    mult = f' m={m}' if m != 1 else ''
    geom = ''
    if GEOM:
        # Unshared 0.44 um contacted S/D extension per finger, as Magic extracts
        # for a single finger (conservative for shared multi-finger diffusion).
        a = w * 0.44
        pp = 2 * (w + 0.44)
        geom = f' ad={a:.4g}p as={a:.4g}p pd={pp:.4g}u ps={pp:.4g}u'
    return f'X{name} {d} {g} {s} {b} {kind} w={w:g}u l={l:g}u{geom}{mult}'


def isw_netlist(name, nf, variant='bodyswitch', ss_m=1, ss_l=20.0):
    """Island header switch.

    Ports: VDD (common ring), VSS, VISL (island rail), EN (core-domain enable,
    active high), ISO (island-off/clamp request, high = isolate), PG (rail good).
    variant: 'bodyswitch' (selected: single PMOS, auto-bulk well VMAX, gate
    driver on VMAX), 'bodyvdd' (reference: Edwards-style body tied to the
    ring), 'b2b' (back-to-back common-source PMOS pair, 2x fingers each).
    """
    p, n = 'pfet_03v3', 'nfet_03v3'
    L = []
    L.append(f'.subckt {name} VDD VSS VISL EN ISO PG')
    # Undefined/floating EN is pulled to the off state (weak long NMOS).
    L.append(_m('MENPD', 'EN', 'VDD', 'VSS', 'VSS', n, 0.42, 20))
    # Core-domain inverter: ENB.
    L.append(_m('MINVP', 'ENB', 'EN', 'VDD', 'VDD', p, 2, 0.28))
    L.append(_m('MINVN', 'ENB', 'EN', 'VSS', 'VSS', n, 1, 0.28))
    # Auto-bulk selectors scale with the pass device: its n-well junction
    # leakage at 125 C otherwise drags VMAX (and the off gate) below VDD during
    # a slow ring ramp, weakly turning the pass device on (seen in simulation
    # at ff/125 C with 4 um selectors).
    wbt = max(4.0, round(nf * FINGER_W_UM / 330.0))
    wb = (wbt, 0.28, 1) if wbt <= 10 else (10.0, 0.28, int(math.ceil(wbt / 10.0)))   # (w, l, fingers)
    # Discharge NMOS scales with the pass device. A 1 us ring ramp couples
    # the island rail up through the pass drain-well junction and overlap
    # capacitance (~0.61 V at the wired size with a fixed W/L = 1/2 device).
    mdis_w = max(1.0, round(nf * FINGER_W_UM / 9000.0, 1))
    if variant == 'bodyswitch':
        well = 'VMAX'
        L.append(_m('MP', 'VISL', 'GATE', 'VDD', 'VMAX', p, FINGER_W_UM, PASS_L_UM, nf))
        # Auto-bulk selector: VMAX = max(VDD, VISL); MB3 ties the well to VDD while on.
        L.append(_m('MB1', 'VMAX', 'VISL', 'VDD', 'VMAX', p, *wb))
        L.append(_m('MB2', 'VMAX', 'VDD', 'VISL', 'VMAX', p, *wb))
        # MB3 ties the well to VDD while on. Its gate GD is an RC-delayed copy
        # of GATE (MRD + MCD), so at turn-off the well stays tied to VDD until
        # the pass gate is fully charged. Without the delay, the pass gate's
        # charge comes from the floating well (VISL ~ VDD is inside the
        # auto-bulk dead zone), VMAX sags ~0.4 V and the pass device stays
        # weakly on (seen in simulation with an unloaded island).
        L.append(_m('MB3', 'VMAX', 'GD', 'VDD', 'VMAX', p, 4, 0.28))
        L.append(_m('MRD', 'GD', 'VSS', 'GATE', 'VMAX', p, 0.42, 40))
        L.append(_m('MCD', 'VSS', 'GD', 'VSS', 'VSS', n, 10, 10, 2))
    elif variant == 'bodyvdd':
        well = 'VDD'
        L.append(_m('MP', 'VISL', 'GATE', 'VDD', 'VDD', p, FINGER_W_UM, PASS_L_UM, nf))
    elif variant == 'b2b':
        well = 'VMID'
        # Common-source pair: bodies on the shared source node VMID. Each device
        # has 2x fingers to hold the same series resistance.
        L.append(_m('MP', 'VMID', 'GATE', 'VDD', 'VMID', p, FINGER_W_UM, PASS_L_UM, 2 * nf))
        L.append(_m('MP2', 'VMID', 'GATE', 'VISL', 'VMID', p, FINGER_W_UM, PASS_L_UM, 2 * nf))
        # Gate off-level must be the highest terminal: reuse an auto-bulk max.
        L.append(_m('MB1', 'VMAX', 'VISL', 'VDD', 'VMAX', p, *wb))
        L.append(_m('MB2', 'VMAX', 'VDD', 'VISL', 'VMAX', p, *wb))
        well = 'VMAX'
    else:
        raise ValueError(variant)
    # Gate driver on the well supply: strong pull to the off state while EN low.
    L.append(_m('MPU', 'GATE', 'EN', well, well, p, 4, 0.28))
    # Soft start: weak saturated NMOS discharges the gate; Miller capacitance of
    # the pass device sets the island-rail slew.
    L.append(_m('MSS', 'GATE', 'EN', 'VSS', 'VSS', n, 0.42, ss_l, ss_m))
    # Active discharge of the island rail while off (current-limited, long L).
    L.append(_m('MDIS', 'VISL', 'ENB', 'VSS', 'VSS', n, mdis_w if variant == 'bodyswitch' else 1.0, 1.0))
    # Rail-good threshold: high-threshold skewed inverter on VISL + restoring inverter.
    L.append(_m('MPG1P', 'PGB', 'VISL', 'VDD', 'VDD', p, 4, 0.28))
    L.append(_m('MPG1N', 'PGB', 'VISL', 'VSS', 'VSS', n, 0.42, 4))
    L.append(_m('MPG2P', 'PG', 'PGB', 'VDD', 'VDD', p, 2, 0.28))
    L.append(_m('MPG2N', 'PG', 'PGB', 'VSS', 'VSS', n, 1, 0.28))
    # ISO = NAND(EN, PG): high (isolate) unless enabled and the rail is good.
    L.append(_m('MISP1', 'ISO', 'EN', 'VDD', 'VDD', p, 2, 0.28))
    L.append(_m('MISP2', 'ISO', 'PG', 'VDD', 'VDD', p, 2, 0.28))
    L.append(_m('MISN1', 'ISO', 'EN', 'NISO', 'VSS', n, 2, 0.28))
    L.append(_m('MISN2', 'NISO', 'PG', 'VSS', 'VSS', n, 2, 0.28))
    L.append(f'.ends {name}')
    return '\n'.join(L) + '\n'


ATB_VARIANTS = {
    # name: (T1 nfet W, T1 pfet W, T1 L, T2 nfet W, T2 pfet W, shunt W), um.
    # T1 touches the tapped node; T2 the bus side.
    'atb_leaf_s': (0.42, 0.84, 0.28, 1.0, 2.0, 1.0),  # sense leaf: minimum T1 for <= 5 fF node loading
    'atb_leaf_f': (4.0, 8.0, 0.5, 4.0, 8.0, 1.0),     # force leaf: L=0.5 T1 for <= 100 pA node leakage
    'atb_grp': (8.0, 16.0, 0.28, 8.0, 16.0, 2.0),     # group (local bus -> global bus) T-switch
}
# Bare leaves: a switch pair + one inverter, driven directly by the register
# file's one-hot atb{0,1}_sw[code-1] line. Default-open comes from the
# register reset (all lines 0). Break-before-make comes from the commit rule:
# a zero code is committed between two non-zero codes. The group switch
# (atb_grp) and pad switch (atb_pad) keep the pulldown + delayed non-overlap
# control as a hardware backstop.
BARE_LEAVES = ('atb_leaf_s', 'atb_leaf_f')


def atb_ctl_lines():
    """Shared select logic: default-open pulldown and break-before-make.

    SD is a delayed copy of SEL. TGON = SEL & SD (late on, early off);
    SHON = !SEL & !SD (late on, early off). TGON and SHON never overlap and a
    deselected cell opens before any newly selected cell on the same bus closes.
    """
    p, n = 'pfet_03v3', 'nfet_03v3'
    return [
        _m('MSPD', 'SEL', 'VDD', 'VSS', 'VSS', n, 0.42, 20),
        _m('MD1P', 'SA', 'SEL', 'VDD', 'VDD', p, 0.84, 2),
        _m('MD1N', 'SA', 'SEL', 'VSS', 'VSS', n, 0.42, 2),
        _m('MD2P', 'SD', 'SA', 'VDD', 'VDD', p, 0.84, 2),
        _m('MD2N', 'SD', 'SA', 'VSS', 'VSS', n, 0.42, 2),
        # NAND(SEL, SD) -> TGONB
        _m('MNAP1', 'TGONB', 'SEL', 'VDD', 'VDD', p, 1, 0.28),
        _m('MNAP2', 'TGONB', 'SD', 'VDD', 'VDD', p, 1, 0.28),
        _m('MNAN1', 'TGONB', 'SEL', 'NNA', 'VSS', n, 1, 0.28),
        _m('MNAN2', 'NNA', 'SD', 'VSS', 'VSS', n, 1, 0.28),
        _m('MTGP', 'TGON', 'TGONB', 'VDD', 'VDD', p, 2, 0.28),
        _m('MTGN', 'TGON', 'TGONB', 'VSS', 'VSS', n, 1, 0.28),
        # NOR(SEL, SD) -> SHON
        _m('MNOP1', 'NNO', 'SEL', 'VDD', 'VDD', p, 2, 0.28),
        _m('MNOP2', 'SHON', 'SD', 'NNO', 'VDD', p, 2, 0.28),
        _m('MNON1', 'SHON', 'SEL', 'VSS', 'VSS', n, 1, 0.28),
        _m('MNON2', 'SHON', 'SD', 'VSS', 'VSS', n, 1, 0.28),
    ]


def atb_tap_netlist(name):
    wn1, wp1, l1, wn, wp, wsh = ATB_VARIANTS[name]
    p, n = 'pfet_03v3', 'nfet_03v3'
    L = [f'.subckt {name} NODE BUS SEL VDD VSS']
    if name in BARE_LEAVES:
        L.append(_m('MSWP', 'SWB', 'SEL', 'VDD', 'VDD', p, 1.0, 0.28))
        L.append(_m('MSWN', 'SWB', 'SEL', 'VSS', 'VSS', n, 0.5, 0.28))
        on, onb, sh = 'SEL', 'SWB', 'SWB'
    else:
        L += atb_ctl_lines()
        on, onb, sh = 'TGON', 'TGONB', 'SHON'
    # T-switch: NODE -TG1- MID -TG2- BUS, MID shunted to VSS when open.
    L.append(_m('MT1N', 'NODE', on, 'MID', 'VSS', n, wn1, l1))
    L.append(_m('MT1P', 'NODE', onb, 'MID', 'VDD', p, wp1, l1))
    L.append(_m('MT2N', 'MID', on, 'BUS', 'VSS', n, wn, 0.28))
    L.append(_m('MT2P', 'MID', onb, 'BUS', 'VDD', p, wp, 0.28))
    L.append(_m('MSH', 'MID', sh, 'VSS', 'VSS', n, wsh, 0.28))
    L.append(f'.ends {name}')
    return '\n'.join(L) + '\n'


ATB_PAD = {'wn': 8.0, 'wp': 16.0, 'wsh': 2.0}


def atb_pad_netlist(name='atb_pad'):
    """Pad-side switch between the provider analog pad (PAD) and the global bus.

    The pad can be driven from the bench while the die is unpowered or below the
    pad voltage, so the PMOS well is an auto-bulk VMAX = max(VDD, PAD) and its
    off gate is pulled to VMAX. NMOS gate is a VDD-domain signal (0 when VDD is
    absent). The global bus is shunted to VSS while open.
    """
    p, n = 'pfet_03v3', 'nfet_03v3'
    L = [f'.subckt {name} PAD BUS SEL VDD VSS']
    L += atb_ctl_lines()
    L.append(_m('MB1', 'VMAX', 'PAD', 'VDD', 'VMAX', p, 2, 0.28))
    L.append(_m('MB2', 'VMAX', 'VDD', 'PAD', 'VMAX', p, 2, 0.28))
    L.append(_m('MGPU', 'GP', 'TGON', 'VMAX', 'VMAX', p, 1, 0.28))
    L.append(_m('MGPD', 'GP', 'TGON', 'VSS', 'VSS', n, 1, 0.28))
    L.append(_m('MTN', 'PAD', 'TGON', 'BUS', 'VSS', n, ATB_PAD['wn'], 0.28))
    L.append(_m('MTP', 'PAD', 'GP', 'BUS', 'VMAX', p, ATB_PAD['wp'], 0.28))
    L.append(_m('MSH', 'BUS', 'SHON', 'VSS', 'VSS', n, ATB_PAD['wsh'], 0.28))
    L.append(f'.ends {name}')
    return '\n'.join(L) + '\n'


def iso_clamp_netlist(name='iso_clamp'):
    """Core-boundary isolation clamp, core VDD domain: Y = A AND NOT ISO.
    Used in both directions: island->core (A from the island, possibly
    back-powered) and core->island (keeps core drive off an unpowered island's
    inputs). A only reaches a gate, so an island at up to 3.63 V cannot inject
    into the core rail."""
    p, n = 'pfet_03v3', 'nfet_03v3'
    L = [f'.subckt {name} A ISO Y VDD VSS']
    L.append(_m('MIP', 'AN', 'A', 'VDD', 'VDD', p, 1, 0.28))
    L.append(_m('MIN', 'AN', 'A', 'VSS', 'VSS', n, 0.5, 0.28))
    # NOR(AN, ISO)
    L.append(_m('MP1', 'NY', 'ISO', 'VDD', 'VDD', p, 2, 0.28))
    L.append(_m('MP2', 'Y', 'AN', 'NY', 'VDD', p, 2, 0.28))
    L.append(_m('MN1', 'Y', 'AN', 'VSS', 'VSS', n, 0.5, 0.28))
    L.append(_m('MN2', 'Y', 'ISO', 'VSS', 'VSS', n, 0.5, 0.28))
    L.append(f'.ends {name}')
    return '\n'.join(L) + '\n'


# ATB hierarchy plan (chip-wide): 8 groups x 12 leaves = 96 node slots.
ATB_PLAN = {
    'groups': ['core_bias_ref', 'pll_timing', 'rf_rx', 'rf_tx', 'conv', 'wired_rx',
               'wired_tx_usb', 'supply_monitors_replicas'],
    'leaves_per_group': 12,
    'force_capable_leaves_per_group': 4,
    'select_bits': {'group': 3, 'leaf': 4, 'bus_enable': 2},
}


if __name__ == '__main__':
    alloc, src = island_allocations()
    print(json.dumps(alloc, indent=1))
