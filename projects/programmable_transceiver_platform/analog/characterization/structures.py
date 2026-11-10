"""Characterization structures reached through the analog test bus (ATB).

One cell, `pt_char_atb`, holds every ATB characterization node of the
register map (codes 43-54, spec/register-map.md "ATB nodes"):

  43..50  device replicas, one node each, diode-connected:
          NMOS  drain = gate = NODE, source = body = VSS
          PMOS  source = body (n-well) = NODE, drain = gate = VSS
          Forcing a current into NODE through ATB0 and reading NODE through
          ATB1 (Kelvin) gives the diode I-V: Vt, k' and subthreshold slope.
  51, 52  resistor matching pair: four ppolyf_u_1k units in series per side,
          interleaved A B B A A B B A in one row; NODE -> ... -> VSS.
  53, 54  MIM matching pair: two cap_mim_2f0 units per side, A B B A; top
          plate = NODE, bottom plate = VSS.

The cell has no VDD connection at all. Every structure is a two-terminal
device between its ATB node and VSS, so with the bus open it draws only
junction leakage, and it cannot back-power anything.

Device sizes are the unit fingers the blocks use (counted from the block
netlists: rf_rx/lna.spice, rf_rx/rxmix_i.spice, converters/adc_i.spice,
rf_tx/rfdriver.spice).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'converters' / 'lib'))
from convkit import Mos, Cap, Res, Circuit  # noqa: E402

CELL = 'pt_char_atb'

# code, port, model, w, l, m, source of the size
REPLICAS = [
    (43, 'RN_LNA', 'nfet_03v3', 5.0, 0.5, 2, 'lna.spice gm fingers nfet 5/0.5 (x112)'),
    (44, 'RP_LNA', 'pfet_03v3', 5.0, 0.28, 2, 'lna.spice pfet 5/0.28 (x32)'),
    (45, 'RN_MIX', 'nfet_03v3', 5.0, 0.28, 2, 'rxmix_i.spice switch nfet 5/0.28 (x24)'),
    (46, 'RP_MIX', 'pfet_03v3', 20.0, 1.0, 1, 'rxmix_i.spice load pfet 20/1 (x66)'),
    (47, 'RN_SMP', 'nfet_03v3', 8.0, 0.28, 1, 'converters/circuits.py bootstrap(): ADC sampling switch MS nfet 8/0.28'),
    (48, 'RP_SMP', 'pfet_03v3', 10.0, 0.28, 1, 'adc_i.spice comparator/logic pfet 10/0.28 (x101); the 5/0.28 pfet is already RP_LNA'),
    (49, 'RN_DRV', 'nfet_03v3', 20.0, 0.5, 1, 'rfdriver.spice nfet 20/0.5 (x140)'),
    (50, 'RP_DRV', 'pfet_03v3', 20.0, 0.28, 1, 'rfdriver.spice pfet 20/0.28 (x52)'),
]
RES_UNIT = dict(w=2.0, l=10.0)      # ppolyf_u_1k, ~5 kohm per unit
RES_UNITS = 4                       # per side -> ~20 kohm
MIM_UNIT = 40.0                     # um square cap_mim_2f0 (~3.2 pF)
MIM_UNITS = 2                       # per side -> ~6.5 pF
PASSIVES = [(51, 'RES_A'), (52, 'RES_B'), (53, 'MIM_A'), (54, 'MIM_B')]
PORTS = [p for _, p, *_ in REPLICAS] + [p for _, p in PASSIVES] + ['VSS']
ATB_CODE = {p: c for c, p, *_ in REPLICAS}
ATB_CODE.update({p: c for c, p in PASSIVES})


def circuit():
    devs, nrow, prow = [], [], []
    for code, port, model, w, l, m, _ in REPLICAS:
        name = 'M' + port
        if model == 'nfet_03v3':
            devs.append(Mos(name, model, w, l, d=port, g=port, s='VSS', b='VSS', m=m))
            nrow.append(name)
        else:
            devs.append(Mos(name, model, w, l, d='VSS', g='VSS', s=port, b=port, m=m))
            prow.append(name)
    # resistor chains, interleaved A B B A A B B A
    order = 'ABBAABBA'
    k = {'A': 0, 'B': 0}
    rrow = []
    for side in order:
        i = k[side]
        k[side] += 1
        node = f'RES_{side}'
        a = node if i == 0 else f'r{side.lower()}{i}'
        b = 'VSS' if i == RES_UNITS - 1 else f'r{side.lower()}{i + 1}'
        name = f'R{side}{i}'
        devs.append(Res(name, RES_UNIT['w'], RES_UNIT['l'], a=a, b=b, sub='VSS'))
        rrow.append(name)
    crow = []
    for j, side in enumerate('ABBA'):
        name = f'C{side}{j}'
        devs.append(Cap(name, MIM_UNIT, MIM_UNIT, top=f'MIM_{side}', bot='VSS'))
        crow.append(name)
    return Circuit(CELL, PORTS, devs, rows=[nrow, prow, rrow, crow],
                   wide_nets={'VSS': 2.0})


if __name__ == '__main__':
    print(circuit().spice())
