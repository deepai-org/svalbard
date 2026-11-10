#!/usr/bin/env python3
"""Tank inductor for the autonomous RF LO: geometry, physical model, FastHenry
cross-check, ngspice model and Magic layout (gf180mcuD, 5LM, 1.0 um Metal5).

gf180mcuD ships no inductor and no inductor model. This script derives one from
first principles and the PDK's own stack data, and states the uncertainty.

Geometry (one inductor; the quadrature VCO uses two)
  Square single-ended spiral used differentially: terminal A on the outer turn,
  n turns inward, centre end returned to terminal B by an underpass (Metal2 ||
  Metal1) that crosses all turns. Turns are Metal5 || Metal4 || Metal3, joined by
  via arrays at every corner. Manhattan only, so Magic DRC applies directly.
  The same geometry is used by the closed-form model, by FastHenry and by the
  layout generator (one polyline, `centerline()`).

Process data (Magic tech file gf180mcuD.tech, `extract` style ngspice, typ;
min/max in the (lrlc)/(hrhc) variants):
  layer   bottom z (um)  thickness (um)  sheet (mOhm/sq) typ [min..max]
  Metal1  1.23           0.55            90
  Metal2  2.38           0.55            90
  Metal3  3.53           0.55            90
  Metal4  4.68           0.55            90 [76..104]
  Metal5  5.83           1.0025          40 [31..49]
  via3/via4 contact 4.5 ohm per cut (typ)
  IMD treated as SiO2, eps_r 3.9 (tech-file C values imply eps_r ~3.9-4.2).

Physical model (single-pi, Yue & Wong, IEEE TED 47(3) 2000 [2]):
  Ls  Mohan modified Wheeler, square K1=2.34 K2=2.75 [1]  (cross-checked by
      FastHenry partial-inductance extraction of the drawn polyline)
  Rs  DC from parallel sheets; skin factor t/(delta(1-exp(-t/delta))) per layer;
      current crowding (proximity of inner turns) factor 1.3 [3]; underpass and
      vias added. FastHenry gives R(f) with filament discretisation, which
      contains skin and proximity on the drawn cross-section; the model uses the
      larger of the two.
  Cs  underpass overlap (M2 under turns, dielectric M2 top -> M3 bottom 0.6 um)
  Cox metal-to-substrate, parallel plate to the lowest strap layer (Metal3,
      3.53 um) x 1.15 fringe factor.
  Rsi/Csi  substrate: Gsub/Csub per unit area (Yue [2]: Gsub ~ 1e-7 S/um^2,
      Csub ~ 1e-3..7e-3 fF/um^2 for 10-20 ohm.cm p-sub). gf180mcuD does not publish
      the substrate resistivity; MCU-class wafers are 8-20 ohm.cm p-type. The
      nominal uses Gsub 4e-8 S/um^2, Csub 6e-3 fF/um^2, and the "low-Q" corner uses
      the worst substrate (loss resistance at its minimum ~ factor 3) together
      with Rs +50 %.

References
  [1] Mohan et al., JSSC 34(10) 1999.  [2] Yue, Wong, TED 47(3) 2000.
  [3] Kuhn, Ibrahim, TMTT 49(1) 2001.  [4] FastHenry 3 (Kamon, Tsuk, White).
"""
import json
import math
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MU0 = 4e-7 * math.pi
EPS0 = 8.854e-12
ANALOG_IMAGE = 'docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3'
DIGITAL_IMAGE = 'svalbard/librelane-gf180-canary:2026.08'

G = dict(turns=3, width_um=25.0, space_um=2.5, dout_um=300.0, under_w_um=12.0, f_hz=2.45e9,
         strap=['metal5', 'metal4', 'metal3'], underpass=['metal2', 'metal1'])
STACK = dict(metal1=(1.23, 0.55, 0.090), metal2=(2.38, 0.55, 0.090), metal3=(3.53, 0.55, 0.090),
             metal4=(4.68, 0.55, 0.090), metal5=(5.83, 1.0025, 0.040))
SUB = dict(nominal=dict(gsub=4e-8, csub=6e-3), worst=dict(gsub=1.2e-7, csub=2e-3), best=dict(gsub=1.3e-8, csub=1.8e-2))
CROWD = 1.3
VIA_OHM = 0.3      # vias + underpass contacts, lumped


def centerline(g=G):
    """Square spiral centre line, outer start (A) at the left of the bottom edge,
    clockwise inward. Returns list of (x, y) in um, origin at the spiral centre."""
    n, w, s, d = g['turns'], g['width_um'], g['space_um'], g['dout_um']
    p = w + s
    h = d / 2 - w / 2                      # half side of the outer turn centre line
    pts = [(-h - 20.0, -h), (-h, -h)]      # lead-in from the left
    for k in range(n):
        a = h - k * p
        pts += [(-a, a), (a, a), (a, -a)]
        pts.append((-(a - p), -a) if k < n - 1 else (0.0, -a))
    # remove consecutive duplicates
    out = [pts[0]]
    for q in pts[1:]:
        if q != out[-1]:
            out.append(q)
    return out


def geometry(g=G):
    pts = centerline(g)
    length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
    n, w, s, d = g['turns'], g['width_um'], g['space_um'], g['dout_um']
    din = d - 2 * n * w - 2 * (n - 1) * s
    return pts, length, din


def analytic(g=G, sub='nominal', rs_scale=1.0, l_scale=1.0, f=None):
    f = f or g['f_hz']
    w0 = 2 * math.pi * f
    pts, length, din = geometry(g)
    n, w, d = g['turns'], g['width_um'], g['dout_um']
    davg = (d + din) / 2
    rho = (d - din) / (d + din)
    L = 2.34 * MU0 * n ** 2 * davg * 1e-6 / (1 + 2.75 * rho) * l_scale
    gpar = 0.0
    for lay in g['strap']:
        z, t, rsh = STACK[lay]
        delta = math.sqrt(rsh * t * 1e-6 / (math.pi * f * MU0)) * 1e6
        skin = t / (delta * (1 - math.exp(-t / delta)))
        gpar += 1 / (rsh * skin)
    r_turns = (1 / gpar) * length / w * CROWD
    under_len = d / 2 + 20
    gu = sum(1 / STACK[l][2] for l in g['underpass'])
    r_under = under_len / g['under_w_um'] / gu
    rs = (r_turns + r_under + VIA_OHM) * rs_scale
    rdc = (1 / sum(1 / STACK[l][2] for l in g['strap'])) * length / w + r_under + VIA_OHM
    zlow = min(STACK[l][0] for l in g['strap'])
    area = length * w
    cox = 3.9 * EPS0 * area * 1e-12 / (zlow * 1e-6) * 1.15
    zu_top = max(STACK[l][0] + STACK[l][1] for l in g['underpass'])
    cs = n * g['under_w_um'] * w * 1e-12 * 3.9 * EPS0 / ((zlow - zu_top) * 1e-6)
    sp = SUB[sub]
    csi = sp['csub'] * 1e-15 * area
    rsi = 1 / (sp['gsub'] * area)
    # per terminal: Cox/2 in series with (2 Rsi || Csi/2)
    zsub = 1 / (1 / (2 * rsi) + 1j * w0 * csi / 2) + 1 / (1j * w0 * cox / 2)
    yt = 1 / zsub
    rp_shunt = 1 / yt.real
    rp_series = (w0 * L) ** 2 / rs
    rp_diff = 1 / (1 / rp_series + 1 / (2 * rp_shunt))
    return dict(L_nH=L * 1e9, Rs_ohm=rs, Rdc_ohm=rdc, R_turns_ohm=r_turns, R_underpass_ohm=r_under,
                length_um=length, din_um=din, metal_area_um2=area, footprint_um2=(d + 40) * d,
                Cox_total_fF=cox * 1e15, Cs_fF=cs * 1e15, Csi_total_fF=csi * 1e15, Rsi_total_ohm=rsi,
                shunt_per_terminal_ohm=rp_shunt, shunt_per_terminal_fF=yt.imag / w0 * 1e15,
                Q_series=w0 * L / rs, Rp_diff_ohm=rp_diff, Q_eff=rp_diff / (w0 * L), substrate=sub,
                rs_scale=rs_scale, l_scale=l_scale, f_hz=f)


# ------------------------------------------------------------------ FastHenry
def fasthenry_input(g=G, freqs=(1e9, 2.45e9, 4.9e9)):
    pts, _, _ = geometry(g)
    w = g['width_um']
    L = ['* pt_spiral FastHenry model (lcvco/spiral.py)', '.units um', '.default sigma=2.5e7']
    nodes = []
    for lay in g['strap']:
        z, t, rsh = STACK[lay]
        sig = 1 / (rsh * t)   # S per um (FastHenry units um)
        for i, (x, y) in enumerate(pts):
            L.append(f'N{lay}_{i} x={x:.3f} y={y:.3f} z={z + t / 2:.4f}')
        for i in range(len(pts) - 1):
            nw = 5 if lay == 'metal5' else 3
            L.append(f'E{lay}_{i} N{lay}_{i} N{lay}_{i + 1} w={w} h={t} sigma={sig:.4e} nwinc={nw} nhinc=2')
        nodes.append(lay)
    # vias at every corner: tie strap layers together
    for i in range(len(pts)):
        L.append('.equiv ' + ' '.join(f'N{l}_{i}' for l in g['strap']))
    # underpass: from the centre end straight down (-y) past the outer turn, on metal2 || metal1
    xe, ye = pts[-1]
    yb = -g['dout_um'] / 2 - 20.0
    for lay in g['underpass']:
        z, t, rsh = STACK[lay]
        sig = 1 / (rsh * t)   # S per um (FastHenry units um)
        L.append(f'NU{lay}_0 x={xe:.3f} y={ye:.3f} z={z + t / 2:.4f}')
        L.append(f'NU{lay}_1 x={xe:.3f} y={yb:.3f} z={z + t / 2:.4f}')
        L.append(f'EU{lay} NU{lay}_0 NU{lay}_1 w={g["under_w_um"]} h={t} sigma={sig:.4e} nwinc=3 nhinc=2')
    L.append(f'.equiv N{g["strap"][0]}_{len(pts) - 1} ' + ' '.join(f'NU{l}_0' for l in g['underpass']))
    L.append('.equiv ' + ' '.join(f'NU{l}_1' for l in g['underpass']))
    L.append(f'.external N{g["strap"][0]}_0 NU{g["underpass"][0]}_1')
    L.append(f'.freq fmin={min(freqs):g} fmax={max(freqs):g} ndec=10')
    L.append('.end')
    return '\n'.join(L) + '\n'


def fasthenry(g=G, work=None):
    work = Path(work or (HERE.parents[4] / 'scratch' / 'timing' / 'lcvco' / 'fasthenry'))
    work.mkdir(parents=True, exist_ok=True)
    (work / 'spiral.inp').write_text(fasthenry_input(g))
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '6g', '--entrypoint', '/bin/bash',
           '-v', f'{work}:/work', '-w', '/work', ANALOG_IMAGE, '-lc', 'fasthenry spiral.inp > fh.log 2>&1']
    subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    txt = (work / 'Zc.mat').read_text() if (work / 'Zc.mat').exists() else ''
    res = []
    for blk in re.finditer(r'Impedance matrix for frequency = ([0-9.eE+-]+)\s+1 x 1\s+([-0-9.eE+]+)\s+([-+0-9.eE]+)j', txt):
        f, re_, im = map(float, blk.groups())
        res.append(dict(f_hz=f, R_ohm=re_, L_nH=im / (2 * math.pi * f) * 1e9, Q=im / re_))
    return dict(points=res, log_tail=(work / 'fh.log').read_text()[-400:] if (work / 'fh.log').exists() else None)


def interp(points, f):
    pts = sorted(points, key=lambda p: p['f_hz'])
    for a, b in zip(pts, pts[1:]):
        if a['f_hz'] <= f <= b['f_hz']:
            t = (math.log(f) - math.log(a['f_hz'])) / (math.log(b['f_hz']) - math.log(a['f_hz']))
            return {k: a[k] + t * (b[k] - a[k]) for k in ('R_ohm', 'L_nH')}
    return None


# ------------------------------------------------------------------ spice
def subckt(name, m, note):
    return '\n'.join([
        f'* {name}: {note}',
        f'* L={m["L_nH"]:.3f} nH, Rs={m["Rs_ohm"]:.2f} ohm, Q_series={m["Q_series"]:.1f}, Q_eff={m["Q_eff"]:.1f} '
        f'@ {m["f_hz"] / 1e9:g} GHz, substrate {m["substrate"]}',
        f'.subckt {name} A B VSS',
        f'LS A M {m["L_nH"]:.4f}n', f'RS M B {m["Rs_ohm"]:.4f}', f'CS A B {m["Cs_fF"]:.3f}f',
        f'COXA A SA {m["Cox_total_fF"] / 2:.3f}f', f'COXB B SB {m["Cox_total_fF"] / 2:.3f}f',
        f'RSIA SA VSS {2 * m["Rsi_total_ohm"]:.2f}', f'RSIB SB VSS {2 * m["Rsi_total_ohm"]:.2f}',
        f'CSIA SA VSS {m["Csi_total_fF"] / 2:.4f}f', f'CSIB SB VSS {m["Csi_total_fF"] / 2:.4f}f',
        f'.ends {name}', ''])


# L scales are relative to the Mohan value; nominal is set to the FastHenry
# extraction of the drawn polyline (0.91 x Mohan, i.e. 2.65 nH), and +-10 % of that
# spans both FastHenry and Mohan.
L_NOM = 0.91
VARIANTS = {
    # name: (substrate, Rs scale, L scale)
    'pt_spiral': ('nominal', 1.0, L_NOM),
    'pt_spiral_lowq': ('worst', 1.5, L_NOM),
    'pt_spiral_lhi': ('nominal', 1.0, L_NOM * 1.10),
    'pt_spiral_llo': ('nominal', 1.0, L_NOM * 0.90),
    'pt_spiral_lhi_lowq': ('worst', 1.5, L_NOM * 1.10),
    'pt_spiral_llo_lowq': ('worst', 1.5, L_NOM * 0.90),
}


# ------------------------------------------------------------------ layout
def layout_tcl(g=G, cell='pt_spiral_ind'):
    pts, _, _ = geometry(g)
    w = g['width_um']
    hw = w / 2
    cmds = ['crashbackups stop', f'load {cell}', 'snap internal', 'units microns']

    def rect(layer, x1, y1, x2, y2):
        x1, x2 = sorted((x1, x2))
        y1, y2 = sorted((y1, y2))
        cmds.extend([f'box {x1:.3f}um {y1:.3f}um {x2:.3f}um {y2:.3f}um', f'paint {layer}'])

    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        for lay in g['strap']:
            rect(lay, min(x1, x2) - hw, min(y1, y2) - hw, max(x1, x2) + hw, max(y1, y2) + hw)
    # via arrays at every corner (strap layers); Magic generates the cuts from via4/via3 areas
    for (x, y) in pts:
        a = hw - 1.0
        rect('via4', x - a, y - a, x + a, y + a)
        rect('via3', x - a, y - a, x + a, y + a)
    # underpass: centre end down to below the outer turn, metal2 || metal1 joined by via1 at both ends
    xe, ye = pts[-1]
    yb = -g['dout_um'] / 2 - 20.0
    uh = g['under_w_um'] / 2
    for lay in ('metal2', 'metal1'):
        rect(lay, xe - uh, yb - uh, xe + uh, ye + uh)
    a = uh - 1.0
    for (yy) in (ye, yb):
        rect('via1', xe - a, yy - a, xe + a, yy + a)
    rect('via2', xe - a, ye - a, xe + a, ye + a)          # metal2 -> metal3 at the centre end
    # terminal B landing: metal2 -> metal3 -> metal4 -> metal5 below the spiral
    for lay in ('metal3', 'metal4', 'metal5'):
        rect(lay, xe - uh, yb - uh, xe + uh, yb + uh)
    for v in ('via2', 'via3', 'via4'):
        rect(v, xe - a, yb - a, xe + a, yb + a)
    x0, y0 = pts[0]
    cmds += [f'box {x0 - hw:.3f}um {y0 - hw:.3f}um {x0 + hw:.3f}um {y0 + hw:.3f}um',
             'label A FreeSans 1 0 0 0 c metal5', 'port make 1',
             f'box {xe - uh:.3f}um {yb - uh:.3f}um {xe + uh:.3f}um {yb + uh:.3f}um',
             'label B FreeSans 1 0 0 0 c metal5', 'port make 2',
             'select top cell', 'save', 'drc catchup', 'drc check', 'drc catchup',
             'set f [open drc.txt w]', 'puts $f [drc list count total]', 'puts $f [drc listall why]', 'close $f',
             'extract all', 'ext2spice lvs', 'ext2spice', 'gds write ' + cell, 'quit -noprompt']
    return '\n'.join(cmds) + '\n'


def layout(g=G):
    work = HERE.parents[4] / 'scratch' / 'timing' / 'lcvco' / 'layout'
    work.mkdir(parents=True, exist_ok=True)
    (work / 'spiral.tcl').write_text(layout_tcl(g))
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '6g', '--entrypoint', '/bin/sh',
           '--mount', f'type=bind,src={work},dst=/work', '-w', '/work', DIGITAL_IMAGE, '-c',
           'magic -dnull -noconsole -rcfile /pdk/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc /work/spiral.tcl > magic.log 2>&1']
    subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    drc = (work / 'drc.txt').read_text() if (work / 'drc.txt').exists() else 'missing'
    first = drc.split('\n', 1)[0].strip()
    return dict(drc_count=int(first) if first.isdigit() else first, drc_report=drc[:2000], work=str(work),
                gds=(work / 'pt_spiral_ind.gds').exists())


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else 'model'
    rec_p = HERE / 'spiral.json'
    rec = json.loads(rec_p.read_text()) if rec_p.exists() and what != 'model' else {}
    if what in ('model', 'all'):
        rec = dict(geometry=G, stack=STACK, substrate_params=SUB, crowding=CROWD, via_ohm=VIA_OHM,
                   variants={k: analytic(G, *v) for k, v in VARIANTS.items()},
                   at_4p9ghz=analytic(G, f=4.9e9))
    if what in ('fasthenry', 'all'):
        fh = fasthenry(G)
        rec['fasthenry'] = fh
        p = interp(fh['points'], G['f_hz']) if fh['points'] else None
        if p:
            a = rec['variants']['pt_spiral']
            rec['fasthenry_vs_model'] = dict(L_ratio=p['L_nH'] / a['L_nH'], R_ratio=p['R_ohm'] / a['Rs_ohm'],
                                             fasthenry_at_f=p)
    if what in ('layout', 'all'):
        rec['layout'] = layout(G)
    rec['uncertainty'] = dict(
        L='+-10 %: Mohan quotes 2-3 % vs field solvers; FastHenry (partial inductance of the drawn polyline, '
          'no substrate eddy currents) cross-checks it; the lead-in, the underpass return and the neighbouring QVCO '
          'inductor are not in the closed form. Bounded by variants pt_spiral_lhi/llo.',
        Rs='-20 %/+50 % (crowding factor and vias); bounded by the low-Q variants (x1.5).',
        substrate='Gsub x3 / Csub /3 (worst) vs nominal: substrate resistivity is not published for gf180mcuD.',
        Q='Q_eff spans the nominal and the low-Q variants; the design must start and cover the band with low-Q.')
    rec_p.write_text(json.dumps(rec, indent=1) + '\n')
    sp = ['* Tank inductor models for the autonomous RF LO, generated by lcvco/spiral.py; see spiral.json.',
          '* NOT EM-verified against silicon: closed-form L/R cross-checked with FastHenry; substrate per Yue & Wong.', '']
    for k, v in VARIANTS.items():
        sp.append(subckt(k, analytic(G, *v), f'variant {v}'))
    (HERE / 'spiral.spice').write_text('\n'.join(sp))
    print(json.dumps({k: {kk: round(vv, 3) for kk, vv in v.items() if isinstance(vv, float)}
                      for k, v in rec['variants'].items()}, indent=0))
    for k in ('fasthenry_vs_model', 'layout'):
        if k in rec:
            print(k, json.dumps(rec[k], default=str)[:1500])


if __name__ == '__main__':
    main()
