"""Core-support cells added 2026-11-14 for the chip top's build demands (D-BIAS, D-REFVCM, D-TXTERM).

Kept out of circuits_dist.py so the hashes recorded in the published distribution evidence stay valid.
Same generator and unit devices as the banks.  Build: generate_ext.py (layout, DRC, LVS, KLayout DRC, GDS read-back LVS).
"""
from circuits_dist import Circuit, NM, PM, SWN, SWP, VREF_UNIT
def tap(n, name=None):
    """Extra switched 10 uA outputs on an EXISTING island trunk (D-BIAS).

    Identical to bank(n) without the PMOS diode: the mirror gates sit on the
    trunk node TRK, whose diode is in the island's pt_bias_bank.  Same unit
    devices, so an output equals a bank output as long as the tap shares the
    bank's local rail (integration rule: abut the bank, same VDD strap; rail
    offset sensitivity is in the evidence).  A tap adds only gate load to TRK.
    """
    name = name or f'pt_bias_tap{n}'
    c = Circuit(name, ['VDD', 'VSS', 'TRK'] + [f'EN{k}' for k in range(n)] + [f'OUT{k}' for k in range(n)])
    c.notes += [f'{n} more switched 10 uA source outputs on an island trunk; no diode (the diode is in the island bank).']
    for k in range(n):
        c.n(f'I{k}_N', f'enb{k}', f'EN{k}', 'VSS', 4.0, 0.28)
        c.p(f'I{k}_P', f'enb{k}', f'EN{k}', 'VDD', 8.0, 0.28)
        c.p(f'PM{k}', f'pm{k}', 'TRK', 'VDD', PM['w'], PM['l'], nf=2)
        c.p(f'PS{k}', f'OUT{k}', f'enb{k}', f'pm{k}', SWP['w'], SWP['l'])
    return c


def refvcm(name='pt_refvcm'):
    """Common-mode source for the refpad VCM pins (D-REFVCM): VDD/2 of its island rail, gated.

    EN = 1: 2 + 2 units of the pt_bias_vref resistor (ppolyf_u_1k 1 x 40 um) behind a PMOS header:
    ~20 uA, ~40 kohm Thevenin; the refpads only take DC bias through 100 kohm per leg.
    EN = 0: header off, the lower half pulls VCM (and the pads) to VSS, no current.
    Four NMOS gate capacitors (20 x 10 um each) shunt LO common-mode current on VCM.
    """
    c = Circuit(name, ['VDD', 'VSS', 'EN', 'VCM'])
    c.notes += ['Refpad common-mode source: VCM = VDD/2 when EN, 0 V when off; separate from the ADC VCM_MASTER.']
    c.n('IE_N', 'enb', 'EN', 'VSS', 4.0, 0.28)
    c.p('IE_P', 'enb', 'EN', 'VDD', 8.0, 0.28)
    c.p('PH', 'top', 'enb', 'VDD', 10.0, 0.5, nf=2)
    chain = ['top', 't1', 'VCM', 'b1', 'VSS']
    for k in range(4):
        c.r(f'RC_{k}', chain[k], chain[k+1], **VREF_UNIT)
    for k in range(4):
        c.n(f'CD{k}', 'VSS', 'VCM', 'VSS', 20.0, 10.0)
    return c


TXB_UNIT = dict(w=2.0, l=20.0)    # 10 kohm nominal, ppolyf_u_1k


def txpad_bias(name='pt_txpad_bias'):
    """Reference and bias for the TX-pad termination buffer, and the TX-pad detect PMOS bias (D-TXTERM).

    BUF_REF  = VDD/2            (10k + 10k)   } exactly the divider fixture every pads bench used
    BUF_BIAS = VDD * 3/11       (80k + 30k)   } (termination_buffer_connected.py RREF1/2, RBIAS1/2)
    Both dividers hang on PMOS headers closed by EN; EN = 0 gives 0 V on both (buffer tail off) and no current.
    DETECT_PBIAS: IBIAS_DET (10 uA sourced by an island bias output) -> NMOS diode -> x5 NMOS mirror ->
    PMOS diode 4/2 um = the pad's DETECT_x_SOURCE device, so each pad leg sources ~50 uA.
    x5, not x10 (review 2026-11-14): the pad's 4/2 um PMOS needs ~2.85 V of Vsg for the 100 uA of
    analog-architecture detect.test_current_a, which leaves the mirror 0.14-0.45 V (triode, 73-101 uA, supply-set);
    at x5 DETECT_PBIAS stays >= 0.54 V and the current is 49-51 uA over all corners.  100 uA needs a wider pad
    source device (TX pad relayout).  EN_DET = 0: mirror input open and DETECT_PBIAS tied to VDD.
    """
    c = Circuit(name, ['VDD', 'VSS', 'EN', 'BUF_REF', 'BUF_BIAS', 'EN_DET', 'IBIAS_DET', 'DETECT_PBIAS'])
    c.notes += ['TX-pad termination buffer REF/BIAS dividers (gated) and detect-source PMOS bias (gated).']
    c.n('IE_N', 'enb', 'EN', 'VSS', 4.0, 0.28)
    c.p('IE_P', 'enb', 'EN', 'VDD', 8.0, 0.28)
    c.p('PHR', 'rtop', 'enb', 'VDD', 20.0, 0.5, nf=4)
    c.r('RR_T', 'rtop', 'BUF_REF', **TXB_UNIT)
    c.r('RR_B', 'BUF_REF', 'VSS', **TXB_UNIT)
    c.p('PHB', 'btop', 'enb', 'VDD', 10.0, 0.5, nf=2)
    prev = 'btop'
    for k in range(8):
        nxt = 'BUF_BIAS' if k == 7 else f'bt{k}'
        c.r(f'RB_T{k}', prev, nxt, **TXB_UNIT)
        prev = nxt
    prev = 'BUF_BIAS'
    for k in range(3):
        nxt = 'VSS' if k == 2 else f'bb{k}'
        c.r(f'RB_B{k}', prev, nxt, **TXB_UNIT)
        prev = nxt
    # detect bias
    c.n('ID_N', 'endb', 'EN_DET', 'VSS', 4.0, 0.28)
    c.p('ID_P', 'endb', 'EN_DET', 'VDD', 8.0, 0.28)
    c.n('SWD', 'IBIAS_DET', 'EN_DET', 'nd', SWN['w'], SWN['l'])
    c.n('PDN', 'nd', 'endb', 'VSS', 2.0, 0.28)
    c.n('MD', 'nd', 'nd', 'VSS', NM['w'], NM['l'], nf=2)
    for k in range(5):
        c.n(f'MM{k}', 'DETECT_PBIAS', 'nd', 'VSS', NM['w'], NM['l'], nf=2)
    c.p('PD', 'DETECT_PBIAS', 'DETECT_PBIAS', 'VDD', 4.0, 2.0)
    c.p('PUP', 'DETECT_PBIAS', 'EN_DET', 'VDD', 2.0, 0.28)
    return c


EXTRA = {'pt_bias_tap2': lambda: tap(2), 'pt_refvcm': refvcm, 'pt_txpad_bias': txpad_bias}

