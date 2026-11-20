"""r12 staging of pt_ctle r5: lay5.py [tag]  -> stage/<tag>/{work,gen,readback,lvsneg}; nothing goes to analog/wired_rx/generated.
Same steps as r10ctle/lay10.py (generate + Magic DRC + extraction + LVS of the .mag -> fail on unplaced antenna diodes -> GDS
export -> gds_uniquify.publish_checked (KLayout precheck main + antenna; record next to the staged GDS) -> GDS READ BACK FROM
DISK: Magic DRC, extraction, netgen LVS (property errors = fail)) plus an LVS negative control (one tail finger W 20 -> 20.5 um
in the reference must fail).  Layout options = run_family.LAYOUT_OPTS['ctle'] with the r5 current table below (the tree's
run_family.py is not edited: the owner moves R5_CURRENTS there at publish).  One Docker job at a time, OMP_NUM_THREADS=1."""
import sys, json, shutil, subprocess, hashlib
from pathlib import Path
W = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_rx'); sys.path.insert(0, str(W))
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog')
import wrx_flow as f
import run_family as rf
import netlists
import gds_uniquify
H = Path(__file__).resolve().parent
tag = sys.argv[1] if len(sys.argv) > 1 else 'ctle'
K_IR = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
base = H / 'stage' / tag; work = base / 'work'; gen = base / 'gen'; gen.mkdir(parents=True, exist_ok=True)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
src = W / 'ctle.spice'


def r5_currents(d):
    """mA, + = the net feeds the terminal (tt design values; wrx_flow applies 1.3x).  Tail fingers are declared K_IR x their
    current (62.5 uA) so that the sp / src / VDD tracks and trunks come out wider than EM needs (r4 R+C: 10-13 ohm tail ->
    pair); every other entry is the real design current."""
    n = d.nodes
    if d.model.startswith('pfet') and n[1] == 'atb_ctle_pbias' and n[0] != 'atb_ctle_pbias':
        i = 2.5 / 42 * (K_IR if n[0] in ('sp', 'atb_ctle_src', 'spr') else 1.0)
        return {0: -i, 2: i}
    if d.model.startswith('pfet') and n[1] in ('RX_P', 'RX_N', 'vgr'):
        return {0: -2.5 / 6, 2: 2.5 / 6}                 # input pair finger (and the replica finger)
    if d.model.startswith('ppolyf') and n[0] in ('cp', 'cn', 'cpr'):
        return {0: 2.5 / netlists.CTLE_RL_M, 1: -2.5 / netlists.CTLE_RL_M}     # load strip -> VSS
    if d.iso:
        return {0: 3.4, 2: -3.4} if n[2] in ('CTLE_P', 'CTLE_N') else {0: 0.6, 2: -0.6}   # follower / replica follower
    if d.model.startswith('nfet') and n[1] == 'fbias':
        return {0: 0.30, 2: -0.30}                     # sink finger / mirror diode
    return {}


opts = dict(rf.LAYOUT_OPTS['ctle'])
opts['currents'] = r5_currents
opts['trunk_match'] = (('RX_P', 'RX_N'), ('sp', 'atb_ctle_src'), ('CTLE_P', 'CTLE_N'))
sub = f.parse_spice(src)
lay = f.generate_layout(sub, work, columns=rf.COLUMNS.get('ctle'), **opts)
rep = dict(block='ctle', tag=tag, k_ir=K_IR, source=str(src), source_sha256=sha(src), wrx_flow_sha256=sha(W / 'wrx_flow.py'), netlists_sha256=sha(W / 'netlists.py'),
           lay5_sha256=sha(__file__), devices=len(sub.devices), drc_errors=lay['drc_count'], size_um=lay['size_um'], area_um2=lay['area_um2'],
           grid=dict(columns=lay['columns'], rows=lay['rows']), antenna_diodes=lay['antenna_diodes'], antenna_unplaced=lay['antenna_unplaced'],
           iso_wells=lay.get('iso_wells'), matched_foreign_metal=lay.get('matched_foreign_metal'), row_report=lay.get('row_report'))
print('layout', {k: rep[k] for k in ('drc_errors', 'size_um', 'area_um2', 'grid', 'antenna_unplaced')}, flush=True)
if lay['drc_count']:
    print((work / 'drc-details.txt').read_text()[:3000])
ref = f.lvs_reference(src, sub.name, lay.get('antenna_diodes'), work / 'lvs_reference.spice')
lv = f.lvs(work, f'{sub.name}.lvs.spice', sub.name, ref, sub.name)
rep['lvs_mag'] = dict(unique=lv['unique_match'], property_errors=lv['property_errors'], final=lv['final_result'])
print('lvs(mag)', rep['lvs_mag'], flush=True)
(base / 'layout.json').write_text(json.dumps(rep, indent=1, default=str) + '\n')
if lay['drc_count'] or not lv['unique_match'] or lay['antenna_unplaced']:
    sys.exit('STOP: DRC / LVS / unplaced antenna diode')
exp = base / 'export'
if exp.exists(): shutil.rmtree(exp)
exp.mkdir(); shutil.copy(work / f'{sub.name}.mag', exp / f'{sub.name}.mag')
for pm in work.glob(f'{sub.name}__prim_*.mag'): shutil.copy(pm, exp / pm.name)
rep['gds_export'] = f.export_gds(exp, sub.name, sum(d.model.startswith('ppolyf') for d in sub.devices))
print('export', {k: rep['gds_export'][k] for k in ('hres_ok', 'pass', 'klayout_drc')}, flush=True)
shutil.copy(exp / f'{sub.name}.gds', gen / 'ctle.gds')
for ext in ('mag', 'ext.spice', 'lvs.spice'): shutil.copy(work / f'{sub.name}.{ext}', gen / f'ctle.{ext}')
for pm in work.glob(f'{sub.name}__prim_*.mag'): shutil.copy(pm, gen / pm.name)
shutil.copy(work / 'lvs_reference.spice', gen / 'ctle.lvs_reference.spice'); shutil.copy(work / 'lvs.txt', gen / 'ctle-lvs.txt')
for extra in ('iso-wells.json', 'em-widths.json'):
    if (work / extra).exists(): shutil.copy(work / extra, gen / f'ctle-{extra}')
# the flow's publish step: uniquify + KLayout precheck (main + antenna), record ctle-kldrc.json next to the GDS
rep['publish_checked'] = gds_uniquify.publish_checked(gen / 'ctle.gds', 'ctle', sub.name, threads=1)
print('publish_checked', rep['publish_checked'], flush=True)
# GDS read back from disk
rb = base / 'readback'
if rb.exists(): shutil.rmtree(rb)
rb.mkdir(); shutil.copy(gen / 'ctle.gds', rb / 'in.gds'); shutil.copy(work / 'lvs_reference.spice', rb / 'lvs_reference.spice')
(rb / 'rb.tcl').write_text('\n'.join(['crashbackups stop', 'gds read in.gds', f'load {sub.name}', 'select top cell', 'drc euclidean on', 'drc style drc(full)',
    'drc check', 'drc catchup', 'set f [open drc-count.txt w]', 'puts $f [drc list count total]', 'close $f', 'set f [open drc-why.txt w]', 'puts $f [drc listall why]', 'close $f', 'extract all', 'ext2spice lvs',
    'ext2spice -o rb.lvs.spice', 'quit -noprompt']) + '\n')
(rb / 'rb.sh').write_text('export PDK_ROOT=/foss/pdks PDK=gf180mcuD\n/foss/tools/bin/magic -dnull -noconsole -rcfile /foss/pdks/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc rb.tcl > rb.log 2>&1\n')
subprocess.run(['docker', 'run', '--rm', *f.DOCKER_LIMITS, '--entrypoint', '/bin/bash', '--mount', f'type=bind,src={rb},dst=/work', '-w', '/work', f.ANALOG_IMAGE, '/work/rb.sh'],
               capture_output=True, text=True, timeout=3600)
dtxt = (rb / 'drc-count.txt').read_text().strip() if (rb / 'drc-count.txt').exists() else 'missing'
lv2 = f.lvs(rb, 'rb.lvs.spice', sub.name, rb / 'lvs_reference.spice', sub.name) if (rb / 'rb.lvs.spice').exists() else dict(unique_match=False, property_errors=None, final_result='no extraction')
rep['readback'] = dict(gds_sha256=sha(rb / 'in.gds'), drc_raw=dtxt, lvs_unique=lv2['unique_match'], lvs_property_errors=lv2['property_errors'], lvs_final=lv2['final_result'])
if (rb / 'lvs.txt').exists(): shutil.copy(rb / 'lvs.txt', gen / 'ctle-lvs-gds-readback.txt')
# negative control on the read-back extraction: one tail finger 20 -> 20.5 um in the reference
nd = base / 'lvsneg'
if nd.exists(): shutil.rmtree(nd)
nd.mkdir(); shutil.copy(rb / 'rb.lvs.spice', nd / 'lay.spice')
good = (rb / 'lvs_reference.spice').read_text()
old = 'sp atb_ctle_pbias VDD_WIRE_SW VDD_WIRE_SW pfet_03v3 w=20u l=1u m=2'
assert old in good
bad = good.replace(old, 'sp atb_ctle_pbias VDD_WIRE_SW VDD_WIRE_SW pfet_03v3 w=20.5u l=1u m=2', 1)
(nd / 'bad.spice').write_text(bad)
lv3 = f.lvs(nd, 'lay.spice', sub.name, nd / 'bad.spice', sub.name)
rep['lvs_negative_control'] = dict(change='one tail instance (2 fingers) w 20 -> 20.5 um in the reference', unique_match=lv3['unique_match'],
                                   property_errors=lv3['property_errors'], final=lv3['final_result'], detected=not lv3['unique_match'])
(rb / 'in.gds').unlink()
print('readback', rep['readback'], 'negative control', rep['lvs_negative_control'], flush=True)
rep['gds_sha256'] = sha(gen / 'ctle.gds'); rep['ext_sha256'] = sha(gen / 'ctle.ext.spice')
(base / 'layout.json').write_text(json.dumps(rep, indent=1, default=str) + '\n'); shutil.copy(base / 'layout.json', gen / 'ctle-layout.json')
