"""Shared flow helpers for the timing family: simulation, layout, LVS, evidence."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import sys

import netlist
import layout_engine as le
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gds_uniquify as gu  # noqa: E402

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
REPO = PROJECT.parents[1]
SCRATCH = REPO / 'scratch' / 'timing'
GENERATED = HERE / 'generated'
ANALOG_IMAGE = 'docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3'
ANALOG_IMAGE_ID = 'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305'
DIGITAL_IMAGE = le.DIGITAL_IMAGE
MODELS = '/foss/pdks/gf180mcuD/libs.tech/ngspice'


def image_id(name):
    r = subprocess.run(['docker', 'image', 'inspect', name, '--format', '{{.Id}}'], capture_output=True, text=True)
    return r.stdout.strip() or None


def sha(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def header(corner='typical', temp=27):
    res = {'typical': 'res_typical', 'ss': 'res_ss', 'ff': 'res_ff', 'tt': 'res_typical'}.get(corner, 'res_typical')
    corner = 'typical' if corner == 'tt' else corner
    return (f'.lib {MODELS}/sm141064.ngspice {corner}\n'
            f'.lib {MODELS}/sm141064.ngspice {res}\n'
            f'.lib {MODELS}/sm141064.ngspice diode_{corner if corner in ("ss", "ff") else "typical"}\n'   # antenna diodes
            f'.include {MODELS}/design.ngspice\n'
            f'.temp {temp}\n'
            '.option method=gear reltol=1e-3\n')


def ngspice(work, name, deck, timeout=7200):
    """Run `deck` (text) in the analog image; return dict of .measure results."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    (work / f'{name}.spice').write_text(deck)
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '3', '--memory', '8g', '-e', 'OMP_NUM_THREADS=1',
           '--entrypoint', '/bin/bash', '-v', f'{work}:/work', '-w', '/work', ANALOG_IMAGE,
           '-lc', f'ngspice -b {name}.spice > {name}.log 2>&1']
    subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    log = (work / f'{name}.log').read_text(errors='replace')
    meas = {}
    for line in log.splitlines():
        m = re.match(r'^\s*([a-z_][a-z0-9_]*)\s*=\s*([-+0-9.eE]+)', line)
        if m and not line.strip().startswith('Error'):
            meas[m.group(1)] = float(m.group(2))
    failed = [l.strip() for l in log.splitlines() if 'failed' in l.lower() and 'measure' in l.lower()]
    meas['_errors'] = [l.strip() for l in log.splitlines() if l.strip().lower().startswith('error')][:10] + failed[:10]
    return meas


def stage_sources(work, block):
    """Copy the block netlist and the shared cells into a sim work dir."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    for f in HERE.glob('*.spice'):
        shutil.copy(f, work / f.name)
    for f in GENERATED.glob('*.ext.spice'):
        shutil.copy(f, work / f.name)
    for b, st in STAGED.items():   # staged (unpublished) extraction overrides the published one
        f = Path(st) / f'{b}.ext.spice'
        if f.exists():
            shutil.copy(f, work / f.name)
    (work / 'generated' / 'fast').mkdir(parents=True, exist_ok=True)
    for f in (GENERATED / 'fast').glob('*.spice'):
        shutil.copy(f, work / 'generated' / 'fast' / f.name)


STAGED = {}   # block -> stage dir whose .ext.spice benches should use instead of generated/ (run_timing publish-on-pass)


def layout_clean(drc, lvs, kl):
    """Publish gate for a layout: Magic DRC 0, netgen unique match, KLayout precheck (main + antenna) clean."""
    kl = kl or {}
    kl_ok = kl['precheck_clean'] if 'precheck_clean' in kl else (kl.get('ran') and kl.get('violations') == 0)
    return bool(drc == 0 and (lvs or {}).get('unique_match') and kl_ok)


def publish_stage(block):
    """Copy a staged layout (SCRATCH/<block>/stage) into generated/. Only call after the gate passed."""
    stage = SCRATCH / block / 'stage'
    if not stage.exists():
        raise FileNotFoundError(stage)
    GENERATED.mkdir(exist_ok=True)
    for f in stage.iterdir():
        if f.is_file():
            shutil.copy(f, GENERATED / f.name)
    for sub, dst in (('fast', GENERATED / 'fast'), ('primitives', GENERATED / 'primitives')):
        dst.mkdir(exist_ok=True)
        for f in (stage / sub).glob('*'):
            shutil.copy(f, dst / f.name)
    STAGED.pop(block, None)
    print(f'{block}: published {stage} -> {GENERATED}', flush=True)


def build_layout(block, rows=None, max_row_width=160.0, extra_trunk_nets=(), publish='clean'):
    """publish: 'clean' (default) copies into generated/ only if layout_clean(); 'never' leaves it staged
    (caller runs benches on the stage, then publish_stage()); 'force' = the old unconditional behaviour."""
    src = HERE / f'{block}.spice'
    top = f'pt_{block}'
    ports, devices = netlist.load(src, top)
    work = SCRATCH / block / 'layout'
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    rows_resolved = rows(devices) if callable(rows) else rows
    rep = le.generate(work, top, ports, devices, rows=rows_resolved, max_row_width=max_row_width,
                      extra_trunk_nets=extra_trunk_nets)
    macros = sorted({d.model for d in devices if d.model in netlist.MACROS})
    defs = ''.join((GENERATED / 'fast' / f'{m}.spice').read_text() for m in macros)
    (work / 'schematic.spice').write_text(defs + with_antenna_diodes(netlist.flat_spice(ports, devices, top), rep))
    lvs = le.netgen_lvs(work, f'{top}.lvs.spice', top, 'schematic.spice', top)
    for m in macros:  # macro .mag files are needed to reopen the hierarchical layout
        shutil.copy(work / f'{m}.mag', GENERATED / 'fast' / f'{m}.mag') if (work / f'{m}.mag').exists() else None
    gds_export_analog(work, top)
    kl = klayout_drc(work, top)
    (work / 'klayout.json').write_text(json.dumps(kl, indent=1))
    drc_raw = rep['drc_count_raw']
    drc = le.drc_errors(drc_raw)
    # Build every publishable artifact into a STAGE dir; generated/ is only written by publish_stage()
    # (publish-on-pass; a failing re-layout must never overwrite published evidence).
    stage = SCRATCH / block / 'stage'
    if stage.exists():
        shutil.rmtree(stage)
    (stage / 'fast').mkdir(parents=True)
    (stage / 'primitives').mkdir()
    for m in macros:  # macro .mag files are needed to reopen the hierarchical layout
        if (work / f'{m}.mag').exists():
            shutil.copy(work / f'{m}.mag', stage / 'fast' / f'{m}.mag')
    for suffix in ('.mag', '.ext.spice', '.lvs.spice'):
        f = work / f'{top}{suffix}'
        if f.exists():
            shutil.copy(f, stage / f'{block}{suffix}')
    if (work / f'{top}.a.gds').exists():
        shutil.copy(work / f'{top}.a.gds', stage / f'{block}.gds')
        # block-unique subcell names (p_*/ct_* differ between blocks; the chip GDS merge is by name), then the
        # required tapeout-precheck KLayout decks (DRC + antenna) -> <stage>/<block>-kldrc.json
        pre = gu.publish_checked(stage / f'{block}.gds', block, top)
        kl = dict(kl, precheck=pre, precheck_clean=pre['clean'])
        (work / 'klayout.json').write_text(json.dumps(kl, indent=1))
    for f in work.glob('p_*.mag'):  # primitives are needed to reopen the hierarchical .mag
        shutil.copy(f, stage / 'primitives' / f.name)
    shutil.copy(work / 'lvs.txt', stage / f'{block}-lvs.txt')
    details = (work / 'drc-details.txt').read_text() if (work / 'drc-details.txt').exists() else ''
    (stage / f'{block}-drc.txt').write_text(f'drc(full) error count: {drc_raw}\n{details}')
    clean = layout_clean(drc, lvs, kl)
    published = False
    if publish == 'force' or (publish == 'clean' and clean):
        publish_stage(block)
        published = True
    elif publish == 'clean':
        print(f'{block}: layout NOT clean (drc={drc}, lvs_unique={lvs.get("unique_match")}, '
              f'precheck_clean={kl.get("precheck_clean")}) -> generated/ untouched; staged in {stage}', flush=True)
    return dict(ports=ports, devices=len(devices), layout=rep, drc_errors=drc, lvs=lvs, klayout=kl, work=str(work),
                stage=str(stage), layout_clean=clean, published=published)


def with_antenna_diodes(top_spice, rep, sub='VSS'):
    """LVS reference = schematic + the generator's antenna diodes (layout_engine report)."""
    lines = le.ad.spice_lines(rep.get('antenna_diodes', []), sub=sub)
    if not lines:
        return top_spice
    k = top_spice.rstrip().rfind('.ends')
    return top_spice[:k] + '\n'.join(lines) + '\n' + top_spice[k:]


def extracted_subckt(block):
    if block in STAGED and (Path(STAGED[block]) / f'{block}.ext.spice').exists():
        return (Path(STAGED[block]) / f'{block}.ext.spice').read_text()
    """Return the extracted netlist text (hierarchical with parasitic C)."""
    return (GENERATED / f'{block}.ext.spice').read_text()


def write_evidence(block, record):
    GENERATED.mkdir(exist_ok=True)
    p = GENERATED / f'{block}-evidence.json'
    p.write_text(json.dumps(record, indent=1) + '\n')
    return p


def gds_export_analog(work, cell, timeout=3600):
    """GDS from the analog image's Magic (8.3.678) with `cif ostyle gdsii`:
    the canary image's Magic drops the HRES (62/0) marker on ppolyf_u_1k."""
    work = Path(work)
    out = f'{cell}.a.gds'   # canary-written files are root-owned; write a fresh name
    (work / 'gdsx.tcl').write_text(f'crashbackups stop\nload {cell}\ncif ostyle gdsii\ngds write {out}\nquit -noprompt\n')
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '3', '--memory', '8g', '-e', 'OMP_NUM_THREADS=1',
           '--entrypoint', '/bin/bash', '-v', f'{work}:/work', '-w', '/work', ANALOG_IMAGE,
           '-lc', 'magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc /work/gdsx.tcl > gdsx.log 2>&1']
    subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return work / out


def klayout_drc(work, cell, timeout=7200):
    """KLayout gf180mcuD DRC (sak-drc.sh -k, analog image) on the exported GDS."""
    from collections import Counter
    work = Path(work)
    kd = work / 'klayout'
    if kd.exists():
        shutil.rmtree(kd)
    kd.mkdir()
    shutil.copy(work / f'{cell}.a.gds', kd / f'{cell}.gds')
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '3', '--memory', '8g', '-e', 'OMP_NUM_THREADS=1',
           '--env', 'PDK=gf180mcuD', '--env', 'PDKPATH=/foss/pdks/gf180mcuD',
           '--entrypoint', '/bin/bash', '-v', f'{kd}:/work', '-w', '/work', ANALOG_IMAGE,
           '-lc', f'sak-drc.sh -k -w /work/out /work/{cell}.gds > /work/klayout.log 2>&1']
    subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    dbs = list((kd / 'out').glob('*/*.lyrdb')) + list((kd / 'out').glob('*.lyrdb'))
    if not dbs:
        return dict(ran=False, log_tail=(kd / 'klayout.log').read_text()[-600:])
    t = dbs[0].read_text()
    cats = Counter(re.findall(r'<item>.*?<category>(.*?)</category>', t, re.S))
    return dict(ran=True, violations=sum(cats.values()), by_rule=dict(cats), deck='gf180mcuD KLayout (sak-drc.sh -k)')


# ------------------------------------------------- netlist-level subckt name checks
# Extracted block netlists define their PCell subckts under generic names
# (p_nfet_03v3_w1_l0p28, ...).  A chain bench that includes several of them gets
# one definition per name: ngspice keeps one and ignores the rest.  This is
# harmless only if the definitions are equivalent.  `subckt_defs` canonicalises
# each definition (ports in order; R/C node pairs unordered; X lines as written).
def subckt_defs(text):
    import re as _re
    t = text.replace('\n+', ' ')
    out = {}
    for m in _re.finditer(r'^\.subckt (\S+) (.*?)\n(.*?)^\.ends', t, _re.M | _re.S):
        els = []
        for line in m.group(3).splitlines():
            f = line.split()
            if not f or f[0].startswith('*'):
                continue
            els.append((f[0][0], tuple(sorted(f[1:3])), f[3]) if f[0][0] in 'CR' else ('X', tuple(f[1:])))
        out[m.group(1)] = (m.group(2).split(), sorted(els))
    return out


def check_duplicate_subckts(paths):
    """Return {name: [files]} for subckt names defined in more than one file,
    with 'equivalent' True/False.  Use before running any multi-netlist bench."""
    seen, res = {}, {}
    for p in paths:
        for n, d in subckt_defs(Path(p).read_text()).items():
            if n in seen:
                q, d0 = seen[n]
                r = res.setdefault(n, dict(files=[str(q)], equivalent=True))
                r['files'].append(str(p))
                r['equivalent'] = r['equivalent'] and d == d0
            else:
                seen[n] = (p, d)
    return res


def uniquify_subckts(text, prefix, keep=()):
    """Prefix every subckt defined in `text` (except the names in `keep`, e.g.
    the top cell and macros another file must see) with `prefix__`, as
    gds_uniquify does for GDS cell names."""
    import re as _re
    names = [n for n in _re.findall(r'^\.subckt (\S+)', text, _re.M) if n not in keep]
    for n in sorted(names, key=len, reverse=True):
        text = _re.sub(rf'(?<![\w#]){_re.escape(n)}(?![\w#])', f'{prefix}__{n}', text)
    return text
