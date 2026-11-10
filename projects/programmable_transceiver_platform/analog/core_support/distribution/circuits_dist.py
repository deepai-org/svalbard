"""Per-island bias distribution: one trunk per island from the master biasgen.

Topology (all 3.3 V devices; every consumer *sinks* 10 uA into an NMOS diode on
its IBIAS pin, so each island output must *source* 10 uA):

  biasgen idac2_source (bandgap mode, coarse, code 10 = 10 uA)
      -> pt_bias_root  (always-on core rail): NMOS diode + one NMOS mirror leg
         per island trunk.  Each leg sinks 10 uA from its trunk through an NMOS
         series switch gated by EN_<island> (register reset value 0 = off).
      -> trunk wire (current mode, so IR drop along the die does not matter)
      -> pt_bias_bank<N> (on the island's switched rail): PMOS diode receives the
         trunk current; N PMOS mirror outputs, each with a PMOS series switch
         that is closed only when the consuming block's EN is high.

Cascodes are deliberately not used: the consumer pins sit at ~0.95 V, a PMOS
diode drops ~1.2 V, and stacked-diode cascodes at both ends leave no compliance
on a 3.3 V rail.  Long channels (L = 4 um) keep the Vds-induced error small.

ATB hooks: ROOT_REF (master diode, force a current in to replace the biasgen)
and each TRK_<island> (island diode, force a current out to replace the root
leg after EN_<island> = 0).  The ATB leaf switches themselves are
analog/island_support cells placed at integration.
"""
import sys
from pathlib import Path

RF_TX = Path(__file__).resolve().parents[2] / 'rf_tx'
sys.path.insert(0, str(RF_TX))
try:
    from circuits import Circuit  # noqa: E402  (shared generator data model, analog/rf_tx/circuits.py)
except ImportError:  # simulation containers mount only analog/core_support; ISLANDS is all they need
    Circuit = None

ISLANDS = {
    # island: consumers (block IBIAS pins), from the analog/*/README.md inventory
    'rf': ['lna', 'rxmix_i', 'rxmix_q', 'bbfilter_i', 'bbfilter_q', 'txmix_i', 'txmix_q', 'rfdriver'],
    'conv': ['adc_i', 'adc_q', 'dac_i', 'dac_q', 'refbuf'],
    # consolidation pass 3: pll trunk feeds three pt_pll_ring instances (TX/shared, RX CDR,
    # host_follow) and one reserved output for a possible LC-VCO loop (default off)
    'pll': ['pll_ring_tx', 'pll_ring_rx', 'pll_ring_host', 'lc_vco_reserved'],
    'wire': ['ctle', 'detect', 'wiredtx'],
    'debug': ['bb_tap_i', 'bb_tap_q', 'bb_tap_wmon'],
}

NM = dict(w=4.0, l=4.0)      # NMOS mirror device (root)
PM = dict(w=5.0, l=4.0)      # PMOS mirror device (bank), 2 fingers
SWN = dict(w=4.0, l=0.5)
SWP = dict(w=8.0, l=0.5)


def root(name='pt_bias_root'):
    isl = list(ISLANDS)
    c = Circuit(name, ['VSS', 'ROOT_REF'] + [f'EN_{i.upper()}' for i in isl] + [f'TRK_{i.upper()}' for i in isl])
    c.notes += ['Master-side trunk splitter: ROOT_REF receives 10 uA (biasgen idac2, or ATB force);',
                'one 1:1 NMOS leg per island trunk, switched by EN_<island> (default off).']
    c.n('MREF', 'ROOT_REF', 'ROOT_REF', 'VSS', NM['w'], NM['l'], nf=2)
    for i in isl:
        I = i.upper()
        c.n(f'M_{I}', f'm_{i}', 'ROOT_REF', 'VSS', NM['w'], NM['l'], nf=2)
        c.n(f'SW_{I}', f'TRK_{I}', f'EN_{I}', f'm_{i}', SWN['w'], SWN['l'])
    return c


def bank(n, name=None):
    name = name or f'pt_bias_bank{n}'
    c = Circuit(name, ['VDD', 'VSS', 'TRK'] + [f'EN{k}' for k in range(n)] + [f'OUT{k}' for k in range(n)])
    c.notes += [f'Island mirror bank with {n} switched 10 uA source outputs on the island rail (VDD = VISL).',
                'TRK is the PMOS diode node (trunk from pt_bias_root, or ATB force).']
    c.p('PREF', 'TRK', 'TRK', 'VDD', PM['w'], PM['l'], nf=2)
    for k in range(n):
        # enable inverter on the island rail; 4/8 um gates keep long EN routes inside
        # the metal-to-gate antenna ratio (minimum-size gates failed ANT.5 in bank8)
        c.n(f'I{k}_N', f'enb{k}', f'EN{k}', 'VSS', 4.0, 0.28)
        c.p(f'I{k}_P', f'enb{k}', f'EN{k}', 'VDD', 8.0, 0.28)
        c.p(f'PM{k}', f'pm{k}', 'TRK', 'VDD', PM['w'], PM['l'], nf=2)
        c.p(f'PS{k}', f'OUT{k}', f'enb{k}', f'pm{k}', SWP['w'], SWP['l'])
    return c


# Master voltage references (analog-architecture.json bias.vref0 / bias.vcm).
# Passive, always-on, on core VDD; no register control, so reset-safe by
# construction (both outputs stay inside 0..VDD and only drive gates or
# n-diffusion sampling switches).  One unit resistor everywhere for ratio
# matching: ppolyf_u_1k (unsalicided, high-R) W=1 um L=40 um, ~40 kohm.
#   VREF0 = VBG * 5/6  (1.212 V -> 1.010 V): 1 unit VBG->VREF0, 5 units
#           VREF0->VSS; 240 kohm loads the bandgap's class-AB buffered vbg with
#           ~5 uA.  Bandgap off -> VREF0 discharges to 0.  An ATB0 force of VBG
#           (fallback) moves VREF0 with it.
#   VCM   = VDD / 2    (1.65 V at 3.3 V): 2 units VDD->VCM, 2 units VCM->VSS;
#           ~20 uA static, 40 kohm Thevenin.  Ratiometric to the supply, which
#           is what the 'about VDD/2' consumers (ADC top-plate VCM) need; any
#           charge-sharing decoupling belongs at the consumer.
VREF_UNIT = dict(w=1.0, l=40.0)


def vref(name='pt_bias_vref'):
    c = Circuit(name, ['VDD', 'VSS', 'VBG', 'VREF0', 'VCM'])
    c.notes += ['Passive master references: VREF0 = 5/6 VBG, VCM = VDD/2 (always on, core VDD).']
    c.r('RV_T', 'VBG', 'VREF0', **VREF_UNIT)
    chain = ['VREF0', 'v1', 'v2', 'v3', 'v4', 'VSS']
    for k in range(5):
        c.r(f'RV_B{k}', chain[k], chain[k+1], **VREF_UNIT)
    cm = ['VDD', 'c1', 'VCM', 'c2', 'VSS']
    for k in range(4):
        c.r(f'RC_{k}', cm[k], cm[k+1], **VREF_UNIT)
    return c


BANKS = sorted({len(v) for v in ISLANDS.values()})
CELLS = {'pt_bias_root': root, 'pt_bias_vref': vref}
CELLS.update({f'pt_bias_bank{n}': (lambda n=n: bank(n)) for n in BANKS})
