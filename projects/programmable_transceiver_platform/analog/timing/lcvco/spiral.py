#!/usr/bin/env python3
"""Analytical model of the LC-VCO tank inductor (P3-4 evaluation).

gf180mcuD has no inductor model or EM-qualified inductor.  This script builds a
lumped single-pi model of a symmetric differential octagonal spiral from
documented closed-form expressions and writes it as an ngspice subcircuit
(`pt_spiral A B VSS`) plus a JSON record of every input, intermediate value
and the stated uncertainty.  It is an estimate, not a substitute for EM
simulation (e.g. FastHenry/ASITIC/openEMS) before tapeout.

References
  [1] S. S. Mohan et al., "Simple accurate expressions for planar spiral
      inductances", IEEE JSSC 34(10), 1999: modified Wheeler formula
      L = K1 mu0 n^2 d_avg / (1 + K2 rho); octagon K1 = 2.25, K2 = 3.55
      (quoted accuracy ~2-3 % against field solvers for typical geometries).
  [2] C. P. Yue, S. S. Wong, "Physical modeling of spiral inductors on
      silicon", IEEE TED 47(3), 2000: single-pi model (Ls, Rs, Cs, Cox, Rsi, Csi).
  [3] W. B. Kuhn, N. M. Ibrahim, "Analysis of current crowding effects in
      multiturn spiral inductors", IEEE TMTT 49(1), 2001.
Process data (gf180mcuD Magic tech file, `extract` section):
  Metal5 sheet 40 mOhm/sq, thickness 1.0 um, bottom 5.83 um above substrate;
  Metal4 sheet 90 mOhm/sq, 0.55 um, bottom 4.68 um; M4-M5 dielectric 0.60 um.
"""
import json, math, sys
from pathlib import Path

MU0 = 4e-7 * math.pi
EPS_OX = 3.9 * 8.854e-12
EPS_SI = 11.9 * 8.854e-12

G = dict(shape='octagon', turns=2, width_um=20.0, space_um=2.0, dout_um=400.0,
         strap='Metal5 with Metal4 strapped in parallel (M4 also forms the crossover)',
         f_hz=2.45e9)
P = dict(m5_sheet=0.040, m5_t_um=1.0, m4_sheet=0.090, m4_t_um=0.55, h_m4_um=4.68, t_m45_um=0.60,
         # substrate (Yue [2] style, lumped per unit spiral area); p-sub ~10 ohm.cm assumed
         gsub_s_per_um2=4.0e-8, csub_f_per_um2=0.006e-15,
         crowding_factor=1.3, via_and_underpass_ohm=0.3)

def model(g=G, p=P):
    n, w, s, dout = g['turns'], g['width_um'], g['space_um'], g['dout_um']
    din = dout - 2 * n * w - 2 * (n - 1) * s
    davg = (dout + din) / 2
    rho = (dout - din) / (dout + din)
    K1, K2 = 2.25, 3.55
    L = K1 * MU0 * n ** 2 * davg * 1e-6 / (1 + K2 * rho)
    length_um = n * 8 * math.tan(math.pi / 8) * davg          # centre-line length
    area_um2 = length_um * w
    rsh = 1 / (1 / p['m5_sheet'] + 1 / p['m4_sheet'])          # strapped M5 || M4
    rdc = rsh * length_um / w + p['via_and_underpass_ohm']
    # skin effect on the thicker (M5) conductor, rho = sheet * t
    rho_al = p['m5_sheet'] * p['m5_t_um'] * 1e-6
    delta_um = math.sqrt(rho_al / (math.pi * g['f_hz'] * MU0)) * 1e6
    t = p['m5_t_um']
    skin = t / (delta_um * (1 - math.exp(-t / delta_um)))
    rac = (rdc - p['via_and_underpass_ohm']) * skin * p['crowding_factor'] + p['via_and_underpass_ohm']
    cox = EPS_OX * area_um2 * 1e-12 / (p['h_m4_um'] * 1e-6)    # total, to the substrate surface
    cs = n * w ** 2 * 1e-12 * EPS_OX / (p['t_m45_um'] * 1e-6)    # crossover overlap
    csi = p['csub_f_per_um2'] * area_um2
    rsi = 1 / (p['gsub_s_per_um2'] * area_um2)
    w0 = 2 * math.pi * g['f_hz']
    q_series = w0 * L / rac
    # effective Q including the substrate branch (each terminal: Cox/2 in series with Rsi*2 || Csi/2)
    zsub = 1 / (1 / (2 * rsi) + 1j * w0 * csi / 2) + 1 / (1j * w0 * cox / 2)
    yt = 1 / zsub
    rp_shunt = 1 / yt.real                                         # per terminal to ground
    ceff_shunt = yt.imag / w0
    # differential: tank sees Ls/Rs between terminals; each terminal's shunt loss
    # appears as 2*rp_shunt across the differential port
    rp_series = (w0 * L) ** 2 / rac
    rp_diff = 1 / (1 / rp_series + 1 / (2 * rp_shunt))
    q_eff = rp_diff / (w0 * L)
    out = dict(geometry=g, process=p,
               din_um=din, davg_um=davg, fill_ratio=rho, L_nH=L * 1e9, length_um=length_um,
               metal_area_um2=area_um2, footprint_um2=dout ** 2, rsheet_strapped_ohm=rsh,
               Rdc_ohm=rdc, skin_depth_um=delta_um, skin_factor=skin, Rac_ohm=rac,
               Cox_total_fF=cox * 1e15, Cs_fF=cs * 1e15, Csi_total_fF=csi * 1e15, Rsi_total_ohm=rsi,
               shunt_per_terminal_ohm=rp_shunt, shunt_per_terminal_fF=ceff_shunt * 1e15,
               Q_series=q_series, Rp_diff_ohm=rp_diff, Q_eff=q_eff,
               uncertainty=dict(
                   L='+-10 % (Mohan [1] quotes 2-3 % vs field solvers; +-10 % covers the M4 strap, '
                     'the crossover, the lead-in and return-path effects not modelled)',
                   Rac='-20 %/+50 % (current crowding factor 1.3 assumed, [3]; via/underpass 0.3 ohm assumed)',
                   substrate='Rsi/Csi factor 3 either way (substrate resistivity and doping profile not known '
                             'from the PDK); Cox +-20 %',
                   Q='therefore Q_eff ~ -35 %/+20 % around the nominal value'))
    return out

def write(out, path):
    m = out
    lines = [f'* pt_spiral: analytical single-pi model of the LC-VCO tank inductor (lcvco/spiral.py)',
             f'* {m["geometry"]["shape"]}, n={m["geometry"]["turns"]}, w={m["geometry"]["width_um"]} um, '
             f's={m["geometry"]["space_um"]} um, dout={m["geometry"]["dout_um"]} um, {m["geometry"]["strap"]}',
             f'* L={m["L_nH"]:.3f} nH, Rac={m["Rac_ohm"]:.2f} ohm @2.45 GHz, Q_series={m["Q_series"]:.1f}, '
             f'Q_eff={m["Q_eff"]:.1f}; NOT EM-verified, see spiral.json for uncertainty',
             '.subckt pt_spiral A B VSS',
             f'LS A M {m["L_nH"]:.4f}n',
             f'RS M B {m["Rac_ohm"]:.4f}',
             f'CS A B {m["Cs_fF"]:.3f}f',
             f'COXA A SA {m["Cox_total_fF"] / 2:.3f}f',
             f'COXB B SB {m["Cox_total_fF"] / 2:.3f}f',
             f'RSIA SA VSS {2 * m["Rsi_total_ohm"]:.2f}',
             f'RSIB SB VSS {2 * m["Rsi_total_ohm"]:.2f}',
             f'CSIA SA VSS {m["Csi_total_fF"] / 2:.4f}f',
             f'CSIB SB VSS {m["Csi_total_fF"] / 2:.4f}f',
             '.ends pt_spiral', '']
    Path(path).write_text('\n'.join(lines))

if __name__ == '__main__':
    here = Path(__file__).parent
    out = model()
    write(out, here / 'spiral.spice')
    (here / 'spiral.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in out.items()
                      if k not in ('geometry', 'process', 'uncertainty')}, indent=0))
