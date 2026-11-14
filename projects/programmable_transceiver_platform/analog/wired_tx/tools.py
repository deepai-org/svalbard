"""Shared helpers: pinned images, docker runners, hashing and waveform parsing."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
REPO = PROJECT.parents[1]
SCRATCH = REPO / 'scratch' / 'wired_tx'
GENERATED = HERE / 'generated'

ANALOG_IMAGE = ('docker.io/hpretl/iic-osic-tools@sha256:'
                '89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3')
# Lead-provided digital image (non-byte-identical rebuild of the locked 9253a51f... recipe).
DIGITAL_IMAGE = os.environ.get('WTX_DIGITAL_IMAGE', 'svalbard/librelane-gf180-canary:2026.08')
DIGITAL_PDK = '/pdk/gf180mcuD'
ANALOG_PDK = '/foss/pdks/gf180mcuD'
NGSPICE = '/foss/tools/ngspice/bin/ngspice'
DOCKER_LIMITS = ['--network', 'none', '--cpus', '3', '--memory', '8g', '-e', 'OMP_NUM_THREADS=1']


def sha(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def image_id(image):
    try:
        out = subprocess.run(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'],
                             capture_output=True, text=True, check=True).stdout.strip()
        return out
    except subprocess.CalledProcessError:
        return 'unavailable'


def run_digital(work, script_cmd, timeout=3600):
    """Run a shell command inside the digital image with /work bound to `work`."""
    cmd = ['docker', 'run', '--rm', *DOCKER_LIMITS, '-v', f'{work}:/work', '-w', '/work',
           '--entrypoint', '/bin/sh', DIGITAL_IMAGE, '-c', script_cmd]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def magic(work, script, timeout=3600):
    r = run_digital(work, f'magic -dnull -noconsole -rcfile {DIGITAL_PDK}/libs.tech/magic/gf180mcuD.magicrc /work/{script}',
                    timeout)
    (Path(work) / (script + '.log')).write_text(r.stdout + r.stderr)
    r.check_returncode()
    return r


def ngspice(work, deck, timeout=7200, mounts=()):
    """Run ngspice in batch mode inside the analog image."""
    extra = []
    for src, dst in mounts:
        extra += ['-v', f'{src}:{dst}:ro']
    cmd = ['docker', 'run', '--rm', *DOCKER_LIMITS, '-v', f'{work}:/work', *extra, '-w', '/work',
           '--entrypoint', '/bin/bash', ANALOG_IMAGE, '-c', f'{NGSPICE} -b {deck} > {deck}.log 2>&1']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r, (Path(work) / f'{deck}.log').read_text()


def model_header(corner='typical', temp=27, pdk=ANALOG_PDK):
    return (f'.include {pdk}/libs.tech/ngspice/design.ngspice\n'
            f'.lib {pdk}/libs.tech/ngspice/sm141064.ngspice {corner}\n'
            f'.lib {pdk}/libs.tech/ngspice/sm141064.ngspice {_diode(corner)}\n'   # antenna diodes (extracted)
            f'.lib {pdk}/libs.tech/ngspice/sm141064.ngspice {_res(corner)}\n'     # ppolyf loads (CML stage)
            f'.temp {temp}\n.option savecurrents=0\n')


def _res(corner):
    return {'ss': 'res_ss', 'ff': 'res_ff'}.get(corner, 'res_typical')


def _diode(corner):
    return {'ss': 'diode_ss', 'ff': 'diode_ff'}.get(corner, 'diode_typical')


def read_wrdata(path, names):
    """Parse an ngspice `wrdata` file written with `set wr_singlescale`."""
    import numpy as np
    data = np.loadtxt(path)
    out = {'time': data[:, 0]}
    for i, n in enumerate(names):
        out[n] = data[:, 1 + i]
    return out


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=False) + '\n')


def run_analog(work, cmd, timeout=7200, env=()):
    """Run a login-shell command in the analog image with /work bound to `work`."""
    extra = []
    for e in env:
        extra += ['--env', e]
    c = ['docker', 'run', '--rm', *DOCKER_LIMITS, *extra, '-v', f'{work}:/work', '-w', '/work',
         '--entrypoint', '/bin/bash', ANALOG_IMAGE, '-lc', cmd]
    return subprocess.run(c, capture_output=True, text=True, timeout=timeout)


def gds_export_analog(work, cell):
    """GDS written by the analog image's Magic 8.3.678 with `cif ostyle gdsii`
    (spec/block-deliverables.md "GDS export rule")."""
    out = f'{cell}.a.gds'
    (Path(work) / 'gdsx.tcl').write_text(f'crashbackups stop\nload {cell}\ncif ostyle gdsii\ngds write {out}\nquit -noprompt\n')
    run_analog(work, f'magic -dnull -noconsole -rcfile {ANALOG_PDK}/libs.tech/magic/gf180mcuD.magicrc '
                     '/work/gdsx.tcl > gdsx.log 2>&1; magic --version >> gdsx.log 2>&1')
    return Path(work) / out


def klayout_drc(work, gds, cell):
    """KLayout gf180mcuD DRC (sak-drc.sh -k, analog image) on an exported GDS."""
    import re
    import shutil
    from collections import Counter
    kd = Path(work) / 'klayout'
    if kd.exists():
        shutil.rmtree(kd)
    kd.mkdir()
    shutil.copy(gds, kd / f'{cell}.gds')   # sak-drc takes the top cell name from the file name
    run_analog(kd, f'sak-drc.sh -k -w /work/out /work/{cell}.gds > /work/klayout.log 2>&1',
               env=('PDK=gf180mcuD', f'PDKPATH={ANALOG_PDK}'))
    dbs = list((kd / 'out').glob('*/*.lyrdb')) + list((kd / 'out').glob('*.lyrdb'))
    if not dbs:
        return dict(ran=False, log_tail=(kd / 'klayout.log').read_text()[-800:])
    t = dbs[0].read_text()
    cats = Counter(re.findall(r'<item>.*?<category>(.*?)</category>', t, re.S))
    return dict(ran=True, violations=sum(cats.values()), by_rule=dict(cats), report=str(dbs[0]),
                deck='gf180mcuD KLayout (sak-drc.sh -k)')


def netgen_lvs(work, layout_spice, cell, schematic_spice):
    r = run_digital(work, f'netgen -batch lvs "{layout_spice} {cell}" "{schematic_spice} {cell}" '
                          f'{DIGITAL_PDK}/libs.tech/netgen/gf180mcuD_setup.tcl lvs.out > netgen.log 2>&1')
    txt = (Path(work) / 'lvs.out').read_text()
    final = [l for l in txt.splitlines() if 'Final result' in l]
    return dict(unique_match='Circuits match uniquely' in txt, summary=final[-1] if final else txt[-400:],
                tool='Netgen (digital image)', report='lvs.out')


# The pads family validates its extracted pad netlists with a patched ngspice-47
# (analog/pads/generated/simulator-build.json: diode sidewall-charge and capacitor
# multiplier fixes); ngspice 43 in the analog image fails to converge on them.
# Pad-integration decks therefore run with that recorded host binary and the
# unchanged PDK model files copied by the pads flow (hashes equal to the image's).
PAD_NGSPICE = REPO / 'scratch/pad-ngspice47/ngspice-47/src/ngspice'
PAD_MODELS = REPO / 'scratch/transceiver-pad-pdk/ngspice'


def model_header_dir(corner, temp, mdir):
    return (f'.include {mdir}/design.ngspice\n.lib {mdir}/sm141064.ngspice {corner}\n.temp {temp}\n'
            '.option savecurrents=0\n')


def ngspice_host(work, deck, timeout=7200):
    env = dict(os.environ, OMP_NUM_THREADS='1')
    log = Path(work) / f'{deck}.log'
    with open(log, 'w') as f:
        subprocess.run([str(PAD_NGSPICE), '-b', deck], cwd=work, stdout=f, stderr=subprocess.STDOUT,
                       timeout=timeout, env=env)
    return None, log.read_text(errors='replace')
