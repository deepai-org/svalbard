"""PD48 minimal TLP/ESD test site `pad_tlp` (cell pad_tlp_flat).

One native bond pad (Bondpad_5LM) + one leg's primary steering diodes from the shared network recipe:
4 x diode_nd2ps_06v0 PAD->VSS and 4 x diode_pd2nw_06v0 PAD->VDD (generated/protection-primitives, 25 um fingers),
nothing else. Ports PAD (bond), VDD, VSS (M2 bars, strapped to the ring at assembly).
Each diode terminal: a column of single via1 cuts at 1 um pitch (11 per PAD/VSS-down terminal, 6 VDD, 5 substrate tap).
Measurement plan: see analog/pads/README.md PD48 (TLP 100 ns, VF-TLP 1-5 ns, It2 / leakage criterion).
usage: python3 tlp_site.py --output-dir DIR   (Magic in the pinned layout image; DRC + extraction + netgen LVS)"""
import argparse, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
PRIM = HERE / 'generated/protection-primitives'
IMAGE = 'svalbard/librelane-gf180-canary:2026.08'


def generate(W):
    W.mkdir(parents=True, exist_ok=False)
    for n in ('diode_nd2ps_06v0', 'diode_pd2nw_06v0'):
        shutil.copy(PRIM / f'{n}.gds', W / f'{n}.gds')
    c = ['crashbackups stop', 'set ::env(PDKPATH) /pdk/gf180mcuD', 'path search +/pdk/gf180mcuD/libs.ref/gf180mcu_fd_io/mag',
         'gds read diode_nd2ps_06v0.gds', 'gds read diode_pd2nw_06v0.gds', 'load pad_tlp', 'units microns']
    def r(l, x1, y1, x2, y2): c.extend([f'box values {x1:.3f} {y1:.3f} {x2:.3f} {y2:.3f}', f'paint {l}'])
    def via1(x, y): r('metal1', x - .19, y - .19, x + .19, y + .19); r('via1', x - .13, y - .13, x + .13, y + .13); r('metal2', x - .2, y - .2, x + .2, y + .2)
    Y = 110.
    c += ['getcell Bondpad_5LM child 0 0 parent 5.5 0', 'identify BOND']
    nd = [(10 + 6 * i, 'nd') for i in range(4)]; pw = [(48 + 6 * i, 'pw') for i in range(4)]
    for k, (x, t) in enumerate(nd + pw):
        c += [f'getcell {"diode_nd2ps_06v0" if t == "nd" else "diode_pd2nw_06v0"} child 0 0 parent {x} {Y}', f'identify D{k}']
        for dy in range(1, 12): via1(x, Y + dy)                              # PAD: K of nd / A of pw
        if t == 'nd':
            for dy in range(1, 12): via1(x + 1.03, Y - dy)                   # VSS: A of nd (p+ ring)
        else:
            for dy in range(6, 12): via1(x + .99, Y - dy)                    # VDD: K of pw (n-well ring)
            for dy in range(1, 6): via1(x + 1.87, Y - dy)                    # VSS: substrate ring
    r('metal2', 8, Y + .5, 69, Y + 11.5)                                     # PAD bar
    r('metal2', 9, Y - 5.5, 69, Y - .5); r('metal2', 9, Y - 11.5, 30, Y - .5)  # VSS bar (L)
    r('metal2', 46, Y - 11.5, 69, Y - 6.)                                    # VDD bar
    r('metal3', 27, 55, 37, Y + 11.5)                                        # bond (its own M3 at y <= 62) -> PAD bar
    r('via2', 27.5, Y + 1., 36.5, Y + 11.)
    c += [f'box values 50 {Y+8} 50.4 {Y+8.4}', 'label PAD FreeSans 0.3 0 0 0 c metal2', 'port make 1',
          f'box values 60 {Y-3} 60.4 {Y-2.6}', 'label VSS FreeSans 0.3 0 0 0 c metal2', 'port make 2',
          f'box values 60 {Y-9} 60.4 {Y-8.6}', 'label VDD FreeSans 0.3 0 0 0 c metal2', 'port make 3',
          'select top cell', 'flatten pad_tlp_flat', 'load pad_tlp_flat', 'select top cell', 'drc check', 'drc catchup',
          'puts "TLP_DRC [drc list count total]"', 'puts [drc listall why]',
          'extract all', 'ext2spice lvs', 'ext2spice', 'gds write pad_tlp_flat.gds', 'quit -noprompt']
    (W / 'gen.tcl').write_text('\n'.join(c) + '\n')
    out = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', '/bin/sh', '-v', f'{W}:/work', '-w', '/work', IMAGE,
                          '-c', 'magic -dnull -noconsole -rcfile /pdk/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc /work/gen.tcl'], capture_output=True, text=True)
    (W / 'gen.log').write_text(out.stdout + out.stderr)
    drc = next(l for l in out.stdout.splitlines() if l.startswith('TLP_DRC'))
    ref = ['.subckt pad_tlp PAD VSS VDD'] + [f'DN{i} VSS PAD diode_nd2ps_06v0 area=22.5p pj=51.8u\nDP{i} PAD VDD diode_pd2nw_06v0 area=22.5p pj=51.8u' for i in range(4)] + ['.ends']
    (W / 'reference.spice').write_text('\n'.join(ref) + '\n')
    sys.path.insert(0, str(HERE))
    from run_first_pass import lvs
    ok = lvs(W, 'pad_tlp_flat.spice', 'pad_tlp_flat', 'reference.spice', 'pad_tlp', 'lvs.txt')
    print(drc, 'LVS', ok)
    if drc != 'TLP_DRC 0' or not ok: raise SystemExit('TLP site failed DRC/LVS')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--output-dir', type=Path, required=True)
    generate(p.parse_args().output_dir.resolve())
