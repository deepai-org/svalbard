"""AGND_RX ground pad `pad_agnd` (cell pad_agnd_flat) for the two extra pad openings beside RF_RX (PD2-12, PC-18).

One native bond pad (Bondpad_5LM) for the LNA ground AGND_RX and the single tie to die VSS that PD2-12 asks for:
one diode_nd2ps_06v0 (VSS -> PAD) and one diode_pd2nw_06v0 (PAD -> VSS, n-well on VSS), i.e. a back-to-back clamp.
Same pattern as the fixed TLP site (tlp_site.py): Metal2-only escape, nothing on Metal3-5 in the provider rail bands.
Ports PAD (= AGND_RX, Metal2 bar at depth 110.5-121.5; the LNA ground route starts there), VSS (Metal2).
usage: python3 agnd_pad.py --output-dir DIR   (Magic DRC + extraction; LVS by the read-back tool, see README PC section)"""
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
         'gds read diode_nd2ps_06v0.gds', 'gds read diode_pd2nw_06v0.gds', 'load pad_agnd', 'units microns']
    def r(l, x1, y1, x2, y2): c.extend([f'box values {x1:.3f} {y1:.3f} {x2:.3f} {y2:.3f}', f'paint {l}'])
    def via1(x, y): r('metal1', x - .19, y - .19, x + .19, y + .19); r('via1', x - .13, y - .13, x + .13, y + .13); r('metal2', x - .2, y - .2, x + .2, y + .2)
    Y = 110.
    c += ['getcell Bondpad_5LM child 0 0 parent 5.5 0', 'identify BOND']
    nd = [(20, 'nd')]; pw = [(52, 'pw')]                                    # one diode each way: AGND_RX <-> VSS clamp, minimum capacitance
    for k, (x, t) in enumerate(nd + pw):
        c += [f'getcell {"diode_nd2ps_06v0" if t == "nd" else "diode_pd2nw_06v0"} child 0 0 parent {x} {Y}', f'identify D{k}']
        for dy in range(1, 12): via1(x, Y + dy)                              # PAD: K of nd / A of pw
        if t == 'nd':
            for dy in range(1, 12): via1(x + 1.03, Y - dy)                   # VSS: A of nd (p+ ring)
        else:
            for dy in range(6, 12): via1(x + .99, Y - dy)                    # VSS: K of pw (n-well ring tied to VSS: PAD -> VSS diode)
            for dy in range(1, 6): via1(x + 1.87, Y - dy)                    # VSS: substrate ring
    r('metal2', 8, Y + .5, 69, Y + 11.5)                                     # PAD bar
    r('metal2', 9, Y - 20, 30, Y - .5); r('metal2', 45, Y - 5.5, 69, Y - .5)  # VSS: left bar = nd anodes (carries the PAD->VSS current, has the port);
    r('metal2', 45, Y - 20, 45.7, Y - .5); r('metal2', 45, Y - 20, 47.5, Y - 15)  # right bar = pw substrate rings only (taps), joined by the bridge
    r('metal1', 27.9, Y - 19.4, 47.3, Y - 15.6)                              # VSS bridge under the riser (Metal1, below the diode rows)
    for xx in (28.5, 29.2, 46.2, 46.9):
        for dy in (16, 17, 18, 19): via1(xx, Y - dy)
    r('metal2', 45, Y - 11.5, 69, Y - .5)                                    # pw cathode + substrate ring: one VSS bar
    # bond -> PAD bar on Metal2 only (PC-2, 2026-11-14): the provider ring rails are Metal3-5 (DVSS depth 70-117, DVDD from 118)
    # and carry no Metal2, so the riser must not use Metal3 there (the earlier Metal3 riser shorted PAD, DVSS and DVDD).
    r('metal2', 31.5, Y - 21.5, 44.5, Y + 1.)                                # riser, 13 um wide in the gap between the VSS bars ...
    r('metal2', 12, 55, 62, Y - 21.)                                         # ... and 50 um wide below them (the ring has no Metal2)
    c += [f'box values 50 {Y+8} 50.4 {Y+8.4}', 'label PAD FreeSans 0.3 0 0 0 c metal2', 'port make 1',
          f'box values 20 {Y-3} 20.4 {Y-2.6}', 'label VSS FreeSans 0.3 0 0 0 c metal2', 'port make 2',
          'select top cell', 'flatten pad_agnd_flat', 'load pad_agnd_flat', 'select top cell', 'drc check', 'drc catchup',
          'puts "TLP_DRC [drc list count total]"', 'puts [drc listall why]',
          'extract all', 'ext2spice lvs', 'ext2spice', 'gds write pad_agnd_flat.gds', 'quit -noprompt']
    (W / 'gen.tcl').write_text('\n'.join(c) + '\n')
    out = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', '/bin/sh', '-v', f'{W}:/work', '-w', '/work', IMAGE,
                          '-c', 'magic -dnull -noconsole -rcfile /pdk/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc /work/gen.tcl'], capture_output=True, text=True)
    (W / 'gen.log').write_text(out.stdout + out.stderr)
    drc = next(l for l in out.stdout.splitlines() if l.startswith('TLP_DRC'))
    (W / 'reference.spice').write_text('.subckt pad_agnd PAD VSS\nDN0 VSS PAD diode_nd2ps_06v0 area=22.5p pj=51.8u\n'
                                       'DP0 PAD VSS diode_pd2nw_06v0 area=22.5p pj=51.8u\n.ends\n')
    print(drc)
    if drc != 'TLP_DRC 0': raise SystemExit('AGND pad failed DRC')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--output-dir', type=Path, required=True)
    generate(p.parse_args().output_dir.resolve())
