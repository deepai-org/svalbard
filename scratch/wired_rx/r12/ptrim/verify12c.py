"""Verify the DCF-tapped r12c GDS (finalc/gen/ptrim_dcf.gds): KLayout precheck, Magic read-back DRC + LVS vs W/ptrim.spice, negative controls (from final12c.py)."""

import sys, json, shutil, subprocess, hashlib, re
from pathlib import Path
W = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx'); sys.path.insert(0, str(W))
sys.path.insert(0, str(W.parent)); sys.path.insert(0, str(W.parents[1] / 'verification'))
H = Path(__file__).resolve().parent
sys.path.insert(0, "/home/ubuntu/svalbard/scratch/wired_rx/r10ptrim")
import ptrim_compact as p, netlists, wrx_flow as f
import layout_engine as le
import gds_uniquify, kl_block_drc
S = H / 'finalc'; p.FAST = S / 'fast'; p.SCRATCH = S / 'work'; p.GEN = S / 'gen'
for d in (p.FAST, p.SCRATCH, p.GEN): d.mkdir(parents=True, exist_ok=True)
sha = lambda x: hashlib.sha256(Path(x).read_bytes()).hexdigest()
FAM = W / 'ptrim.spice'
assert netlists.BLOCKS['ptrim']().emit() == FAM.read_text(), 'W/ptrim.spice is not netlists.ptrim().emit()'
p.FAMILY = FAM


def verdict(work, out):
    t = (Path(work) / out).read_text() if (Path(work) / out).exists() else ''
    fin = re.findall(r'Final result: (.*)', t)
    return dict(unique='Circuits match uniquely.' in t, property_errors='Property errors' in t or 'property errors' in t,
                final=fin[-1] if fin else None, ok=('Circuits match uniquely.' in t) and not ('roperty errors' in t), report=str(Path(work) / out))


rep = {}
gds = p.GEN / 'ptrim_dcf.gds'
kl = S / 'kl_dcf'
if kl.exists(): shutil.rmtree(kl)
r = kl_block_drc.run('ptrim', gds, 'pt_ptrim', out=kl, threads=1)
assert r['gds_sha256'] == sha(gds)
rep['klayout_precheck'] = dict(clean=r['clean'], gds_sha256=r['gds_sha256'], klayout=r.get('klayout'), work=str(kl / 'ptrim'),
                               decks={k: dict(total=v.get('total'), rules=v.get('rules'), error=v.get('error')) for k, v in r['decks'].items()})
(p.GEN / 'ptrim_dcf-kldrc.json').write_text(json.dumps(rep['klayout_precheck'], indent=1) + '\n')
print('precheck', rep['klayout_precheck']['decks'], flush=True)
# ---- GDS read back from disk
rb = S / 'readback_dcf'
if rb.exists(): shutil.rmtree(rb)
rb.mkdir(); shutil.copy(gds, rb / 'in.gds'); shutil.copy(FAM, rb / 'family.spice')
(rb / 'rb.tcl').write_text('\n'.join(['crashbackups stop', 'gds read in.gds', 'load pt_ptrim', 'select top cell', 'drc euclidean on', 'drc style drc(full)',
    'drc check', 'drc catchup', 'set f [open drc-count.txt w]', 'puts $f [drc list count total]', 'close $f', 'extract all', 'ext2spice lvs',
    'ext2spice -o rb.lvs.spice', 'quit -noprompt']) + '\n')
(rb / 'rb.sh').write_text('export PDK_ROOT=/foss/pdks PDK=gf180mcuD\n/foss/tools/bin/magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc rb.tcl > rb.log 2>&1\n')
subprocess.run(['docker', 'run', '--rm', *f.DOCKER_LIMITS, '--entrypoint', '/bin/bash', '--mount', f'type=bind,src={rb},dst=/work', '-w', '/work', f.ANALOG_IMAGE, '/work/rb.sh'],
               capture_output=True, text=True, timeout=3600)
dtxt = (rb / 'drc-count.txt').read_text().strip() if (rb / 'drc-count.txt').exists() else 'missing'
le.netgen_lvs(rb, 'rb.lvs.spice', 'pt_ptrim', 'family.spice', 'pt_ptrim', out='lvs-readback.txt')
rep['readback'] = dict(gds_sha256=sha(rb / 'in.gds'), drc_raw=dtxt, lvs=verdict(rb, 'lvs-readback.txt'), netlist_sha256=sha(rb / 'rb.lvs.spice') if (rb / 'rb.lvs.spice').exists() else None)
# ---- negative controls (must fail)
fam = FAM.read_text()
u = p.UNITS[3]; old = f'w={u[2]:g}u l={u[3]:g}u m={u[0]}'; assert fam.count(old) >= 8, old
neg1 = fam.replace(old, f'w={u[2] + 0.01:g}u l={u[3]:g}u m={u[0]}', 1); (rb / 'neg_width.spice').write_text(neg1)
lines = fam.splitlines(); i = next(i for i, l in enumerate(lines) if ' ta3 tn3 ' in l and 'nfet' in l)
lines[i] = lines[i].replace(' ta3 tn3 ', ' ta3 tn4 ', 1); (rb / 'neg_net.spice').write_text('\n'.join(lines) + '\n')
le.netgen_lvs(rb, 'rb.lvs.spice', 'pt_ptrim', 'neg_width.spice', 'pt_ptrim', out='lvs-neg-width.txt')
le.netgen_lvs(rb, 'rb.lvs.spice', 'pt_ptrim', 'neg_net.spice', 'pt_ptrim', out='lvs-neg-net.txt')
rep['lvs_negative_controls'] = dict(width_plus_10nm_one_bit3_group=verdict(rb, 'lvs-neg-width.txt'), inv1_gate_of_ch3_moved_to_tn4=verdict(rb, 'lvs-neg-net.txt'))
rep['lvs_negative_controls']['both_fail'] = not rep['lvs_negative_controls']['width_plus_10nm_one_bit3_group']['ok'] and not rep['lvs_negative_controls']['inv1_gate_of_ch3_moved_to_tn4']['ok']
(rb / 'in.gds').unlink()
rep['gds_sha256'] = sha(gds); rep['_x'] = sha(p.GEN / 'ptrim.ext.spice'); rep['mag_sha256'] = sha(p.GEN / 'ptrim.mag'); rep['lvs_spice_sha256'] = sha(p.GEN / 'ptrim.lvs.spice')
(S / 'verify_dcf.json').write_text(json.dumps(rep, indent=1, default=str))
print('readback', rep['readback']['drc_raw'], rep['readback']['lvs']['ok'], 'neg both fail', rep['lvs_negative_controls']['both_fail'], 'kl', rep['klayout_precheck']['clean'], rep['gds_sha256'])
