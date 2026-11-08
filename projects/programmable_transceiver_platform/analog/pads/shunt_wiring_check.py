"""Wiring-resistance check of the v2 rail shunt in the 100 mA retained-network pulse.

Magic's device-level extraction (used for LVS and the earlier screens) has no
wiring resistance. This builds a distributed model of the drawn v2 macro: each
bank is 24 groups of 10 fingers on drain and source plate lines (metal2 ||
metal3, nominal or high sheet resistance), source(k) and drain(k+1) joined plate
to plate, RAIL entering bank 0 and VSS leaving bank 2 at the drawn strap columns
through the drawn strap and via resistances (rail_shunt_v2.strap_resistance).
It replaces the shunt in the same RX retained pulse fixture used for selection.
Lumped-line approximation, not resistance extraction.
"""
import argparse
import json
from pathlib import Path

import stress_safe_clamp as s
import rail_shunt_v2 as v2

GROUPS = 24


def ladder(meta, geo, corner):
    sheet = v2.SHEET if corner == 'nominal' else v2.SHEET_HI
    cut = v2.CUT_OHM if corner == 'nominal' else v2.CUT_OHM_HI
    stages, fingers = meta['shunt']['stages'], meta['shunt']['fingers_per_stage']
    width = geo['bank_width_um']; seg = width / GROUPS
    height = v2.D_REGION[1] - v2.D_REGION[0]
    r_seg = 1 / (1 / sheet[2] + 1 / sheet[3]) * seg / height
    # vertical path inside the joined source(k)/drain(k+1) plate, per group column
    r_join = sheet[3] * (geo['pitch']) / seg
    # via1 columns: ~30 cuts per strip, fingers/GROUPS/2 strips of each kind per group
    r_via = cut / 30 / (fingers / GROUPS / 2)
    res = v2.strap_resistance(meta['straps'], geo, stages)[corner]
    x0 = -width / 2
    col = lambda x: min(GROUPS - 1, max(0, int((x - v2.MACRO_DX - x0) / seg)))
    rail_cols = range(col(v2.RAIL_STRAP_X[0]), col(v2.RAIL_STRAP_X[1]) + 1)
    vss_cols = range(col(v2.VSS_STRAP_X[0]), col(v2.VSS_STRAP_X[1]) + 1)
    L = ['.subckt rail_shunt_flat RAIL VSS']
    m = fingers // GROUPS
    for k in range(stages):
        for i in range(GROUPS):
            L.append(f'XM{k}_{i} DI{k}_{i} DI{k}_{i} SI{k}_{i} VSS nfet_06v0 w=50u l=0.7u nf=1 m={m} ad=22p as=22p pd=100.88u ps=100.88u')
            L.append(f'RVD{k}_{i} DI{k}_{i} D{k}_{i} {r_via:.6g}')
            L.append(f'RVS{k}_{i} SI{k}_{i} S{k}_{i} {r_via:.6g}')
            if i:
                L.append(f'RD{k}_{i} D{k}_{i-1} D{k}_{i} {r_seg:.6g}')
                L.append(f'RS{k}_{i} S{k}_{i-1} S{k}_{i} {r_seg:.6g}')
            if k:
                L.append(f'RJ{k}_{i} S{k-1}_{i} D{k}_{i} {r_join:.6g}')
    n = len(rail_cols)
    L.append(f'RRAILSTRAP RAIL RAILIN {res["rail_strap_ohm"]:.6g}')
    L += [f'RRAILIN{i} RAILIN D0_{i} {n * 1e-3:.6g}' for i in rail_cols]
    n = len(vss_cols)
    L.append(f'RVSSSTRAP VSSOUT VSS {res["vss_strap_ohm"]:.6g}')
    L += [f'RVSSOUT{i} S{stages-1}_{i} VSSOUT {n * 1e-3:.6g}' for i in vss_cols]
    L.append('.ends rail_shunt_flat')
    return '\n'.join(L) + '\n', dict(r_segment_ohm=r_seg, r_join_ohm=r_join, r_via_group_ohm=r_via, straps=res,
                                     rail_columns=list(rail_cols), vss_columns=list(vss_cols))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--macro-dir', type=Path, required=True)
    p.add_argument('--shunt-dir', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    meta = json.loads((a.macro_dir / 'network-layout.json').read_text())
    geo = json.loads((a.shunt_dir / 'geometry.json').read_text())
    src = s.SCRATCH / 'pad-supervised-receive' / s.BASE_DECK
    if s.sha(src) != s.BASE_DECK_SHA256:
        raise ValueError('Fixture differs')
    base = src.read_text().split('.control')[0]
    work = a.output_dir.resolve(); work.mkdir(parents=True, exist_ok=True)
    out = {}
    for corner in ('nominal', 'high'):
        text, model = ladder(meta, geo, corner)
        path = work / f'ladder_{corner}.spice'; path.write_text(text)
        s.VARIANTS[f'v2_wired_{corner}'] = ('extracted', str(path))
        for proc, temp in (('typical', 27), ('ss', 0)):
            r = s.pulse_variant(work, base, f'v2_wired_{corner}', s.VARIANTS[f'v2_wired_{corner}'], proc, temp)
            out[f'{corner}_resistance/{proc}/{temp}C'] = dict(pad_p_peak_v=r['windows']['pulse']['pad_p_max_v'],
                rail_peak_v=r['windows']['pulse']['rail_max_v'], exceeding=r['exposure']['observed_mos_exceeding_gate_screen'],
                brownout_pad_v=r['windows']['before']['pad_p_max_v'], deck_sha256=r['deck_sha256'])
        out[f'{corner}_model'] = model
    a.report.write_text(json.dumps(dict(results=out, scope=__doc__.strip(),
        device_only_reference={'typical/27C': 5.153, 'ss/0C': 5.822}), indent=1) + '\n')
    print(json.dumps(out, indent=1)[:2500])


if __name__ == '__main__':
    main()
