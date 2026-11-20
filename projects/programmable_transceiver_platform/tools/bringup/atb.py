"""ATB1 sense-bus model for simulation and the expected values / limits of the bring-up test plan (spec/bring-up.md
section 10). A real board replaces `AtbSim.node_volts` by an SMU/DMM reading of the ATB1 pad.
Bus path (analog/island_support/README.md): atb_leaf_s 16.4 kOhm + atb_grp 1.17 kOhm + atb_pad 0.59 kOhm (functional
max Ron); meter = spec/test-board/tb_models.spice `tb_atb_meter` (10 MOhm || cable)."""
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
MAP = json.loads((PROJECT/'spec/register-map.json').read_text())
GROUP = {c: g for g, grp in enumerate(MAP['atb_groups']['atb1']) for c in grp['codes']}
R_BUS = 16.4e3 + 1.17e3 + 0.59e3
R_METER = 10e6

# code: (name, island bit or None, expected volts as a function of VDD, low, high limit fn, source impedance, basis)
def _vdd(v): return v
EXPECT = {
    55: ('VBG (trimmed)', None, lambda v: 1.200, lambda v: 1.190, lambda v: 1.210, 5e3, 'core_support README: trim to 1.200 V; untrimmed 1.204-1.220'),
    1: ('ROOT_REF', None, lambda v: 0.92, lambda v: 0.80, lambda v: 1.05, 20e3, 'core_support README 0.92 V nominal; +-13 % for Vt spread'),
    2: ('VREF0', None, lambda v: 1.000, lambda v: 0.985, lambda v: 1.015, 20e3, 'pt_bias_vref = 5/6 VBG (1.010 at VBG 1.212)'),
    3: ('VCM master', None, lambda v: v/2, lambda v: 0.495*v, lambda v: 0.505*v, 40e3, 'pt_bias_vref VDD/2 divider'),
    5: ('core VDD', None, _vdd, lambda v: v-0.03, lambda v: v+0.01, 1.0, 'die VDD = board setpoint minus IR (117 mV budget, quiescent < 30 mV)'),
    13: ('local VSS', None, lambda v: 0.0, lambda v: -0.01, lambda v: 0.01, 1.0, 'register-map: < 10 mV'),
    9: ('pll rail', 2, _vdd, lambda v: v-0.05, lambda v: v+0.01, 1.0, 'island on: VDD minus switch drop (isw ~15 mV); off: < 0.3 V'),
    12: ('debug rail', 5, _vdd, lambda v: v-0.05, lambda v: v+0.01, 1.0, 'as above'),
    8: ('rf_rx rail', 1, _vdd, lambda v: v-0.05, lambda v: v+0.01, 1.0, 'as above (isw_rf 16.5 mV at 55 mA)'),
    11: ('conv rail', 4, _vdd, lambda v: v-0.05, lambda v: v+0.01, 1.0, 'as above'),
    7: ('wired_rx rail', 0, _vdd, lambda v: v-0.05, lambda v: v+0.01, 1.0, 'as above'),
    10: ('wired_tx rail', 0, _vdd, lambda v: v-0.05, lambda v: v+0.01, 1.0, 'as above'),
    32: ('REF_VCM (refvcm on)', 2, lambda v: 0.4988*v, lambda v: 0.495*v, lambda v: 0.502*v, 40e3, 'core_support README pt_refvcm 0.4984-0.4992 VDD, 40 kOhm source'),
}
RAIL_OFF_MAX = 0.3      # register-map / debug-controls: switched rail reads < 0.3 V off


def leaves(chip):
    """ATB1 codes that have a physical leaf on this chip (integration/chips/{common,<chip>}/chip.conn)."""
    import re
    txt = (PROJECT/'integration/chips/common.conn').read_text() + (PROJECT/f'integration/chips/{chip}/chip.conn').read_text()
    return {int(m.group(1)) for m in re.finditer(r'^inst atb1_leaf(\d+) ', txt, re.M)}


class AtbSim:
    """Reads what the RTL actually closed (leaf, group, pad switch) and returns the meter voltage of the modelled node;
    None if the switch path is open (a software or RTL fault: the bus floats)."""
    def __init__(self, sim, chip, vdd=3.30):
        self.sim, self.vdd, self.leaves = sim, vdd, leaves(chip)
    def node_volts(self, code, island_on):
        name, isl, f, lo, hi, rsrc, basis = EXPECT[code]
        v = f(self.vdd) if (isl is None or island_on >> isl & 1) else 0.0
        return v*R_METER/(R_METER+rsrc+R_BUS)
    def read(self, code):
        sw, grp, en, ion = self.sim.atb_state()
        if not (sw >> (code-1) & 1 and grp >> GROUP[code] & 1 and en) or code not in self.leaves:
            return None     # switch path open, or no leaf on this chip (the RTL still accepts the code: OBS-6)
        return self.node_volts(code, ion)


def judge(code, volts, vdd, island_on):
    name, isl, f, lo, hi, rsrc, basis = EXPECT[code]
    if isl is not None and not island_on >> isl & 1:
        return volts is not None and volts < RAIL_OFF_MAX, f'{name} (island off) < {RAIL_OFF_MAX} V'
    return volts is not None and lo(vdd) <= volts <= hi(vdd), f'{name} {lo(vdd):.3f}..{hi(vdd):.3f} V ({basis})'
