"""pt_wiredtx8 run_all without the copy to generated/fast (writes s13/top/out only; the copy is done at the end, in one go)."""
import sys, json, inspect, textwrap
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_tx')
import pt_wiredtx8_layout as P
src = textwrap.dedent(inspect.getsource(P.run_all)).replace("        shutil.copy(src, FAST / name)\n", "")
assert 'FAST / name' not in src
ns = dict(vars(P))
exec(src, ns)
r = ns['run_all']()
v = r['verify_from_disk']
print(json.dumps(dict(size=r['size_um'], area=r['bbox_area_um2'], used=r['used_area_um2'], seam=round(r['seam_um'][1] - r['seam_um'][0], 2), magic_drc=v['magic_drc'],
                      klayout=v['klayout_drc'].get('violations'), lvs=v['lvs'], negatives={k: x['fails_as_required'] for k, x in v['negative_controls'].items()},
                      antenna=v['antenna_magic'], c_netlist=r['c_netlist'], rc=r['rc_netlist'], em_worst=r['em_table']['worst'], trim=r['trim_wires'], sha=r['sha256']), indent=1, default=str))
