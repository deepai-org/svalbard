"""build + verify wtx_mux8 into s13/mux3 (no copy to generated/fast: that happens at the end, with the block)."""
import sys, json
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_tx')
import wtx_mux8_layout as L
r = L.run_all(publish=False)
v = r['verify_from_disk']
print(json.dumps(dict(size_um=r['size_um'], area_um2=r['area_um2'], build=r['build_check'].get('drc_errors'), magic_drc=v['magic_drc'], klayout=v['klayout_drc'].get('violations'),
                      lvs=v['lvs']['summary'], negatives={k: x['fails_as_required'] for k, x in v['negative_controls'].items()},
                      antenna=v['antenna_magic'], rc=r['rc_netlist'], c_netlist={k: r['c_netlist'][k] for k in ('vsubs_lines_fixed', 'ports_ok', 'devices', 'floating_vsubs_left')},
                      outputs_fF={n: r['wire_c_fF'][n]['total'] for n in L.BUS_ORDER}, em_worst=r['em_table']['worst'], sha256=r['sha256']), indent=1, default=str))
