"""Schematic (and extracted) ngspice campaigns for the island support cells.

Runs inside the pinned iic-osic-tools image. Every number written to the
result JSON is parsed from ngspice output; a missing measurement is recorded
as null and fails its criterion.
"""
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design  # noqa: E402

PDK_NG = '/foss/pdks/gf180mcuD/libs.tech/ngspice'
CORNER_LIB = {'tt': 'typical', 'ff': 'ff', 'ss': 'ss', 'fs': 'fs', 'sf': 'sf'}
CORNERS = ['tt', 'ff', 'ss', 'fs', 'sf']
TEMPS = [-40, 27, 125]
VDDS = [3.0, 3.3, 3.6]
WORK = Path('/work/sims')
NUM = r'([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)'


def header(corner, temp):
    return (f'* generated\n.include {PDK_NG}/design.ngspice\n'
            f'.lib {PDK_NG}/sm141064.ngspice {CORNER_LIB[corner]}\n'
            f'.temp {temp}\n.option scale=1 gmin=1e-15 reltol=1e-4\n')


def run(job):
    name, text = job
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / f'{name}.sp'
    path.write_text(text)
    proc = subprocess.run(['ngspice', '-b', str(path)], capture_output=True, text=True, timeout=1800)
    out = proc.stdout + proc.stderr
    (WORK / f'{name}.log').write_text(out)
    vals = {}
    for m in re.finditer(r'^\s*([a-z_0-9]+)\s*=\s*' + NUM, out, re.M | re.I):
        vals[m.group(1).lower()] = float(m.group(2))
    vals['_rc'] = proc.returncode
    vals['_error'] = bool(re.search(r'(?i)error|singular|timestep too small|failed', out)) and not vals
    return name, vals


def run_all(jobs, workers):
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return dict(ex.map(run, jobs))


# ---------------------------------------------------------------------------
# Island switch
# ---------------------------------------------------------------------------

def pdn(bg_ma):
    """Common-ring reduced PDN (analog-architecture.json power.parameters), DC-corrected bond resistance."""
    arch, _ = design.architecture()
    p = arch['blocks']['power']['parameters']
    n = p['reduced_pdn_model']['network']
    return (f"VSUP src 0 PWL(0 0 2u {{VS}})\n"
            f"Rfeed src f1 {n['feed_r']}\nLfeed f1 board {n['feed_l']}\n"
            f"Rbc board b1 {n['board_esr']}\nLbc b1 b2 {n['board_esl']}\nCbc b2 0 {n['board_c']}\n"
            # DC: 8 supply + 10 return bonds at ~0.1 ohm each (coordinator budget,
            # ~25 mV bond drop at 250 mA), lumped into the supply path. The model's
            # 2 ohm package_r is an unmeasured AC damping value, so it sits across
            # the bond inductance instead of in series.
            f"Rpkg board p1 {0.1 / 8 + 0.1 / 10}\nLpkg p1 VDD {p['bond_l_h']}\nRdamp p1 VDD {n['package_r']}\n"
            f"Rdc VDD d1 {n['die_esr']}\nLdc d1 d2 {n['die_esl']}\nCdc d2 0 {n['die_c']}\n"
            f"Ibg VDD 0 PWL(0 0 5u {bg_ma}m)\n")


OVERRIDE = {}   # cell name -> extracted subckt text (renamed to the schematic name)


def isw_cell(name, nf, variant='bodyswitch', ss_m=1, ss_l=20.0):
    if name in OVERRIDE and variant == 'bodyswitch' and ss_m == 1:
        return OVERRIDE[name]
    return design.isw_netlist(name, nf, variant, ss_m, ss_l)


def isw_drop_job(isl, nf, corner, temp, vdd, i_ma):
    t = header(corner, temp) + isw_cell('isw', nf)
    t += (f'VDD VDD 0 {vdd}\nVEN EN 0 {vdd}\nIL VISL 0 {i_ma}m\nXI VDD 0 VISL EN ISO PG isw\n'
          '.control\nop\nlet drop = v(vdd)-v(visl)\nprint drop\nlet pg=v(pg)\nprint pg\nlet iso=v(iso)\nprint iso\n'
          'let iq = -i(vdd) - ' + f'{i_ma}e-3' + '\nprint iq\n.endc\n.end\n')
    return (f'drop_{isl}_{corner}_{temp}_{vdd}', t)


def isw_leak_job(isl, nf, corner, temp, vdd, variant='bodyswitch'):
    t = header(corner, temp) + isw_cell('isw', nf, variant)
    t += (f'VDD VDD 0 {vdd}\nVEN EN 0 0\nVISL VISL 0 0\nXI VDD 0 VISL EN ISO PG isw\n'
          '.control\nop\nlet ileak = i(visl)\nprint ileak\nlet ivdd = -i(vdd)\nprint ivdd\n.endc\n.end\n')
    return (f'leak_{variant}_{isl}_{corner}_{temp}_{vdd}', t)


def isw_reverse_job(isl, nf, corner, temp, vdd, visl, variant):
    t = header(corner, temp) + isw_cell('isw', nf, variant)
    # Peer modeled as an ideal source behind 10 ohm (driver + pad path), so a
    # forward-biased body diode or conducting channel gives a bounded current.
    t += (f'VDD VDD 0 {vdd}\nVEN EN 0 0\nVPEER PEER 0 {visl}\nRPEER PEER VISL 10\nXI VDD 0 VISL EN ISO PG isw\n'
          '.control\nop\nlet i_into_ring = i(vdd)\nprint i_into_ring\nlet i_from_peer = -i(vpeer)\nprint i_from_peer\nlet visl_v = v(visl)\nprint visl_v\n.endc\n.end\n')
    return (f'rev_{variant}_{isl}_{corner}_{temp}_{vdd}_{visl}', t)


def isw_tran_job(isl, nf, corner, temp, vs, alloc_ma, cisl, bg_ma, tag='soft', ss_m=1, ss_l=20.0,
                 load=True, t_off=150e-6, t_stop=250e-6):
    rload = f'RL VISL 0 {3.3 / (alloc_ma * 1e-3):.4g}\n' if load else ''
    t = header(corner, temp) + isw_cell('isw', nf, 'bodyswitch', ss_m, ss_l) + pdn(bg_ma).replace('{VS}', str(vs))
    t += (f'VEN EN 0 PWL(0 0 20u 0 20.01u {{VS}} {t_off} {{VS}} {t_off + 1e-8} 0)\n'.replace('{VS}', str(vs)) +
          f'XI VDD 0 VISLS EN ISO PG isw\nVM VISLS VISL 0\nCI VISL 0 {cisl}\n{rload}'
          f'.tran 20n {t_stop} 0 20n\n'
          '.control\nrun\n'
          'meas tran vdd_pre find v(vdd) at=19u\n'
          f'meas tran vdd_min min v(vdd) from=20u to={t_off}\n'
          f'meas tran vdd_final find v(vdd) at={t_off - 1e-6}\n'
          f'meas tran visl_final find v(visl) at={t_off - 1e-6}\n'
          f'meas tran i_peak max i(vm) from=20u to={t_off}\n'
          'let v90 = 0.9*visl_final\n'
          'meas tran t_on when v(visl)=v90 rise=1\n'
          'meas tran t_10 when v(visl)=0.1*visl_final rise=1\n'
          'meas tran t_pg when v(pg)=1.5 rise=1\n'
          'meas tran t_iso when v(iso)=1.5 fall=1\n'
          f'meas tran t_isooff when v(iso)=1.5 rise=1 from={t_off}\n'
          f'meas tran t_dis when v(visl)=0.3 fall=1 from={t_off}\n'
          'meas tran visl_max_pre max v(visl) from=0 to=19.9u\n'
          '.endc\n.end\n')
    return (f'tran_{tag}_{isl}_{corner}_{temp}_{vs}', t)


def isw_powerup_job(isl, nf, corner, temp, ramp, vfinal=3.63):
    """Ring ramps 0 -> vfinal with EN floating (only the internal pulldown defines it)."""
    t = header(corner, temp) + isw_cell('isw', nf)
    t += (f'VDD VDD 0 PWL(0 0 {ramp} {vfinal})\nXI VDD 0 VISL EN ISO PG isw\nCI VISL 0 150p\n'
          f'.tran 10n {ramp * 3}\n.control\nrun\nmeas tran visl_max max v(visl)\nmeas tran en_max max v(en)\n'
          f'meas tran iso_end find v(iso) at={ramp * 3 * 0.99}\nmeas tran visl_end find v(visl) at={ramp * 3 * 0.99}\n.endc\n.end\n')
    return (f'pwrup_{isl}_{corner}_{temp}_{ramp:g}', t)


# ---------------------------------------------------------------------------
# ATB
# ---------------------------------------------------------------------------

def atb_cells():
    txt = [OVERRIDE.get(n) or design.atb_tap_netlist(n) for n in design.ATB_VARIANTS]
    txt.append(OVERRIDE.get('atb_pad') or design.atb_pad_netlist())
    return ''.join(txt)


def load_pex(path, new_name, ports):
    """Rename an extracted subckt to the schematic name with the schematic pin order."""
    lines = Path(path).read_text().splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.lower().startswith('.subckt'))
    j = i + 1
    while j < len(lines) and lines[j].startswith('+'):
        j += 1
    pins = ' '.join(lines[i:j]).replace('+', ' ').split()[2:]
    if sorted(pins) != sorted(ports):
        raise ValueError(f'extracted pins {pins} != {ports}')
    body = [ln.replace('**FLOATING', '') for ln in lines[j:] if not ln.lower().startswith('.ends')]
    return '\n'.join([f'.subckt {new_name} ' + ' '.join(ports)] + body + [f'.ends {new_name}']) + '\n'


def atb_ron_job(cell, corner, temp, vdd, vsig):
    t = header(corner, temp) + atb_cells()
    t += (f'VDD VDD 0 {vdd}\nVSEL SEL 0 {vdd}\nVA A 0 {vsig}\nVB B 0 {vsig + 0.01}\n'
          f'XC A B SEL VDD 0 {cell}\n.control\nop\nlet ron = abs(0.01/i(vb))\nprint ron\n.endc\n.end\n')
    return (f'ron_{cell}_{corner}_{temp}_{vdd}_{vsig:.2f}', t)


def atb_offc_job(cell, corner, temp, vnode, vbus):
    t = header(corner, temp) + atb_cells()
    t += (f'VDD VDD 0 3.3\nVA A 0 DC {vnode} AC 1\nVB B 0 {vbus}\n'
          f'XC A B 0 VDD 0 {cell}\n.control\nac lin 1 1e6 1e6\n'
          'let cnode = -imag(i(va))/(2*3.14159265*1e6)\nprint cnode\n'
          'op\nlet ileak = -i(va)\nprint ileak\n.endc\n.end\n')
    return (f'offc_{cell}_{corner}_{temp}_{vnode}_{vbus}', t)


def atb_iso_job(cell, corner, temp):
    t = header(corner, temp) + atb_cells()
    t += ('VDD VDD 0 3.3\nVB B 0 DC 1.65 AC 1\nRN A 0 10k\n'
          f'XC A B 0 VDD 0 {cell}\n.control\nac dec 10 1e5 1e9\n'
          'meas ac iso_1meg find vdb(a) at=1e6\nmeas ac iso_10meg find vdb(a) at=1e7\n'
          'meas ac iso_100meg find vdb(a) at=1e8\n.endc\n.end\n')
    return (f'iso_{cell}_{corner}_{temp}', t)


# Minimum all-off gap the register file must insert between two non-zero
# ATB codes on one bus (commit rule: zero code first). Bare leaves rely on it.
ATB_GAP_SPEC_S = 20e-9


def atb_bbm_job(cell, corner, temp, vdd):
    """Two cells on one bus: A deselected at 50 ns, B selected at 50 ns (cells
    with internal break-before-make) or 50 ns + ATB_GAP_SPEC_S (bare leaves,
    which rely on the register-file gap)."""
    bare = cell in design.BARE_LEAVES
    gap = ATB_GAP_SPEC_S if bare else 0.0
    tb = 50e-9 + gap
    on_a, on_b = ('v(sa)', 'v(sb)') if bare else ('v(xa.tgon)', 'v(xb.tgon)')
    sh_a, sh_b = ('v(xa.swb)', 'v(xb.swb)') if bare else ('v(xa.shon)', 'v(xb.shon)')
    t = header(corner, temp) + atb_cells()
    t += (f'VDD VDD 0 {vdd}\n'
          f'VSA SA 0 PWL(0 {vdd} 50n {vdd} 50.1n 0)\nVSB SB 0 PWL(0 0 {tb} 0 {tb + 1e-10} {vdd})\n'
          'VN1 N1 0 0.5\nVN2 N2 0 2.5\nCB BUS 0 200f\n'
          f'XA N1 BUS SA VDD 0 {cell}\nXB N2 BUS SB VDD 0 {cell}\n'
          '.tran 5p 140n\n.control\nrun\n'
          f'meas tran a_off when {on_a}={vdd / 2} fall=1\n'
          f'meas tran b_on when {on_b}={vdd / 2} rise=1\n'
          f'meas tran b_shoff when {sh_b}={vdd / 2} fall=1\n'
          f'meas tran a_shon when {sh_a}={vdd / 2} rise=1\n'
          'let gap_ab = b_on - a_off\nprint gap_ab\nlet gap_b_internal = b_on - b_shoff\nprint gap_b_internal\n'
          'let gap_a_internal = a_shon - a_off\nprint gap_a_internal\n'
          f'meas tran bus_final find v(bus) at=138n\n'
          '.endc\n.end\n')
    return (f'bbm_{cell}_{corner}_{temp}_{vdd}', t)


def atb_glitch_job(cell, corner, temp, cnode):
    """Disturbance of a tapped bias node (1.2 V through 100 kohm, cnode to VSS)
    when its leaf opens and closes, with the bus held at 1.2 V through 10 kohm
    (the sense chain). This isolates the leaf's own TG/shunt overlap and gate
    charge injection from bus charge sharing."""
    t = header(corner, temp) + atb_cells()
    t += ('VDD VDD 0 3.3\nVS S 0 1.2\nRS S NODE 100k\n'
          f'CN NODE 0 {cnode}\nVB B 0 1.2\nRB B BUS 10k\nCB BUS 0 100f\n'
          'VSEL SEL 0 PWL(0 0 1u 0 1.0001u 3.3 3u 3.3 3.0001u 0)\n'
          f'XC NODE BUS SEL VDD 0 {cell}\n.tran 0.1n 6u\n.control\nrun\n'
          'meas tran on_min min v(node) from=0.99u to=2.9u\nmeas tran on_max max v(node) from=0.99u to=2.9u\n'
          'meas tran off_min min v(node) from=2.99u to=6u\nmeas tran off_max max v(node) from=2.99u to=6u\n'
          'let glitch_on = max(abs(on_min-1.2), abs(on_max-1.2))\nprint glitch_on\n'
          'let glitch_off = max(abs(off_min-1.2), abs(off_max-1.2))\nprint glitch_off\n.endc\n.end\n')
    return (f'glitch_{cell}_{corner}_{temp}_{cnode}', t)


def atb_pad_unpowered_job(corner, temp, vdd, vpad, sel):
    t = header(corner, temp) + atb_cells()
    t += (f'VDD VDD 0 {vdd}\nVSEL SEL 0 {sel}\nVP PAD 0 {vpad}\nRBUS BUS 0 1meg\n'
          'XC PAD BUS SEL VDD 0 atb_pad\n.control\nop\nlet i_pad = -i(vp)\nprint i_pad\n'
          'let i_ring = i(vdd)\nprint i_ring\nlet vbus = v(bus)\nprint vbus\n.endc\n.end\n')
    return (f'padov_{corner}_{temp}_{vdd}_{vpad}_{sel}', t)


def atb_forcesense_job(corner, temp):
    """Force 100 uA into a diode-connected NMOS bias node through the force chain
    (ATB0) and read it through the sense chain (ATB1) with a 10 Mohm meter."""
    t = header(corner, temp) + atb_cells()
    t += ('VDD VDD 0 3.3\n'
          'XDIO NODE NODE 0 0 nfet_03v3 w=10u l=1u\n'
          'XLF NODE LF VDD VDD 0 atb_leaf_f\nXGF LF GF VDD VDD 0 atb_grp\nXPF ATB0 GF VDD VDD 0 atb_pad\n'
          'XLS NODE LS VDD VDD 0 atb_leaf_s\nXGS LS GS VDD VDD 0 atb_grp\nXPS ATB1 GS VDD VDD 0 atb_pad\n'
          'IF 0 ATB0 100u\nRM ATB1 0 10meg\nCP0 ATB0 0 2p\nCP1 ATB1 0 2p\n'
          '.control\nop\nlet v_force_pad = v(atb0)\nprint v_force_pad\nlet v_node = v(node)\nprint v_node\n'
          'let v_sense_pad = v(atb1)\nprint v_sense_pad\nlet force_ir_error = v(atb0)-v(node)\nprint force_ir_error\n'
          'let sense_error = v(atb1)-v(node)\nprint sense_error\n.endc\n.end\n')
    return (f'fs_{corner}_{temp}', t)


def atb_settle_job(corner, temp):
    """Sense path step response: 10 kohm node at 1.2 V, leaf+group+pad, 2 pF pad
    + 10 pF bench load on ATB1, all other 11 leaves / 7 groups present and off."""
    t = header(corner, temp) + atb_cells()
    offleaves = ''.join(f'XOL{i} Z{i} LS 0 VDD 0 atb_leaf_s\nVZ{i} Z{i} 0 1.65\n' for i in range(11))
    offgrps = ''.join(f'XOG{i} Y{i} GS 0 VDD 0 atb_grp\nVY{i} Y{i} 0 1.65\n' for i in range(7))
    t += ('VDD VDD 0 3.3\nVSRC S 0 1.2\nRS S NODE 10k\n'
          'VSEL SEL 0 PWL(0 0 100n 0 100.1n 3.3)\n'
          'XLS NODE LS SEL VDD 0 atb_leaf_s\nXGS LS GS SEL VDD 0 atb_grp\nXPS ATB1 GS SEL VDD 0 atb_pad\n'
          + offleaves + offgrps +
          'CP ATB1 0 12p\n.tran 1n 3u\n.control\nrun\n'
          'meas tran t_settle when v(atb1)=1.188 rise=1\nmeas tran v_end find v(atb1) at=2.9u\n'
          'let settle_1pct = t_settle-100n\nprint settle_1pct\n.endc\n.end\n')
    return (f'settle_{corner}_{temp}', t)


# ---------------------------------------------------------------------------
# Envelope (spec/tapeout-plan.md "Operating envelope"):
#  function: tt/ss/ff x 22/32 C x 3.15/3.35 V at the die, plus tt/27 C/3.3 V
#  safety:   0..3.63 V ramps, brownout, repeated ramps, 0..85 C
#  exploratory only: -40/125 C, 3.0/3.6 V, fs/sf
F_POINTS = [('tt', 27, 3.3)] + [(c, t, v) for c in ('tt', 'ss', 'ff') for t in (22, 32) for v in (3.15, 3.35)]
X_POINTS = [(c, t, v) for c in CORNERS for t in (-40, 125) for v in (3.0, 3.6)]
S_TEMPS = [0, 27, 85]
S_CORNERS = ['tt', 'ss', 'ff']
VMAX_SAFE = 3.63


def _clean(v):
    return {k: x for k, x in v.items() if not k.startswith('_')}


def isw_backdrive_job(isl, nf, corner, temp, vdd, vpad, load_ohm, cisl):
    """Bench mishap reported by the rf_tx work: 3.3 V DC on the RF_TX pad feeds
    the island rail through the driver output junctions (~90 mA into a 0 V
    rail). Modeled as diode + 28 ohm from the pad to VISL, calibrated by the
    'rail held at 0 V' case (load_ohm=0). Island switch off (EN low)."""
    t = header(corner, temp) + isw_cell('isw', nf)
    load = ('VHOLD VISL 0 0\n' if load_ohm == 0 else
            (f'RL VISL 0 {load_ohm}\n' if load_ohm else ''))
    t += (f'.model DJ D(IS=1e-14 N=1)\nVDD VDD 0 {vdd}\nVEN EN 0 0\nVPAD PAD 0 {vpad}\n'
          f'DJ PAD PJ DJ\nRJ PJ VISL 28\nCI VISL 0 {cisl}\n{load}XI VDD 0 VISL EN ISO PG isw\n'
          '.control\nop\nlet i_pad = -i(vpad)\nprint i_pad\nlet i_into_ring = i(vdd)\nprint i_into_ring\n'
          'let visl_v = v(visl)\nprint visl_v\nlet pg_v = v(pg)\nprint pg_v\nlet iso_v = v(iso)\nprint iso_v\n.endc\n.end\n')
    return (f'bdrv_{isl}_{corner}_{temp}_{vdd}_{vpad}_{load_ohm}', t)


def isw_brownout_job(isl, nf, corner, temp, en_mode, vdip):
    """Ring 3.3 V -> vdip (10 us) -> 3.3 V, then 0 -> 3.63 V -> 0 twice (repeated ramps)."""
    en = 'VEN EN 0 0\n' if en_mode == 'low' else ('REN EN VDD 1\n' if en_mode == 'on' else '')
    t = header(corner, temp) + isw_cell('isw', nf)
    t += ('VDD VDD 0 PWL(0 0 5u 3.3 40u 3.3 41u {d} 51u {d} 52u 3.3 90u 3.3 92u 0 110u 0 112u 3.63 140u 3.63 '
          '142u 0 160u 0 162u 3.63 200u 3.63)\n').format(d=vdip)
    t += (f'{en}XI VDD 0 VISLS EN ISO PG isw\nVM VISLS VISL 0\nCI VISL 0 150p\nRL VISL 0 10k\n'
          '.tran 20n 200u 0 20n\n.control\nrun\n'
          'meas tran visl_max max v(visl)\nmeas tran i_rev_max min i(vm)\nmeas tran i_fwd_max max i(vm)\n'
          'meas tran visl_end find v(visl) at=199u\nmeas tran pg_end find v(pg) at=199u\n'
          'meas tran iso_end find v(iso) at=199u\nmeas tran visl_after_dip find v(visl) at=80u\n'
          'meas tran gate_end find v(xi.gate) at=199u\n.endc\n.end\n')
    return (f'brown_{isl}_{corner}_{temp}_{en_mode}_{vdip}', t)


def campaign(workers, quick=False):
    alloc, arch_path = design.island_allocations()
    char_nf = 200
    # Ron*W characterization over the functional points (sizing) and exploratory points.
    jobs = [isw_drop_job('char', char_nf, c, tc, v, 20) for c, tc, v in F_POINTS + X_POINTS]
    res = run_all(jobs, workers)
    ronw = {k: res[k]['drop'] / 20e-3 * char_nf * design.FINGER_W_UM for k in res if 'drop' in res[k]}
    fkeys = [f'drop_char_{c}_{t}_{v}' for c, t, v in F_POINTS]
    worst_key = max(fkeys, key=lambda k: ronw[k])
    ronw_worst = ronw[worst_key]
    sizes = {}
    for isl, a in alloc.items():
        nf = design.pass_fingers(a['design_current_ma'], ronw_worst)
        rows, per_row, _ = design.array_shape(nf)
        sizes[isl] = {'fingers': nf, 'w_um': nf * design.FINGER_W_UM, 'l_um': design.PASS_L_UM,
                      'array_rows': rows, 'fingers_per_row': per_row}
    out = {'architecture_source': arch_path, 'allocation': alloc,
           'envelope': {'functional_points': F_POINTS, 'exploratory_points': X_POINTS,
                        'safety_temps_c': S_TEMPS, 'safety_vmax_v': VMAX_SAFE},
           'sizing_rule': {'design_margin': design.DESIGN_MARGIN, 'drop_target_v': design.DROP_TARGET_V,
                           'ron_w_worst_functional_ohm_um': ronw_worst, 'worst_functional_point': worst_key,
                           'ron_w_tt_27_3v3_ohm_um': ronw.get('drop_char_tt_27_3.3'),
                           'ron_w_worst_exploratory_ohm_um': max(ronw.values())},
           'sizes': sizes}

    # --- drop at design current: functional points (gate) + exploratory (record)
    jobs = []
    for isl, a in alloc.items():
        for c, tc, v in F_POINTS + ([] if quick else X_POINTS):
            jobs.append(isw_drop_job(isl, sizes[isl]['fingers'], c, tc, v, a['design_current_ma']))
    res = run_all(jobs, workers)
    drop = {}
    for isl in alloc:
        fk = [f'drop_{isl}_{c}_{t}_{v}' for c, t, v in F_POINTS]
        xk = [k for k in res if k.startswith(f'drop_{isl}_') and k not in fk]
        fv = [res[k].get('drop') for k in fk]
        drop[isl] = {'design_current_ma': alloc[isl]['design_current_ma'],
                     'functional_cases': len(fk), 'functional_converged': sum(x is not None for x in fv),
                     'functional_drop_max_v': max(x for x in fv if x is not None),
                     'functional_worst': max(fk, key=lambda k: res[k].get('drop', 9)),
                     'functional_pass': all(x is not None and x <= design.DROP_TARGET_V + 1e-6 for x in fv),
                     'drop_tt_27_3v3_v': res[f'drop_{isl}_tt_27_3.3'].get('drop'),
                     'island_rail_min_at_3v15_v': min(float(k.split('_')[-1]) - res[k]['drop'] for k in fk if 'drop' in res[k]),
                     'pg_high_all_functional': all(res[k].get('pg', 0) > 0.9 * float(k.split('_')[-1]) for k in fk),
                     'iso_low_all_functional': all(res[k].get('iso', 9) < 0.1 for k in fk),
                     'on_quiescent_max_a': max(res[k].get('iq', float('nan')) for k in fk),
                     'exploratory_drop_max_v': max((res[k]['drop'] for k in xk if 'drop' in res[k]), default=None)}
    out['drop'] = drop

    # --- off leakage: safety temps at 3.63 V, plus 125 C exploratory
    jobs = []
    for isl in alloc:
        for c in S_CORNERS:
            for tc in S_TEMPS + [125]:
                jobs.append(isw_leak_job(isl, sizes[isl]['fingers'], c, tc, VMAX_SAFE))
            for tc in (22, 32):
                jobs.append(isw_leak_job(isl, sizes[isl]['fingers'], c, tc, 3.35))
    res = run_all(jobs, workers)
    leak = {}
    for isl in alloc:
        ks = [k for k in res if k.startswith(f'leak_bodyswitch_{isl}_')]
        func = [k for k in ks if k.endswith('_3.35')]
        saf = [k for k in ks if k.endswith(f'_{VMAX_SAFE}') and '_125_' not in k]
        leak[isl] = {'functional_max_a_3v35_22to32c': max(res[k]['ileak'] for k in func),
                     'tt_27c_3v63_a': res[f'leak_bodyswitch_{isl}_tt_27_{VMAX_SAFE}']['ileak'],
                     'safety_max_a_3v63_0to85c': max(res[k]['ileak'] for k in saf),
                     'exploratory_125c_max_a': max(res[k]['ileak'] for k in ks if '_125_' in k),
                     'cell_ring_current_off_max_a_0to85c': max(res[k]['ivdd'] for k in saf)}
    out['off_leakage'] = leak

    # --- reverse blocking (safety): variants compared at the wired size
    jobs = []
    pairs = [(3.3, 3.63), (0.0, 3.3), (0.0, 3.63), (3.15, 3.63), (1.5, 3.63)]
    for variant in ['bodyswitch', 'bodyvdd', 'b2b']:
        for isl in (['wired'] if variant != 'bodyswitch' else list(alloc)):
            for c in S_CORNERS:
                for tc in S_TEMPS:
                    for vdd, visl in pairs:
                        jobs.append(isw_reverse_job(isl, sizes[isl]['fingers'], c, tc, vdd, visl, variant))
    res = run_all(jobs, workers)
    rev = {}
    for variant in ['bodyswitch', 'bodyvdd', 'b2b']:
        for isl in alloc:
            ks = [k for k in res if k.startswith(f'rev_{variant}_{isl}_')]
            if not ks:
                continue
            cases = {k.split(f'rev_{variant}_{isl}_')[1]: {'i_into_ring_a': res[k].get('i_into_ring'),
                                                           'i_from_peer_a': res[k].get('i_from_peer')} for k in ks}
            rev[f'{variant}/{isl}'] = {
                'max_i_into_ring_a': max(v['i_into_ring_a'] for v in cases.values() if v['i_into_ring_a'] is not None),
                'max_i_from_peer_a': max(v['i_from_peer_a'] for v in cases.values() if v['i_from_peer_a'] is not None),
                'max_i_from_peer_ring_unpowered_a': max(v['i_from_peer_a'] for k, v in cases.items() if k.split('_')[2] == '0.0'),
                'cases': cases}
    out['reverse'] = rev

    # --- turn-on/off transients on the selected common-ring PDN
    tpoints = [('tt', 27, 3.3), ('ss', 22, 3.3), ('ss', 32, 3.3), ('ff', 22, 3.3), ('ff', 32, 3.3)]
    jobs = []
    bg = 130.0  # mA background on the ring (core + host allocations, RF/wired modes)
    for isl, a in alloc.items():
        for c, tc, vs in tpoints:
            jobs.append(isw_tran_job(isl, sizes[isl]['fingers'], c, tc, vs, a['peak_allocation_ma'],
                                     a['island_decap_f'], bg))
        jobs.append(isw_tran_job(isl, sizes[isl]['fingers'], 'tt', 27, 3.3, a['peak_allocation_ma'],
                                 a['island_decap_f'], bg, tag='abrupt', ss_m=40, ss_l=0.28))
        for c, tc in (('tt', 27), ('ss', 22)):
            jobs.append(isw_tran_job(isl, sizes[isl]['fingers'], c, tc, 3.3, a['peak_allocation_ma'],
                                     a['island_decap_f'], bg, tag='noload', load=False))
    res = run_all(jobs, workers)
    out['transient'] = {k: _clean(v) for k, v in res.items()}

    # --- safety: undefined control during 0 -> 3.63 V ramps; brownout and repeated ramps
    jobs = [isw_powerup_job(isl, sizes[isl]['fingers'], c, tc, r)
            for isl in alloc for c in S_CORNERS for tc in (0, 85) for r in (1e-6, 100e-6)]
    res = run_all(jobs, workers)
    out['powerup_en_floating'] = {k: _clean(v) for k, v in res.items()}
    jobs = [isw_brownout_job(isl, sizes[isl]['fingers'], c, tc, en, d)
            for isl in alloc for c, tc in (('tt', 0), ('ss', 85), ('ff', 85)) for en in ('float', 'on') for d in (1.0, 2.0)]
    res = run_all(jobs, workers)
    out['brownout_repeated_ramps'] = {k: _clean(v) for k, v in res.items()}

    # --- RF_TX pad back-drive into the off RF island (coordinator input from the rf_tx work)
    rl = round(3.3 / (alloc['rf']['peak_allocation_ma'] * 1e-3), 1)
    jobs = [isw_backdrive_job('rf', sizes['rf']['fingers'], c, tc, vdd, vp, ld, alloc['rf']['island_decap_f'])
            for c in S_CORNERS for tc in S_TEMPS for vdd in (0.0, 3.3) for vp in (3.3, 3.63)
            for ld in (0, None, rl)]
    res = run_all(jobs, workers)
    out['rf_tx_backdrive'] = {'model': 'PAD -> diode(IS=1e-14) -> 28 ohm -> VISL; switch off; load 0 = rail held at 0 V (calibration), None = decap only, '
                              f'{rl} ohm = RF island allocation as a resistor',
                              'cases': {k: _clean(v) for k, v in res.items()}}

    # --- ATB
    atb = {}
    cells = list(design.ATB_VARIANTS) + ['atb_pad']
    jobs = []
    for cell in cells:
        for c, tc, vdd in F_POINTS + ([] if quick else X_POINTS):
            for vs in [x * 0.15 for x in range(int(round(vdd / 0.15)) + 1)]:
                jobs.append(atb_ron_job(cell, c, tc, vdd, round(min(vs, vdd), 3)))
    res = run_all(jobs, workers)
    ron = {}
    for cell in cells:
        fset = {f'_{c}_{t}_{v}_' for c, t, v in F_POINTS}
        fk = [k for k in res if k.startswith(f'ron_{cell}_') and any(s_ in k for s_ in fset)]
        xk = [k for k in res if k.startswith(f'ron_{cell}_') and k not in fk]
        good = {k: res[k]['ron'] for k in fk if 'ron' in res[k]}
        wk = max(good, key=good.get)
        ron[cell] = {'functional_max_ohm': good[wk], 'functional_worst': wk, 'functional_cases': len(fk),
                     'functional_converged': len(good),
                     'tt_27_3v3_max_ohm': max(v for k, v in good.items() if '_tt_27_3.3_' in k),
                     'exploratory_max_ohm': max((res[k]['ron'] for k in xk if 'ron' in res[k]), default=None)}
    atb['ron'] = ron

    jobs = []
    for cell in design.ATB_VARIANTS:
        for c in S_CORNERS:
            for tc in (22, 32, 85):
                for vn in (0.0, 1.65, 3.35):
                    for vb in (0.0, 3.35):
                        jobs.append(atb_offc_job(cell, c, tc, vn, vb))
    res = run_all(jobs, workers)
    offc = {}
    for cell in design.ATB_VARIANTS:
        ks = [k for k in res if k.startswith(f'offc_{cell}_')]
        fk = [k for k in ks if '_85_' not in k]
        offc[cell] = {'c_max_f': max(res[k]['cnode'] for k in ks if 'cnode' in res[k]),
                      'c_min_f': min(res[k]['cnode'] for k in ks if 'cnode' in res[k]),
                      'c_tt_22_mid_f': res.get(f'offc_{cell}_tt_22_1.65_0.0', {}).get('cnode'),
                      'leak_abs_max_functional_a': max(abs(res[k]['ileak']) for k in fk if 'ileak' in res[k]),
                      'leak_abs_max_85c_a': max(abs(res[k]['ileak']) for k in ks if 'ileak' in res[k] and '_85_' in k),
                      'cases': len(ks)}
    atb['off_node_loading'] = offc

    jobs = [atb_iso_job(cell, c, tc) for cell in design.ATB_VARIANTS for c, tc in [('tt', 27), ('ff', 32)]]
    res = run_all(jobs, workers)
    atb['isolation_db_into_10k_node'] = {k: _clean(v) for k, v in res.items()}

    jobs = [atb_bbm_job(cell, c, tc, v) for cell in ['atb_leaf_s', 'atb_leaf_f', 'atb_grp', 'atb_pad']
            for c, tc, v in F_POINTS]
    res = run_all(jobs, workers)
    bbm = {}
    for cell in ['atb_leaf_s', 'atb_leaf_f', 'atb_grp', 'atb_pad']:
        ks = [k for k in res if k.startswith(f'bbm_{cell}_')]
        g = [res[k].get('gap_ab') for k in ks]
        gi = [res[k].get('gap_b_internal') for k in ks] + [res[k].get('gap_a_internal') for k in ks]
        bbm[cell] = {'cases': len(ks),
                     'min_gap_between_cells_s': min(g) if all(x is not None for x in g) else None,
                     'min_internal_shunt_tg_gap_s': min(gi) if all(x is not None for x in gi) else None}
    atb['break_before_make'] = bbm
    atb['break_before_make_gap_spec_s'] = ATB_GAP_SPEC_S
    jobs = [atb_glitch_job(cell, c, tc, cn) for cell in design.BARE_LEAVES
            for c, tc, _ in F_POINTS for cn in (1e-12, 10e-12)]
    res = run_all(jobs, workers)
    atb['select_glitch'] = {cell: {'max_on_v': max(res[k]['glitch_on'] for k in res if k.startswith(f'glitch_{cell}_') and 'glitch_on' in res[k]),
                                   'max_off_v': max(res[k]['glitch_off'] for k in res if k.startswith(f'glitch_{cell}_') and 'glitch_off' in res[k]),
                                   'cases': sum(1 for k in res if k.startswith(f'glitch_{cell}_')),
                                   'node': '1.2 V via 100 kohm with 1 pF or 10 pF; bus at 1.2 V via 10 kohm'}
                           for cell in design.BARE_LEAVES}

    jobs = [atb_pad_unpowered_job(c, tc, vdd, vp, 0.0) for c in S_CORNERS for tc in S_TEMPS
            for vdd, vp in [(0.0, VMAX_SAFE), (0.0, 3.3), (3.3, VMAX_SAFE), (3.15, VMAX_SAFE), (1.5, VMAX_SAFE), (3.3, -0.3)]]
    res = run_all(jobs, workers)
    pov = {k: _clean(v) for k, v in res.items()}
    atb['pad_overvoltage'] = {'cases': pov,
                              'max_abs_i_pad_a': max(abs(v['i_pad']) for v in pov.values()),
                              'max_abs_i_pad_positive_overdrive_a': max(abs(v['i_pad']) for k, v in pov.items() if not k.endswith('_-0.3_0.0')),
                              'max_abs_vbus_v': max(abs(v['vbus']) for v in pov.values())}

    jobs = [atb_forcesense_job(c, tc) for c, tc in [('tt', 27), ('ss', 32), ('ff', 22)]]
    jobs += [atb_settle_job(c, tc) for c, tc in [('tt', 27), ('ss', 32)]]
    res = run_all(jobs, workers)
    atb['force_sense'] = {k: _clean(v) for k, v in res.items() if k.startswith('fs_')}
    atb['sense_settling'] = {k: _clean(v) for k, v in res.items() if k.startswith('settle_')}
    out['atb'] = atb
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='/work/schematic-result.json')
    ap.add_argument('--workers', type=int, default=os.cpu_count() or 2)
    ap.add_argument('--quick', action='store_true')
    a = ap.parse_args()
    res = campaign(a.workers, a.quick)
    res['pdk_ngspice'] = {n: hashlib.sha256(Path(PDK_NG, n).read_bytes()).hexdigest()
                          for n in ('design.ngspice', 'sm141064.ngspice', 'sm141064.spice')}
    res['source_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted(Path(__file__).resolve().parent.glob('*.py'))}
    Path(a.out).write_text(json.dumps(res, indent=1, default=str))
    print('wrote', a.out)


if __name__ == '__main__':
    main()
