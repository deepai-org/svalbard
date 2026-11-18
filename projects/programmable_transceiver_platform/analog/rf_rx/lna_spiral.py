"""LNA tank inductor: same generator/model family as the QVCO spiral (analog/timing/lcvco/spiral.py), geometry: 220 um outer,
4 turns, 20 um, L 2.01 nH, Q_eff 7.0 nominal.  TWO single-ended spirals, vtk -> tank_p and vtk -> tank_n (they carry the DC);
2 x 57.2k um^2.  Variants (sized at the PESSIMISTIC values):
  pt_lna_ind       nominal model
  pt_lna_ind_pess  L -15 %, Rs scaled so that Q_eff = 4 at 2.44 GHz, worst substrate
  pt_lna_ind_lhi   L +10 %, nominal Q
The core layout is LVS-checked without the spiral (as the QVCO); the spiral is a DRC-only cell placed at the tank pins
`tank_p` / `tank_n`, and benches insert the model (tb.netlist)."""
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'timing' / 'lcvco'))
import spiral as SP

G = dict(SP.G, dout_um=220.0, turns=4, width_um=20.0, under_w_um=12.0, f_hz=2.44e9)   # under_w < width: via2 enclosure
L_NOM = SP.L_NOM


def model(variant='nom'):
    if variant == 'nom':
        return SP.analytic(G, 'nominal', 1.0, L_NOM)
    if variant == 'lhi':
        return SP.analytic(G, 'nominal', 1.0, L_NOM * 1.10)
    # pess: L -15 %, worst substrate, Rs scale found for Q_eff = 4
    lo, hi = 1.0, 10.0
    for _ in range(50):
        mid = (lo + hi) / 2
        q = SP.analytic(G, 'worst', mid, L_NOM * 0.85)['Q_eff']
        lo, hi = (mid, hi) if q > 4 else (lo, mid)
    return SP.analytic(G, 'worst', lo, L_NOM * 0.85)


NAMES = {'nom': 'pt_lna_ind', 'pess': 'pt_lna_ind_pess', 'lhi': 'pt_lna_ind_lhi'}

# Source-degeneration inductor (coordinator decision 2026-11-13, risk RFR-12): ON CHIP, one spiral per CS source to the LNA's own
# VSS, so no bond wire or pad is in the degeneration path.  Same generator/model family: 100 um, 2 turns, 15 um -> 0.31 nH,
# Rs 1.7 ohm, 14.0k um^2 each (scan: scratch/rf-lna-q/f2.py).  Variants: pess = L -15 %, Rs +30 %, worst substrate
# (gain/NF worst); lhi = L +10 %; lowr = Rs -30 %, best substrate (least damping: stability worst).
G_DEG = dict(SP.G, dout_um=100.0, turns=2, width_um=15.0, under_w_um=12.0, f_hz=2.44e9)   # round 2: halved (0.31 nH, 14.0k um^2): +0.6 dB gain, same NF on the channel, S11 holds
DEG_NAMES = {'nom': 'pt_lna_deg', 'pess': 'pt_lna_deg_pess', 'lhi': 'pt_lna_deg_lhi', 'lowr': 'pt_lna_deg_lowr'}


def model_deg(variant='nom'):
    sub, rs, ls = {'nom': ('nominal', 1.0, 1.0), 'pess': ('worst', 1.3, 0.85), 'lhi': ('nominal', 1.0, 1.10),
                   'lowr': ('best', 0.7, 1.0)}[variant]
    return SP.analytic(G_DEG, sub, rs, L_NOM * ls)


def subckt_deg(variant='nom'):
    return SP.subckt(DEG_NAMES[variant], model_deg(variant), f'LNA source degeneration, variant {variant}')


def subckt(variant='nom'):
    return SP.subckt(NAMES[variant], model(variant), f'LNTA tank, variant {variant}')


if __name__ == '__main__':
    for v in NAMES:
        m = model(v)
        print(v, {k: round(m[k], 2) for k in ('L_nH', 'Rs_ohm', 'Q_eff', 'Rp_diff_ohm', 'footprint_um2', 'Cox_total_fF')})
    for v in DEG_NAMES:
        m = model_deg(v)
        print('deg', v, {k: round(m[k], 2) for k in ('L_nH', 'Rs_ohm', 'Rdc_ohm', 'Q_series', 'footprint_um2', 'Cox_total_fF')})


def layout(which='ind'):
    """Magic layout + DRC of pt_lna_ind (which='ind') or pt_lna_deg ('deg') with the QVCO spiral generator; output in
    generated/lna_<which>.{mag,gds}.  DRC-only cells (no devices): benches insert the models above."""
    import subprocess, shutil, rfrx_flow as flow
    g, cell = (G, 'pt_lna_ind') if which == 'ind' else (G_DEG, 'pt_lna_deg')
    work = flow.SCRATCH / f'lna_{which}'
    work.mkdir(parents=True, exist_ok=True)
    for f in work.glob('pt_lna_*'):
        f.unlink()
    if (work / 'drc.txt').exists():
        (work / 'drc.txt').unlink()
    tcl = SP.layout_tcl(g, cell=cell).replace('pt_spiral_ind', cell)
    (work / 'spiral.tcl').write_text(tcl)
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '6g', '--env', 'OMP_NUM_THREADS=1', '--entrypoint', '/bin/sh',
           '--mount', f'type=bind,src={work},dst=/work', '-w', '/work', SP.DIGITAL_IMAGE, '-c',
           'magic -dnull -noconsole -rcfile /pdk/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc /work/spiral.tcl > magic.log 2>&1']
    subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    drc = (work / 'drc.txt').read_text() if (work / 'drc.txt').exists() else 'missing'
    for f in work.glob(f'{cell}.*'):
        shutil.copy(f, flow.GENERATED / f.name.replace(cell, f'lna_{which}'))
    return drc.split('\n', 1)[0].strip()


if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == 'layout':
    for w_ in ('ind', 'deg'):
        print(w_, 'DRC', layout(w_))
