#!/usr/bin/env python3
"""Publish step of every custom pad family (one place; the published GDS is git-ignored, so this is what makes it
reproducible):

    python3 pad_publish.py <family> [<built.gds>]        family: pad_txpad pad_refpad pad_rf_pair pad_rftxpad
                                                          pad_single_leg pad_hspad pad_wirepad pad_tlp | all

  1. copy the generator's GDS (if given) to the published path (integration/assembly/pad_cup.py PUBLISHED)
  2. pad_cup.py publish: only the stock Bondpad_5LM stack under each opening, no Via3 / Via4 in the provider-ring rail
     band; written without GDS timestamps, so the same generator output gives the same sha256
  3. pad_cup.py check (fails on anything under an opening / cuts in the band)
  4. KLayout read-back LVS of the published GDS (PDK deck gf180mcu.lvs, project image) against the family's reference
     netlist converted to PDK device form (pad_ref_pdk.py): <family dir>/pad-lvs-kl.json
  5. the family's records (pcNN*.json sha256, *-kldrc.json gds_sha256) get the new sha256
Exit 1 if check or LVS fails. Data root: SVALBARD_DATA (default: this checkout; worktrees use the main checkout)."""
import json, hashlib, os, re, shutil, subprocess, sys, glob, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get('SVALBARD_DATA', HERE.parents[3]))
ASM = HERE.parents[1] / 'integration/assembly'
KL = os.environ.get('KL_IMAGE', 'sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305')
AN = 'projects/programmable_transceiver_platform/analog/pads/generated/'
# family -> (published GDS, GDS top, reference netlist, reference top)
FAM = {'pad_txpad': ('stress-safe-families/wired-transmit/combined.gds', 'pad_txpad', 'stress-safe-families/wired-transmit/lvs-reference.spice', 'pad_txpad'),
       'pad_refpad': ('stress-safe-families/reference/combined.gds', 'pad_refpad', 'stress-safe-families/reference/lvs-reference.spice', 'combined_flat'),
       'pad_rf_pair': ('stress-safe-families/rf-pair/pad.gds', 'pad_rf_pair', 'stress-safe-families/rf-pair/reference.spice', 'pad_reference'),
       'pad_rftxpad': ('stress-safe-families/rf-tx/pad.gds', 'pad_rftxpad', 'stress-safe-families/rf-tx/reference.spice', 'pad_reference'),
       'pad_single_leg': ('stress-safe-families/single-leg/pad.gds', 'pad_single_leg', 'stress-safe-families/single-leg/reference.spice', 'pad_reference'),
       'pad_hspad': ('stress-safe-families/wired-receive-hs/pad_hspad.gds', 'pad_hspad', 'stress-safe-families/wired-receive-hs/lvs-reference.spice', 'pad_hspad_flat'),
       'pad_wirepad': ('stress-safe-families/wired-receive-usb/combined.gds', 'pad_wirepad', 'stress-safe-families/wired-receive-usb/lvs-reference.spice', 'combined_flat'),
       'pad_tlp': ('tlp-site/pad_tlp_flat.gds', 'pad_tlp_flat', 'tlp-site/reference.spice', 'pad_tlp')}
SW = ('thr=1 run_mode=deep metal_top=11K mim_option=B metal_level=5LM poly_res=1k mim_cap=2 lvs_sub=gf180mcu_gnd verbose=false '
      'spice_net_names=true spice_comments=false scale=false schematic_simplify=true net_only=false top_lvl_pins=true combine=false '
      'purge=false purge_nets=false implicit_connect=true')      # same-name pieces joined: the pads' DVDD / VSS pieces are joined by the ring at chip level (proved there by check_padsup / chip LVS)
UG = f'{os.getuid()}:{os.getgid()}'


def kl(mounts, cmd):
    m = sum((['-v', x] for x in mounts), [])
    return subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--memory', '16g', '--user', UG, '-e', 'HOME=/tmp',
                           '-e', 'OMP_NUM_THREADS=1', *m, '--entrypoint', '/bin/bash', KL, '-c',
                           'export PATH=$PATH:/foss/tools/klayout LD_LIBRARY_PATH=/foss/tools/klayout PDK_ROOT=/foss/pdks; ' + cmd],
                          capture_output=True, text=True)


def lvs(fam):
    gds, top, ref, rtop = FAM[fam]; gen = REPO / AN
    sys.path.insert(0, str(HERE)); import pad_ref_pdk
    w = Path(tempfile.mkdtemp(prefix=f'padlvs_{fam}_'))
    src = open(gen / ref).read().replace('\n+', ' ').splitlines()
    out = '\n'.join(pad_ref_pdk.conv(src))
    out = re.sub(rf'(?im)^(\.subckt\s+){re.escape(rtop)}(\s)', rf'\g<1>{top}\g<2>', out)       # reference top = GDS top
    out = re.sub(rf'(?im)^(\.ends\s+){re.escape(rtop)}\s*$', rf'\g<1>{top}', out)
    (w / 'ref.spice').write_text(out + '\n')
    sw = SW + f' topcell={top} input=/g/{gds} schematic=/w/ref.spice report=/w/out.lvsdb target_netlist=/w/out.cir'
    r = kl([f'{gen}:/g:ro', f'{w}:/w'], 'cd /w; klayout -b -r /foss/pdks/gf180mcuD/libs.tech/klayout/tech/lvs/gf180mcu.lvs ' +
           ' '.join('-rd ' + x for x in sw.split()) + ' 2>&1 | tail -40')
    log = r.stdout + r.stderr
    ok = 'Congratulations! Netlists match' in log
    mism = 'Netlists don\'t match' in log
    cir = (w / 'out.cir').read_text() if (w / 'out.cir').exists() else ''
    res = dict(family=fam, gds=gds, gds_sha256=hashlib.sha256(open(gen / gds, 'rb').read()).hexdigest(), reference=ref,
               deck='gf180mcu.lvs (project PDK f6eeac7, KLayout 0.30.9 image), schematic_simplify, top_lvl_pins',
               result='match' if ok else ('mismatch' if mism else 'error'),
               layout_devices=len(re.findall(r'(?m)^[MRDCQ]\$', cir)), reference_devices=len(re.findall(r'(?m)^[MRD]', out)),
               log_tail=log[-1500:] if not ok else '')
    if not ok: shutil.copy(w / 'out.lvsdb', gen / os.path.dirname(gds) / 'pad-lvs-kl.lvsdb') if (w / 'out.lvsdb').exists() else None
    shutil.rmtree(w, ignore_errors=True)
    return res


def records(fam, new):
    gen = REPO / AN; d = gen / os.path.dirname(FAM[fam][0]); base = os.path.basename(FAM[fam][0]); n = 0
    for f in glob.glob(str(HERE / 'generated' / os.path.dirname(FAM[fam][0]) / '*.json')):
        j = json.load(open(f)); ch = False
        if isinstance(j.get('sha256'), dict) and base in j['sha256']: j['sha256'][base] = new; ch = True
        if 'gds_sha256' in j and j.get('gds', base) == base: j['gds_sha256'] = new; ch = True
        if ch: open(f, 'w').write(json.dumps(j, indent=1) + '\n'); n += 1
    return n


def main(a):
    lvs_only = a[0] == '--lvs-only'; a = a[1:] if lvs_only else a
    fams = list(FAM) if a[0] == 'all' else [a[0]]; bad = 0
    for fam in fams:
        if lvs_only:
            L = lvs(fam); open(HERE / 'generated' / os.path.dirname(FAM[fam][0]) / 'pad-lvs-kl.json', 'w').write(json.dumps(L, indent=1) + '\n')
            print(f'{fam}: KLayout read-back LVS {L["result"]} (layout {L["layout_devices"]}, reference {L["reference_devices"]})'); bad += L['result'] != 'match'; continue
        dst = REPO / AN / FAM[fam][0]
        if len(a) > 1: shutil.copy(a[1], dst)
        r = kl([f'{REPO}:/r', f'{ASM}:/a:ro'], f'klayout -b -zz -r /a/pad_cup.py -rd cmd="publish /r {fam}"')
        print(r.stdout.strip().replace('\n', '\n  '))
        if 'PAD CUP CHECK PASS' not in r.stdout: print(f'{fam}: pad_cup FAILED', r.stderr[-400:]); bad += 1; continue
        L = lvs(fam); sha = L['gds_sha256']
        open(HERE / 'generated' / os.path.dirname(FAM[fam][0]) / 'pad-lvs-kl.json', 'w').write(json.dumps(L, indent=1) + '\n')
        print(f'{fam}: sha256 {sha[:16]}, KLayout read-back LVS {L["result"]} (layout {L["layout_devices"]}, reference {L["reference_devices"]} devices), records {records(fam, sha)}')
        bad += L['result'] != 'match'
    print('PAD PUBLISH', 'PASS' if not bad else f'FAIL ({bad})')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or ['all']))
