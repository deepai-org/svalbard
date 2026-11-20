"""Full-pessimistic corners per spec/design-assumptions.md (LO owner r5):
  spiral Q = 4 at 2.45 GHz (rows 'Spiral Q'), L +10 % / -10 % (two-sided), MIM series R 5 ohm, varactor Q = 8,
  parasitic C x1.15 / x0.90, ss/32/3.15 and ff/22/3.35.
Patches run_qvco_r5_ext: CORNERS += PFULL (ss, L+10 %, Q4) and PFULLLO (ss, L-10 %, Q4), spiral variants made by
scaling the series R of the *_lowq models until Q_eff(diff) = 4.0 at 2.45 GHz."""
import math, re, sys
import numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/timing/lcvco')
import run_qvco_r5_ext as rx
import run_lcvco as rl
SRC = (rx.HERE / 'spiral.spice').read_text()


def block(name):
    return re.search(rf'(\* {name}:.*?\.ends {name}\n)', SRC, re.S).group(1)


def zdiff(b, f, rs_scale=1.0):
    v = {k: float(re.search(rf'^{k} \S+ \S+ ([0-9.e+-]+)', b, re.M).group(1).rstrip('nf')) for k in ('LS', 'RS', 'CS', 'COXA', 'RSIA', 'CSIA')}
    w = 2 * math.pi * f
    zs = 1j * w * v['LS'] * 1e-9 + v['RS'] * rs_scale
    ys = 1 / zs + 1j * w * v['CS'] * 1e-15
    zsh = 1 / (1j * w * v['COXA'] * 1e-15) + 1 / (1 / v['RSIA'] + 1j * w * v['CSIA'] * 1e-15)
    # diff: series branch || (two shunts in series)
    y = ys + 1 / (2 * zsh)
    z = 1 / y
    return z.imag / z.real


def q4(name, newname, qt=4.0, f=2.45e9):
    b = block(name)
    lo, hi = 1.0, 5.0
    for _ in range(60):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if zdiff(b, f, m) > qt else (lo, m)
    rs = float(re.search(r'^RS M B (\S+)', b, re.M).group(1)) * m
    nb = re.sub(r'^RS M B \S+', f'RS M B {rs:.4f}', b, flags=re.M).replace(name, newname)
    return nb, m, zdiff(b, f, 1.0)


def lscaled(name, scale):
    b = block(name)
    ls = float(re.search(r'^LS A M (\S+)n', b, re.M).group(1))
    return re.sub(r'^LS A M \S+', f'LS A M {ls * scale:.4f}n', b, flags=re.M)


VAR = {}
for base, new in (('pt_spiral_lhi_lowq', 'pt_spiral_lhi_q4'), ('pt_spiral_llo_lowq', 'pt_spiral_llo_q4')):
    nb, m, q0 = q4(base, new)
    VAR[new] = nb
    VAR[new + '_info'] = dict(base=base, q_eff_base=q0, rs_scale=m)
SRC += lscaled('pt_spiral_llo', 0.85 / 0.90).replace('pt_spiral_llo', 'pt_spiral_l85')
VAR['pt_spiral_l85'] = block('pt_spiral_l85')
# design-assumptions pessimistic L is +-15 % (rows 'Spiral inductor L'): L x1.15 / x0.85 of nominal, Q = 4
SRC += lscaled('pt_spiral_lhi_lowq', 1.15 / 1.10).replace('pt_spiral_lhi_lowq', 'pt_spiral_l115_lowq')
SRC += lscaled('pt_spiral_llo_lowq', 0.85 / 0.90).replace('pt_spiral_llo_lowq', 'pt_spiral_l85_lowq')
for base, new in (('pt_spiral_l115_lowq', 'pt_spiral_l115_q4'), ('pt_spiral_l85_lowq', 'pt_spiral_l85_q4')):
    nb, m, q0 = q4(base, new)
    VAR[new] = nb
    VAR[new + '_info'] = dict(base=base, q_eff_base=q0, rs_scale=m)

_orig = rl.spiral_file


def spiral_file(variant):
    if variant in VAR:
        out = re.sub(rf'\b{variant}\b', 'pt_spiral', VAR[variant])
        p = rl.WORK / f'spiral_{variant}.spice'
        p.write_text(out)
        return p.name
    return _orig(variant)


rl.spiral_file = spiral_file
# varactor Q 8 needs ~R_side = Xc/8; MIM 5 ohm -> rser 5 (processed() puts rser/2 on each MIM plate path and rser
# per side on the varactor); the extra varactor R to reach Q 8 is added via RVW_EXTRA per finger.
rx.CORNERS['PFULL'] = dict(corner='ss', temp=32, v=3.15, spiral='pt_spiral_lhi_q4', cw=1.15, rser=5.0)
rx.CORNERS['PFULLLO'] = dict(corner='ss', temp=32, v=3.15, spiral='pt_spiral_llo_q4', cw=0.90, rser=5.0)
rx.CORNERS['PF115'] = dict(corner='ss', temp=32, v=3.15, spiral='pt_spiral_l115_q4', cw=1.15, rser=5.0)
rx.CORNERS['PF85'] = dict(corner='ss', temp=32, v=3.15, spiral='pt_spiral_l85_q4', cw=0.90, rser=5.0)
rx.CORNERS['OF85'] = dict(corner='ff', temp=22, v=3.35, spiral='pt_spiral_l85_q4', cw=0.90, rser=5.0)
rx.CORNERS['OPT85'] = dict(corner='ff', temp=22, v=3.35, spiral='pt_spiral_l85', cw=0.90, rser=0.0)
rx.CORNERS['OFULL'] = dict(corner='ff', temp=22, v=3.35, spiral='pt_spiral_llo_q4', cw=0.90, rser=5.0)

if __name__ == '__main__':
    for k, v in VAR.items():
        if k.endswith('_info'):
            print(k, v)

_proc = rx.processed


def processed(rfwork, kind, cw, rser):
    """rser 5 (full-pessimistic) -> varactor finger R raised so the varactor Q = 8 (279 ohm/finger total, 17 per side)."""
    old = rx.RVW
    rx.RVW = 280.0 - 17 * rser if rser >= 5 else old
    try:
        return _proc(rfwork, kind, cw, rser)
    finally:
        rx.RVW = old


rx.processed = processed
# 2026-11-20 divider envelope: ff weakest tank (L-15 %, Q 4, MIM/varactor +5 ohm) at the low supply 3.15 V
rx.CORNERS['FFW85'] = dict(corner='ff', temp=22, v=3.15, spiral='pt_spiral_l85_q4', cw=0.90, rser=5.0)
# 2026-11-20 range fix: sf / fs process corners (MOS skewed; MIM, MOS-cap and resistor typical: the PDK has no
# skewed MIM/MOS-cap libraries for them), nominal spiral
import run_lcvco as _rlc
_hdr0 = _rlc.hdr
def _hdr(corner, temp):
    if corner in ('sf', 'fs'):
        return (_rlc.tf.header(corner, temp) + f'.lib {_rlc.tf.MODELS}/sm141064.ngspice mimcap_typical\n'
                f'.lib {_rlc.tf.MODELS}/sm141064.ngspice moscap_typical\n')
    return _hdr0(corner, temp)
_rlc.hdr = _hdr
rx.CORNERS['SF'] = dict(corner='sf', temp=27, v=3.3, spiral='pt_spiral', cw=1.0, rser=0.0)
rx.CORNERS['FS'] = dict(corner='fs', temp=27, v=3.3, spiral='pt_spiral', cw=1.0, rser=0.0)
