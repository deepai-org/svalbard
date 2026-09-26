"""Conditional physical estimates grounded in recovered layout and public specs.
Run after cap_geometry.py and preamp_extract.py ... --json; never a PEX substitute.
"""
import json
import math
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[2]
caps=json.loads((root/'evidence/reference-afe-cap-geometry.json').read_text())
connected=json.loads(Path(sys.argv[1]).read_text())
selected=[d for d in connected['devices'] if any(n in ['x_preoutp','x_preoutn'] for n in d['terminals'].values())]
gates=[d for d in selected if d['type']=='nmos' and d['terminals']['G'] in ['x_preoutp','x_preoutn']]
assert len(gates)==2
for d in gates:
 assert math.isclose(d['parameters']['W'],16) and math.isclose(d['parameters']['L'],.28)
area=sum(x['m3_m4_overlap_um2'] for x in caps['bit_geometry'].values())
rows=[]
for density in [.0337,.0394,.0472]:
 capacitance=area*density*1e-15
 rows.append(dict(m4_m3_density_ff_per_um2=density,overlap_only_array_capacitance_pf=capacitance*1e12,
                  differential_sampling_noise_uv=math.sqrt(2*1.380649e-23*300.15/capacitance)*1e6))
print(json.dumps(dict(
 source_sha256=connected['source_sha256'],connected_cell=connected['cell'],
 directly_connected_devices=selected,
 input_gate_oxide_plate_ff=[16*.28*c for c in [3.4,4.4,5.4]],
 input_gate_oxide_note='Cox*drawn W*L plate scale, not measured dynamic Cin; excludes overlap, bias partition, Miller and kickback.',
 capacitor_overlap_area_um2=area,capacitance_scenarios=rows,
 measurement_scenario=dict(sine_vpp=6,signal_rms_v=6/(2*math.sqrt(2)),noise_rms_mv=6/(2*math.sqrt(2))*10**(-41/20)*1000),
 sources=['https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_5_3.html',
          'https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_5_6.html',
          'https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=957346'],
 limitations=['Assuming two equal arrays and independent kT/C noise at 300.15K.',
              'Overlap model omits fringe and field shielding; density range is not a full capacitance confidence interval.',
              '6Vpp is a paper input-swing figure, not confirmed actual FFT tone amplitude.',
              'Published ADC SNR includes the measurement chain; cannot assign it to comparator or transistor noise.',
              'Connected geometry extraction has incomplete well/body/supply-island modeling; inspect preserved islands before circuit simulation.']),indent=2))
