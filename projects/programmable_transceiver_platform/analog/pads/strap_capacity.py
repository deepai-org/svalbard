"""Current-capacity screen of the stress-safe shunt wiring (v2 macro).

Inputs: drawn strap widths/lengths/cut counts (generated/stress-safe-families/
network-shunt/network-layout.json) and Magic sheet resistances. Two loads:
  pulse  100 mA for 2 ns (selection diagnostic)
  dc     13.4 mA: both pads of a pair held at 3.63 V through 50 ohm with the chip
         off at ff/85 C (worst powered-peer case, family-sims.json), and
         57.2 mA: both pads forced to 3.63 V by an ideal source at ff/85 C
         (2 x 28.6 mA, stress-safe-sweep.json pad_loading) - a fault, not lifetime use
Thickness is inferred from sheet resistance with rho = 3.0e-8 ohm m (aluminium
film), which gives the thinnest (most pessimistic) film for a given sheet value.
DC limits are the GF180 design manual section 14.2 values (T0.1 > 100 kh) at the
85 C junction limit of the safety range, unidirectional:
https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_2.html
Table 14.3: metal1..top-1 2.09 mA/um; top metal 11 kA (the selected 1.1 um top
metal of gf180mcuD, MIM_2P0/METAL5 nodeinfo) 4.5 mA/um. Table 14.4: via1-5
(0.26 um) and COMP contact 0.58 mA per cut. At 110 C the values are 1.0 / 2.2
mA/um and 0.28 mA. EM limits are lifetime limits; the 57.2 mA case is a fault.
Pulse heating is adiabatic Joule heating dT = J^2 rho t / c_v (c_v 2.42e6 J/m3K).
"""
import argparse
import json
from pathlib import Path

RHO, CV = 3.0e-8, 2.42e6
SHEET = {1: .090, 2: .090, 3: .090, 4: .090, 5: .040}
DC_LIMIT_MA_PER_UM = {1: 2.09, 2: 2.09, 3: 2.09, 4: 2.09, 5: 4.5}   # DRM 14.2, 85 C, unidirectional
DC_LIMIT_110C = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 2.2}
VIA_LIMIT_MA = .58
DRM_URL = 'https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_2.html'
PULSE_A, PULSE_S, DC_A, DC_FAULT_A = .1, 2e-9, 13.4e-3, 57.2e-3


def wire(name, level, width_um, current_a, length_um=None):
    t = RHO / SHEET[level]
    area = width_um * 1e-6 * t
    j = current_a / area
    out = dict(element=name, layer=f'metal{level}', width_um=width_um, thickness_um_inferred=round(t * 1e6, 3),
               current_a=current_a, ma_per_um=current_a * 1e3 / width_um,
               dc_limit_ma_per_um_drm_85c=DC_LIMIT_MA_PER_UM[level], dc_limit_ma_per_um_drm_110c=DC_LIMIT_110C[level])
    out['pulse_dT_K'] = j ** 2 * RHO * PULSE_S / CV if current_a == PULSE_A else None
    if length_um:
        out['resistance_ohm'] = SHEET[level] * length_um / width_um
    return out


def cuts(name, n, current_a):
    return dict(element=name, cuts=n, current_a=current_a, ma_per_cut=current_a * 1e3 / n, limit_ma_per_cut_drm_85c=VIA_LIMIT_MA)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--macro-json', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    m = json.loads(a.macro_json.read_text())
    st = m['straps']; fingers = m['shunt']['fingers_per_stage']
    res = {}
    for load, i in (('pulse_100mA_2ns', PULSE_A), ('dc_13p4mA', DC_A), ('dc_fault_57p2mA', DC_FAULT_A)):
        rows = [wire('RAIL strap', 5, st['rail']['width_um'], i, st['rail']['length_um']),
                cuts('RAIL via4 array', st['rail']['cuts']['rail_via4'], i), cuts('RAIL via3 array', st['rail']['cuts']['rail_via3'], i),
                wire('VSS strap metal4-only section (y 288..%g)' % (288 + st['vss'].get('metal4_only_um', 12.)), 4, st['vss'].get('metal4_base_width_um', st['vss']['width_um']), i, st['vss'].get('metal4_only_um', 12.)),
                wire('VSS strap metal4 above the base (parallel to metal5)', 4, st['vss']['width_um'], i / 2, st['vss']['metal4_length_um']),
                cuts('VSS via3 array', st['vss']['cuts']['vss_via3'], i),
                wire('VSS strap metal5 parallel', 5, st['vss']['width_um'], i / 2, st['vss']['metal5_length_um']),
                wire('plate spreading from the feed column (metal2, per side, half via metal3)', 2, 21.5, i / 4),
                wire('finger strip (metal1, one finger share)', 1, .23, i / fingers),
                cuts('via1 column (one strip, ~30 cuts)', 30, i / fingers)]
        res[load] = rows
    frac = lambda load: dict(metal=max((r['ma_per_um'] / r['dc_limit_ma_per_um_drm_85c'], r['element']) for r in res[load] if 'ma_per_um' in r),
                             via=max((r['ma_per_cut'] / r['limit_ma_per_cut_drm_85c'], r['element']) for r in res[load] if 'ma_per_cut' in r))
    worst, worst_via = frac('dc_13p4mA'), frac('dc_fault_57p2mA')
    a.report.write_text(json.dumps(dict(scope=__doc__.strip(), drm_source=DRM_URL, v2=res,
                                        dc_worst_fraction_of_drm_85c_limit={'dc_13p4mA': worst, 'dc_fault_57p2mA': worst_via},
                                        wiring_resistance=m.get('wiring_resistance')), indent=1) + '\n')
    print(json.dumps(dict(dc_13p4=worst, dc_fault=worst_via,
                          pulse_max_dT_K=max((r['pulse_dT_K'] or 0) for r in res['pulse_100mA_2ns'] if 'pulse_dT_K' in r)), indent=1))


if __name__ == '__main__':
    main()
