"""Inspect independently downloaded GF180 AFE layouts; requires klayout.
Usage: python analyze.py AUTHOR.gds SUBMITTED.gds > evidence.json
No electrical equivalence or parasitic accuracy is implied by geometric equality.
"""
import hashlib
import json
import math
import sys
import klayout.db as k

layouts = []
sources = []
for path in sys.argv[1:]:
    layout = k.Layout()
    layout.read(path)
    layouts.append(layout)
    sources.append(dict(sha256=hashlib.sha256(open(path, 'rb').read()).hexdigest(),
                        dbu_um=layout.dbu, cells=layout.cells(),
                        tops=[c.name for c in layout.top_cells()]))
assert len(layouts) == 2
assert layouts[0].dbu == layouts[1].dbu
names = ['adc_top_final_deliver', 'opamp1_v2_to_fix', 'opamp2_to_fix',
         'adc_bootsw_debug5', 'adc_comp_miyahara_offcal', 'adc_preamp_v2',
         'lib_cap_array', 'lib_unit_cap_32x', 'lib_unit_cap_8192x']
blocks = {}
for name in names:
    a, b = [l.cell(name) for l in layouts]
    assert a is not None and b is not None, name
    layers = set(layouts[0].layer_infos()) | set(layouts[1].layer_infos())
    differences = []
    for info in sorted(layers, key=str):
        regions = []
        for l, c in zip(layouts, [a, b]):
            idx = l.find_layer(info)
            regions.append(k.Region() if idx is None else k.Region(c.begin_shapes_rec(idx)))
        if not (regions[0] ^ regions[1]).is_empty():
            differences.append(str(info))
    box = b.dbbox()
    blocks[name] = dict(width_um=box.width(), height_um=box.height(),
                        bounding_area_mm2=box.area()/1e6,
                        polygon_difference_layers=differences)
# Inferences use conventional full-scale sinusoidal ADC definitions. They do not
# presume Fig.7's ~5MHz tone belongs to the table's 20MS/s operating condition.
sndr = 6.02 * 4.27 + 1.76
noise = 10**(-41/20)
total = 10**(-sndr/20)
distortion = math.sqrt(total**2-noise**2)
print(json.dumps(dict(sources=sources, blocks=blocks, measurement_inferences=dict(
    equivalent_sndr_db=sndr, noise_rms_over_signal_rms=noise,
    noise_plus_distortion_rms_over_signal_rms=total,
    distortion_rms_over_signal_rms=distortion,
    largest_spur_amplitude_over_fundamental=10**(-33.7/20),
    cmrr_input_equivalent_v_per_v=10**(-58/20),
    psrr_input_equivalent_v_per_v=10**(-81.5/20),
    offset_input_equivalent_v=[.005,.020],
    distortion_power_over_largest_spur_power=(distortion/10**(-33.7/20))**2,
    hypothetical_jitter_only_snr_bound_s_at_5mhz=noise/(2*math.pi*5e6),
    gbw_measured_over_simulated=12.5/14,
    dc_gain_measured_over_simulated=10**((92-99)/20),
    status='Derived, conditional on compatible measurement definitions; not fitted device parameters'),
    limitations=['Polygon XOR ignores text and does not prove electrical equivalence.',
                 'Bounding boxes include routing and do not measure active device area.',
                 'This report covers provenance and algebraic measurement constraints; separate reports contain circuit reconstruction.',
                 'CMRR/PSRR give input-equivalent response ratios, not measured threshold mismatch or device sensitivity.',
                 'The 5 MHz jitter-only bound is hypothetical: table SNR and figure tone may be different measurements.']), indent=2))
